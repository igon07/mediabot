import os
import time
from db import init_db, ensure_file_logged, save_tags
from main import DIRECTORY, get_post, get_descendants

def backfill():
    init_db()
    entries = os.listdir(DIRECTORY)

    for entry in entries:
        full_path = os.path.join(DIRECTORY, entry)

        if os.path.isdir(full_path):
            item_id = entry
            print(f"backfilling folder {item_id}")
            root_post = get_post(int(item_id))
            family = [root_post] + get_descendants(int(item_id))
            unique = list({p["id"]: p for p in family}.values())
            downloadable = [p for p in unique if p.get("file_url")]
            score = max((p.get("score", 0) for p in downloadable), default=0)

        elif os.path.isfile(full_path):
            item_id = os.path.splitext(entry)[0]
            print(f"backfilling file {item_id}")
            post = get_post(int(item_id))
            downloadable = [post]
            score = post.get("score", 0)

        else:
            continue

        ensure_file_logged(item_id, full_path, score=score)
        save_tags(item_id, downloadable)
        time.sleep(0.3)

    print("backfill complete")

if __name__ == "__main__":
    backfill()