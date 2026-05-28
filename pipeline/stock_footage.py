import os
import requests
from config import PEXELS_API_KEY


def download_clips(keywords: list, count: int = 4, output_dir: str = "temp") -> list:
    """Download one stock video clip per keyword from Pexels.

    Each keyword gets its own search, and we pick the top result.
    This ensures clips are relevant to each part of the script.

    Args:
        keywords: List of search queries (e.g., ["baby elephant", "cute kitten"]).
        count: Max number of clips to download.
        output_dir: Directory to save downloaded clips.

    Returns:
        List of file paths to downloaded clips.
    """
    headers = {"Authorization": PEXELS_API_KEY}
    downloaded = []
    seen_ids = set()

    for keyword in keywords[:count]:
        # Search for videos matching this specific keyword
        params = {
            "query": keyword,
            "per_page": 5,
            "size": "medium",
        }

        try:
            response = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            continue

        # Pick the best matching clip from results
        clip_downloaded = False
        for video in data.get("videos", []):
            if clip_downloaded:
                break

            video_id = video["id"]
            if video_id in seen_ids:
                continue
            seen_ids.add(video_id)

            video_files = video.get("video_files", [])
            best_file = _pick_best_file(video_files)
            if not best_file:
                continue

            download_url = best_file["link"]
            file_path = os.path.join(output_dir, f"clip_{video_id}.mp4")

            try:
                vid_response = requests.get(download_url, timeout=60)
                vid_response.raise_for_status()
                with open(file_path, "wb") as f:
                    f.write(vid_response.content)
                downloaded.append(file_path)
                clip_downloaded = True
            except requests.RequestException:
                continue

    return downloaded


def _pick_best_file(video_files: list) -> dict | None:
    """Pick the best quality video file, preferring HD."""
    if not video_files:
        return None

    # Prefer files with decent resolution
    suitable = [vf for vf in video_files if vf.get("height", 0) >= 720]

    if not suitable:
        suitable = [vf for vf in video_files if vf.get("height", 0) >= 480]

    if not suitable:
        suitable = video_files

    # Sort by height descending, pick highest quality
    suitable.sort(key=lambda x: x.get("height", 0), reverse=True)
    return suitable[0]
