import requests
import os
import tempfile
import json
from typing import List, Tuple

# Use environment variable or default key if not set
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "coD9kTa2eddhJ7xKvhLexYVeh1SVjZqGcUgS1DQLnAbR8QZOLOtCUEDY")
PEXELS_VIDEO_SEARCH_URL = "https://api.pexels.com/videos/search"
# Store used assets file within the shared storage if possible, or fallback to temp
STORAGE_DIR = os.getenv("STORAGE_BASE_PATH", tempfile.gettempdir())
USED_ASSETS_FILE = os.path.join(STORAGE_DIR, "pexels_used_assets.json")


def _load_used_assets() -> dict:
    if os.path.exists(USED_ASSETS_FILE):
        try:
            with open(USED_ASSETS_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not decode {USED_ASSETS_FILE}, starting fresh.")
            return {}
    return {}


def _save_used_assets(data: dict):
    try:
        with open(USED_ASSETS_FILE, "w") as f:
            json.dump(data, f, indent=2) # Add indent for readability
    except IOError as e:
        print(f"Error saving used assets file: {e}")


def _register_used_combination(video_ids: List[str]):
    if not video_ids: # Avoid registering empty lists
        return
    data = _load_used_assets()
    # Use a frozenset for unordered, hashable key
    key = str(frozenset(video_ids))
    data[key] = True
    _save_used_assets(data)


def _is_combination_used(video_ids: List[str]) -> bool:
    if not video_ids:
        return False # Empty combination is never "used"
    data = _load_used_assets()
    key = str(frozenset(video_ids))
    return key in data


def get_pexels_videos_for_duration(query, total_duration, min_duration=5, max_duration=60, max_videos=10) -> Tuple[List[str], List[float], List[str]]:
    headers = {"Authorization": PEXELS_API_KEY}
    # Add orientation parameter if needed, e.g., landscape
    params = {
        "query": query,
        "per_page": max(max_videos * 3, 30), # Fetch a decent amount for variety, min 30
        "min_duration": min_duration,
        "max_duration": max_duration,
        "orientation": "landscape" # Assuming landscape is preferred
    }
    print(f"Searching Pexels with params: {params}")
    try:
        response = requests.get(PEXELS_VIDEO_SEARCH_URL, headers=headers, params=params, timeout=15) # Add timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
    except requests.exceptions.RequestException as e:
        print(f"Pexels API request failed: {e}")
        return [], [], []

    urls = []
    durations = []
    video_ids = []

    data = response.json()
    candidates = []
    seen_ids = set() # Keep track of video IDs already added

    for video in data.get("videos", []):
        video_id = str(video.get("id"))
        if not video_id or video_id in seen_ids:
            continue # Skip if no ID or duplicate

        # --- Stricter filtering for "person" ---
        tags = video.get("tags", [])
        # Check if 'person' or related terms appear in tags
        person_in_tags = any("person" in tag.lower() for tag in tags if isinstance(tag, str))
        if person_in_tags:
            # print(f"Skipping video {video_id} due to 'person' tag.")
            continue

        # Check video URL segments
        video_url_lower = (video.get("url", "") or "").lower()
        if "/people/" in video_url_lower or "person" in video_url_lower:
            # print(f"Skipping video {video_id} due to 'person' in URL.")
            continue

        # Check user name
        user_name_lower = video.get("user", {}).get("name", "").lower()
        if "person" in user_name_lower or "people" in user_name_lower:
             # print(f"Skipping video {video_id} due to 'person' in user name.")
            continue
        # --- End stricter filtering ---

        video_files = video.get("video_files", [])
        if not video_files:
            continue

        # Prefer HD or higher resolution, landscape
        valid_files = [
            f for f in video_files
            if f.get("width") and f.get("height") and f.get("width") >= 1280 and f.get("width") > f.get("height")
        ]

        if not valid_files:
             # Fallback: If no HD landscape, take highest width landscape if any
             valid_files = [
                 f for f in video_files
                 if f.get("width") and f.get("height") and f.get("width") > f.get("height")
             ]

        if not valid_files:
            continue # Skip if no suitable landscape file found

        # Sort by width descending to get the best quality
        valid_files.sort(key=lambda x: x["width"], reverse=True)
        chosen_file = valid_files[0]

        url = chosen_file.get("link")
        duration = video.get("duration")

        if url and duration:
            candidates.append((video_id, url, duration))
            seen_ids.add(video_id)

    print(f"Found {len(candidates)} suitable candidates from Pexels for query '{query}'.")

    # Try to find an unused combination that meets the duration requirement
    import random
    random.shuffle(candidates) # Shuffle for variety

    if not candidates:
         print("No suitable candidates found after filtering.")
         return [], [], []

    # Iteratively build a combination until duration is met or candidates run out
    current_combo_ids = []
    current_urls = []
    current_durations = []
    current_total_duration = 0

    for video_id, url, duration in candidates:
        # Check if adding this video keeps the combination unused
        temp_combo_ids = sorted(current_combo_ids + [video_id])
        if not _is_combination_used(temp_combo_ids):
            current_combo_ids.append(video_id)
            current_urls.append(url)
            current_durations.append(duration)
            current_total_duration += duration

            # Check if we have enough duration and videos
            if current_total_duration >= total_duration and len(current_urls) <= max_videos:
                 urls = current_urls
                 durations = current_durations
                 video_ids = current_combo_ids
                 print(f"Selected {len(urls)} videos with total duration {current_total_duration:.2f}s. Combination IDs: {video_ids}")
                 _register_used_combination(video_ids)
                 return urls, durations, video_ids # Found a suitable unused combo

    # If loop finishes without meeting duration using only unused combos,
    # try to build the best possible combo even if used, prioritizing duration.
    if not urls:
        print("Could not find an unused combination meeting the duration. Building best possible combo.")
        # Sort candidates by duration descending to prioritize longer clips first
        candidates.sort(key=lambda x: x[2], reverse=True)
        current_combo_ids = []
        current_urls = []
        current_durations = []
        current_total_duration = 0
        for video_id, url, duration in candidates:
             if len(current_urls) < max_videos:
                 current_combo_ids.append(video_id)
                 current_urls.append(url)
                 current_durations.append(duration)
                 current_total_duration += duration
                 if current_total_duration >= total_duration:
                     break # Stop once duration is met

        urls = current_urls
        durations = current_durations
        video_ids = current_combo_ids
        print(f"Selected {len(urls)} videos (may be a used combination) with total duration {current_total_duration:.2f}s. IDs: {video_ids}")
        # Optionally register this combination as used if you want to track it anyway
        # _register_used_combination(video_ids)

    # Return whatever combination was selected
    return urls, durations, video_ids


def download_asset(url, filename):
    # Use the shared storage directory
    temp_dir = os.getenv("STORAGE_BASE_PATH", tempfile.gettempdir())
    # Create a subdirectory for pexels downloads if it doesn't exist
    download_dir = os.path.join(temp_dir, "pexels_downloads")
    os.makedirs(download_dir, exist_ok=True)

    # Sanitize filename slightly (replace common problematic chars)
    safe_filename = filename.replace("/", "_").replace("\", "_").replace(":", "_").replace("*", "_").replace("?", "_").replace(""", "_").replace("<", "_").replace(">", "_").replace("|", "_")
    path = os.path.join(download_dir, safe_filename)

    if os.path.exists(path):
        print(f"Asset already exists: {path}")
        return path

    print(f"Downloading: {url} -> {path}")
    try:
        r = requests.get(url, stream=True, timeout=60) # Increased timeout for download
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192 * 2): # Slightly larger chunk size
                f.write(chunk)
        print(f"Successfully downloaded: {path}")
        return path
    except requests.exceptions.RequestException as e:
        print(f"Failed to download {url}: {e}")
        # Clean up partially downloaded file if it exists
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError as rm_e:
                print(f"Could not remove partial file {path}: {rm_e}")
        raise # Re-raise the exception so the caller knows it failed 