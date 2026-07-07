"""Maintains the public "latest photo" livestream feed.

Copies the newest synced photo for each Mothbox device to a stable,
world-servable path, and generates a small static dashboard listing every
device. Both are read by the 'livestream' nginx container defined in
docker-compose.yml, which is meant to sit behind a CDN cache (e.g.
Cloudflare) so public viewers never hit this VM directly.
"""

import os
import shutil

from mothboxServerConfig import (
    NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH,
    LATEST_PHOTOS_DIRECTORY_PATH,
    LATEST_PHOTO_EXTENSIONS,
    LIVESTREAM_REFRESH_SECONDS,
)


def _latest_daily_folder(deployment_dir: str):
    """Return the path of the most recent per-night subfolder (e.g. "fluidRobin_2026-06-26").

    Subfolder names embed a fixed-width, zero-padded date, so the
    lexicographically-last name is also the most recent one -- no need to
    parse dates or scan every subfolder's contents. Returns None if
    deployment_dir doesn't exist yet or has no subfolders.
    """
    if not os.path.isdir(deployment_dir):
        return None
    subfolders = [
        name for name in os.listdir(deployment_dir)
        if os.path.isdir(os.path.join(deployment_dir, name))
    ]
    if not subfolders:
        return None
    return os.path.join(deployment_dir, max(subfolders))


def _newest_photo_in_folder(folder: str):
    """Return the path of the most recently captured photo in a single daily folder.

    Filenames embed a fixed-width, zero-padded timestamp (e.g.
    "fluidRobin_2026_06_26__20_49_06_HDR0.jpg"), so the lexicographically-last
    matching filename is also the most recent capture -- this holds
    regardless of any trailing suffix (like "_HDR0") since it comes after
    the fixed-width timestamp digits.
    """
    candidates = sorted(
        name for name in os.listdir(folder)
        if os.path.splitext(name)[1].lower() in LATEST_PHOTO_EXTENSIONS
    )
    if not candidates:
        return None
    return os.path.join(folder, candidates[-1])


def update_latest_photo(mothbox: dict):
    """Copy the most recently synced photo for one device to a stable public path."""
    deployment_dir = os.path.join(NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH, mothbox["deploymentName"])
    daily_folder = _latest_daily_folder(deployment_dir)
    if daily_folder is None:
        return
    newest_path = _newest_photo_in_folder(daily_folder)
    if newest_path is None:
        return

    os.makedirs(LATEST_PHOTOS_DIRECTORY_PATH, exist_ok=True)
    dest = os.path.join(LATEST_PHOTOS_DIRECTORY_PATH, f'{mothbox["mothboxName"]}.jpg')
    tmp_dest = dest + ".tmp"
    shutil.copyfile(newest_path, tmp_dest)
    os.replace(tmp_dest, dest)  # atomic rename avoids ever serving a half-written file


def generate_dashboard_html(mothboxes):
    """Write a static dashboard listing every device's latest photo."""
    cards = "\n".join(
        f'''    <div class="device">
      <h2>{mb["mothboxName"]}</h2>
      <img src="{mb["mothboxName"]}.jpg" alt="{mb["mothboxName"]}">
    </div>'''
        for mb in mothboxes
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mothbox Livestream</title>
<style>
  body {{ font-family: sans-serif; background: #111; color: #eee; margin: 0; padding: 1.5rem; }}
  h1 {{ text-align: center; }}
  .grid {{ display: flex; flex-wrap: wrap; gap: 1.5rem; justify-content: center; }}
  .device {{ text-align: center; }}
  .device img {{ max-width: 480px; width: 100%; height: auto; border-radius: 4px; background: #222; }}
</style>
</head>
<body>
<h1>Mothbox Livestream</h1>
<div class="grid">
{cards}
</div>
<script>
  // Images are cached at the edge/browser for LIVESTREAM_REFRESH_SECONDS;
  // re-assigning the same src re-triggers the fetch once that expires.
  setInterval(() => {{
    document.querySelectorAll('.device img').forEach(img => {{ img.src = img.src; }});
  }}, {LIVESTREAM_REFRESH_SECONDS * 1000});
</script>
</body>
</html>
"""
    os.makedirs(LATEST_PHOTOS_DIRECTORY_PATH, exist_ok=True)
    dest = os.path.join(LATEST_PHOTOS_DIRECTORY_PATH, "index.html")
    tmp_dest = dest + ".tmp"
    with open(tmp_dest, "w") as f:
        f.write(html)
    os.replace(tmp_dest, dest)
