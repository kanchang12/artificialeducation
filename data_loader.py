import json, glob, os

BASE = os.path.dirname(__file__)

def load_labs():
    labs = []
    for f in sorted(glob.glob(os.path.join(BASE, "data/labs/*.json"))):
        with open(f) as fp:
            labs.append(json.load(fp))
    return labs

def load_sandboxes():
    sbs = []
    for f in sorted(glob.glob(os.path.join(BASE, "data/sandbox_labs/*.json"))):
        with open(f) as fp:
            sbs.append(json.load(fp))
    return sbs

def get_lab(task_id):
    for lab in load_labs():
        if lab.get("task_id") == task_id:
            return lab
    return None

def get_sandbox(sb_id):
    for sb in load_sandboxes():
        if sb.get("id") == sb_id:
            return sb
    return None

def load_videos():
    videos = []
    for f in sorted(glob.glob(os.path.join(BASE, "data/videos/*.json"))):
        with open(f) as fp:
            videos.append(json.load(fp))
    return videos

def get_video(video_id):
    for v in load_videos():
        if v.get("id") == video_id:
            return v
    return None

def load_blackbox():
    items = []
    for f in sorted(glob.glob(os.path.join(BASE, "data/blackbox/*.json"))):
        with open(f) as fp:
            items.append(json.load(fp))
    return items

def get_blackbox(bb_id):
    for bb in load_blackbox():
        if bb.get("id") == bb_id:
            return bb
    return None

DIFFICULTY_ORDER = {"easy": 1, "medium": 2, "hard": 3, "legend": 4}
