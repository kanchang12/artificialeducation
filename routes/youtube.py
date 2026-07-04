import time
import xml.etree.ElementTree as ET
import requests
from flask import Blueprint, render_template, jsonify

youtube_bp = Blueprint("youtube", __name__)

# AI With AI — https://www.youtube.com/@aiwithai-y9t
YOUTUBE_CHANNEL_ID = "UCPH_DSgSxIdoQ4qpalUfRyQ"
RSS_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={YOUTUBE_CHANNEL_ID}"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}

_cache = {"videos": [], "fetched_at": 0}
CACHE_TTL_SECONDS = 1800  # 30 min — channel feed only needs to refresh occasionally


def fetch_channel_videos(force=False):
    """Pull the latest videos from the channel's public RSS feed (no API key needed).
    Cached in memory for CACHE_TTL_SECONDS so we don't hit YouTube on every page load."""
    now = time.time()
    if not force and _cache["videos"] and (now - _cache["fetched_at"]) < CACHE_TTL_SECONDS:
        return _cache["videos"]

    try:
        resp = requests.get(RSS_URL, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        videos = []
        for entry in root.findall("atom:entry", NS):
            video_id_el = entry.find("yt:videoId", NS)
            title_el = entry.find("atom:title", NS)
            published_el = entry.find("atom:published", NS)
            group = entry.find("media:group", NS)
            description = ""
            thumbnail = ""
            if group is not None:
                desc_el = group.find("media:description", NS)
                description = (desc_el.text or "").strip() if desc_el is not None else ""
                thumb_el = group.find("media:thumbnail", NS)
                if thumb_el is not None:
                    thumbnail = thumb_el.get("url", "")

            if video_id_el is None:
                continue
            vid = video_id_el.text
            videos.append({
                "id": vid,
                "title": title_el.text if title_el is not None else "Untitled",
                "published": published_el.text if published_el is not None else "",
                "description": description[:220],
                "thumbnail": thumbnail or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                "url": f"https://www.youtube.com/watch?v={vid}",
            })

        # Feed is already newest-first, but sort defensively
        videos.sort(key=lambda v: v["published"], reverse=True)
        _cache["videos"] = videos
        _cache["fetched_at"] = now
    except Exception:
        # Network hiccup or feed temporarily unavailable — fall back to whatever's cached
        pass

    return _cache["videos"]


@youtube_bp.route("/youtube", methods=["GET", "POST"])
def youtube_videos():
    videos = fetch_channel_videos()
    return render_template(
        "youtube.html",
        videos=videos,
        channel_url="https://www.youtube.com/@aiwithai-y9t",
        stale=(not videos),
    )


@youtube_bp.route("/api/videos/refresh", methods=["GET", "POST"])
def youtube_videos_refresh():
    videos = fetch_channel_videos(force=True)
    return jsonify({"ok": True, "count": len(videos), "videos": videos})
