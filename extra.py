import json
import shutil
import zipfile
import tempfile
from PIL import Image
import os
from dotenv import load_dotenv
from db import init_db, ensure_file_logged, save_tags, set_total_size

load_dotenv()
thepath = os.getenv("THEPATH")

def getsize(path):
    total = 0
    for entry in os.scandir(path):
        if entry.is_file():
            total += entry.stat().st_size
        elif entry.is_dir():
            total += getsize(entry.path)
    return total

mysize = getsize(thepath)
set_total_size(mysize)
print(f"finished calculating size: {mysize} bytes, {mysize / (1024 **3)} gb")

# with open('archives.json', 'r') as f:
#     data = json.load(f)
#     print(len(data))

# def convert_ugoira_to_gif(zip_path, gif_path):
#     """Extract a ugoira zip and stitch its frames into a GIF. Frame order +
#     per-frame delay (ms) come from a JSON file bundled inside the zip itself
#     (e.g. 'animation.json'), not from the Danbooru API. Cleans up extracted
#     frames after."""
#     temp_dir = tempfile.mkdtemp()
#     try:
#         with zipfile.ZipFile(zip_path) as zf:
#             zf.extractall(temp_dir)
 
#         # Find the frame-timing JSON inside the extracted contents -- its
#         # name can vary (animation.json is typical), so just grab whichever
#         # .json file is in there.
#         json_files = [f for f in os.listdir(temp_dir) if f.endswith(".json")]
#         if not json_files:
#             return False
 
#         with open(os.path.join(temp_dir, json_files[0])) as f:
#             meta = json.load(f)
 
#         frames_info = meta.get("frames", [])
#         if not frames_info:
#             return False
 
#         images = []
#         durations = []
#         for frame in frames_info:
#             frame_path = os.path.join(temp_dir, frame["file"])
#             if not os.path.exists(frame_path):
#                 continue
#             images.append(Image.open(frame_path).convert("RGBA"))
#             durations.append(frame.get("delay", 100))  # ms, fallback 100ms
 
#         if not images:
#             return False
 
#         images[0].save(
#             gif_path,
#             save_all=True,
#             append_images=images[1:],
#             duration=durations,
#             loop=0,
#             disposal=2,
#         )
#         return True
#     finally:
#         shutil.rmtree(temp_dir, ignore_errors=True)

# ok = convert_ugoira_to_gif(r"D:\danbooru downloads\11732594\11735058.zip", r"D:\danbooru downloads\11732594\11735058.gif")
# if ok:
#     print("yessss delete the zip manually now.")