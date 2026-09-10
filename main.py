import requests
import os
import json
import time
from dotenv import load_dotenv
import zipfile
import glob
import shutil
import tempfile
from PIL import Image
from db import init_db, ensure_file_logged, save_tags, set_total_size

load_dotenv()

BASE = os.getenv("MAINURL")     # last slash included during api_get
USERNAME = os.getenv("MYLOGIN")
LOGIN = os.getenv("MYLOGIN")
API_KEY = os.getenv("MYAPI")
DIRECTORY = os.getenv("THEPATH")
ARCHIVE = os.getenv("ARCHPATH")
DELAY = .2
thepath = os.getenv("THEPATH")

session = requests.Session()
session.headers.update({"User-Agent": f"myscript ({USERNAME})"})

def api_get(path, params=None):
    params = dict(params or {})
    params["login"] = LOGIN
    params["api_key"] = API_KEY
    r = session.get(f"{BASE}{path}", params=params)
    r.raise_for_status()
    time.sleep(DELAY)
    return r.json()


def get_post(id):
    return api_get(f"/posts/{id}.json")

def get_all_pages(tags):
    posts = []
    page = 1
    while True:
        batch = api_get("/posts.json", {"tags" : tags, "limit" : 200, "page" : page})
        if not batch:
            break
        posts.extend(batch)
        if len(batch) < 200:
            break
        page +=1
    return posts

def get_favs():
    # posts = []
    # batch = api_get("/posts.json", {"tags" : f"ordfav:{USERNAME}", "limit" : 150, "page" : 1})
    # posts.extend(batch)
    # return posts
    return get_all_pages(f"ordfav:{USERNAME}")

def get_children(pid):
    return get_all_pages(f"parent:{pid} order:id_asc")

def get_descendants(pid, seen=None):
    if seen is None:
        seen = set()
    seen.add(pid)

    children = get_children(pid)
    all_posts = []
    for child in children:
        if child["id"] in seen:
            continue
        seen.add(child["id"])
        all_posts.append(child)
        all_posts.extend(get_descendants(child["id"], seen))
    return all_posts

def find_root_id(post):
    id = post.get("parent_id") or post["id"]
    seen = {post["id"], id}
    current = post if post["id"] == id else get_post(id)
    while current.get("parent_id") and current["parent_id"] not in seen:
        id = current["parent_id"]
        seen.add(id)
        current = get_post(id)
    return id

def load_archive():
    if os.path.exists(ARCHIVE):
        with open(ARCHIVE, 'r') as f:
            return set(json.load(f))
    return set()

def save_archive(ids):
    with open(ARCHIVE, 'w') as f:
        json.dump(sorted(ids), f)
    
def download_file(url, destination):
    if os.path.exists(destination):
        return
    r = session.get(url, stream=True)
    r.raise_for_status()
    with open(destination, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

def is_ugoira(post):
    #zip file detection
    return post.get("file_ext") == "zip"

def convert_ugoira_to_gif(zip_path, gif_path):
    """Extract a ugoira zip and stitch its frames into a GIF. Frame order +
    per-frame delay (ms) come from a JSON file bundled inside the zip itself
    (e.g. 'animation.json'), not from the Danbooru API. Cleans up extracted
    frames after."""
    temp_dir = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(temp_dir)
 
        # Find the frame-timing JSON inside the extracted contents -- its
        # name can vary (animation.json is typical), so just grab whichever
        # .json file is in there.
        json_files = [f for f in os.listdir(temp_dir) if f.endswith(".json")]
        if not json_files:
            return False
 
        with open(os.path.join(temp_dir, json_files[0])) as f:
            meta = json.load(f)
 
        frames_info = meta.get("frames", [])
        if not frames_info:
            return False
 
        images = []
        durations = []
        for frame in frames_info:
            frame_path = os.path.join(temp_dir, frame["file"])
            if not os.path.exists(frame_path):
                continue
            images.append(Image.open(frame_path).convert("RGBA"))
            durations.append(frame.get("delay", 100))  # ms, fallback 100ms
 
        if not images:
            return False
 
        images[0].save(
            gif_path,
            save_all=True,
            append_images=images[1:],
            duration=durations,
            loop=0,
            disposal=2,
        )
        return True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def getsize(path):
    total = 0
    for entry in os.scandir(path):
        if entry.is_file():
            total += entry.stat().st_size
        elif entry.is_dir():
            total += getsize(entry.path)
    return total

def main():
    os.makedirs(DIRECTORY, exist_ok=True)
    downloaded_ids = load_archive()
    init_db()


    print("getting favs")
    favorites = get_favs()
    print(f"found {len(favorites)} posts")

    processed = set()

    for post in favorites:
        post_id = post["id"]
        if post_id in downloaded_ids:
            continue
        
        root_id = find_root_id(post)
        if root_id in processed:
            continue
        processed.add(root_id)

        root_post = get_post(root_id)
        family = [root_post] + get_descendants(root_id)
        unique = {p["id"]: p for p in family}.values()
        downloadable = [p for p in unique if p.get("file_url")]
        
        if len(downloadable) == 1: # if its not in any family child parent bundles
            folder = DIRECTORY
        else:
            folder = os.path.join(DIRECTORY, str(root_id))
            os.makedirs(folder, exist_ok=True)

            for existing_file in glob.glob(os.path.join(DIRECTORY, f"{root_id}.*")):
                new_path = os.path.join(folder, os.path.basename(existing_file))
                if not os.path.exists(new_path):
                    print(f"migrating standalone {existing_file} -> {new_path}")
                    shutil.move(existing_file, new_path)

        
        for p in downloadable:
            pid = p["id"]
            if pid in downloaded_ids:
                continue
            file_url = p["file_url"]
            ext = file_url.rsplit(".", 1)[-1]
            dest = os.path.join(folder, f"{pid}.{ext}")
            print(f"downloading {pid} to {dest}")
            download_file(file_url, dest)


            if is_ugoira(p):
                gif_dest = os.path.join(folder, f"{pid}.gif")
                if not os.path.exists(gif_dest):
                    print(f"    converting ugoira {pid} -> gif")
                    ok = convert_ugoira_to_gif(dest, gif_dest)
                    if ok:
                        os.remove(dest)  # drop the raw zip once the gif exists
                    else:
                        print(f"    ugoira conversion failed for {pid}, keeping zip")


            downloaded_ids.add(pid)

        
        
        save_archive(downloaded_ids)

        if len(downloadable) == 1:
            only = downloadable[0]
            ext = only["file_url"].rsplit(".", 1)[-1]
            if is_ugoira(only):
                ext = "gif"
            item_id = str(only["id"])
            filepath = os.path.join(DIRECTORY, f"{item_id}.{ext}")
            score = only.get("score", 0)
            ensure_file_logged(item_id, filepath, score=score)
            save_tags(item_id, [only])
        else:
            item_id = str(root_id)
            filepath = folder
            score = max(p.get("score", 0) for p in downloadable)
            ensure_file_logged(item_id, filepath, score=score)
            save_tags(item_id, downloadable)


    print("finished downloading")
    mysize = getsize(thepath)
    set_total_size(mysize)
    print(f"finished calculating size: {mysize} bytes, {mysize / (1024 **3)} gb")




if __name__ == "__main__":
    main()