import requests
import os
import tempfile
import json
from typing import List, Tuple

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "coD9kTa2eddhJ7xKvhLexYVeh1SVjZqGcUgS1DQLnAbR8QZOLOtCUEDY")
PEXELS_VIDEO_SEARCH_URL = "https://api.pexels.com/videos/search"
USED_ASSETS_FILE = os.path.join(tempfile.gettempdir(), "pexels_used_assets.json")


def _load_used_assets() -> dict:
    if os.path.exists(USED_ASSETS_FILE):
        with open(USED_ASSETS_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_used_assets(data: dict):
    with open(USED_ASSETS_FILE, "w") as f:
        json.dump(data, f)


def _register_used_combination(video_ids: List[str]):
    data = _load_used_assets()
    key = ",".join(sorted(video_ids))
    data[key] = True
    _save_used_assets(data)


def _is_combination_used(video_ids: List[str]) -> bool:
    data = _load_used_assets()
    key = ",".join(sorted(video_ids))
    return key in data


def get_pexels_videos_for_duration(query, total_duration, min_duration=5, max_duration=60, max_videos=10) -> Tuple[List[str], List[float]]:
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "per_page": max_videos * 3,  # busca mais para garantir variedade
        "min_duration": min_duration,
        "max_duration": max_duration
    }
    response = requests.get(PEXELS_VIDEO_SEARCH_URL, headers=headers, params=params)
    urls = []
    durations = []
    video_ids = []
    if response.status_code == 200:
        data = response.json()
        candidates = []
        for video in data.get("videos", []):
            tags = video.get("tags", [])
            user_name = video.get("user", {}).get("name", "").lower()
            # Basic filtering to avoid videos clearly showing people
            if any("person" in (t.get("title", "") or "").lower() for t in tags):
                continue
            if "person" in (video.get("url", "") or "").lower():
                continue
            if "person" in user_name:
                continue

            # Get highest quality video link
            video_files = video["video_files"]
            video_files = sorted(video_files, key=lambda x: x["width"], reverse=True)
            url = video_files[0]["link"]
            duration = video["duration"]
            video_id = str(video["id"])
            candidates.append((video_id, url, duration))

        # Try to find an unused combination of videos
        import random
        random.shuffle(candidates)

        # Try to assemble a set of videos that meets the duration without repeating combos
        # This logic might need refinement based on exact needs, but provides a basic attempt
        # For simplicity, this example picks the first valid, unused combo it finds
        for i in range(0, len(candidates) - max_videos + 1):
            combo = candidates[i:i+max_videos]
            combo_ids = [v[0] for v in combo]
            if not _is_combination_used(combo_ids):
                urls = [v[1] for v in combo]
                durations = [v[2] for v in combo]
                video_ids = combo_ids
                break # Use the first unused combo found

        if urls:
            _register_used_combination(video_ids) # Mark this combo as used

    return urls, durations

def download_asset(url, filename):
    temp_dir = tempfile.gettempdir()
    path = os.path.join(temp_dir, filename)
    if os.path.exists(path):
        print(f"Asset already downloaded: {path}")
        return path
    print(f"Downloading: {url} -> {path}")
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"Finished downloading: {path}")
    return path 