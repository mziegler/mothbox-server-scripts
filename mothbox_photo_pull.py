"""Continuous photo-pull daemon.

Pulls photos from every Mothbox device listed in mothbox-list.csv once per
PHOTO_PULL_POLL_INTERVAL_SECONDS, but only during the nightly collection
window defined in mothboxServerConfig.py.  Outside that window the loop
sleeps and does nothing.

Transfers are done with rclone, via the per-device remote named in each
row's "rcloneRemote" column (set up with `rclone config`). rclone performs
much better than rsync over high-latency/low-bandwidth links like Starlink.

Run this as a long-running process (e.g. via docker-compose service
'photo-pull').
"""

import csv
import datetime
import os
import subprocess
import time
import zoneinfo

from mothboxServerConfig import (
    NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH,
    PHOTO_PULL_LOG_PATH,
    CAMERA_TIMEZONE,
    COLLECTION_START_HOUR,
    COLLECTION_END_HOUR,
    PHOTO_PULL_POLL_INTERVAL_SECONDS,
    PHOTO_PULL_MIN_FILE_AGE,
    PHOTO_PULL_TRANSFER_TIMEOUT_SECONDS,
)
from livestream import generate_dashboard_html, update_latest_photo

_TZ = zoneinfo.ZoneInfo(CAMERA_TIMEZONE)


def load_mothbox_list(filename="mothbox-list.csv"):
    """Load device list from CSV. Path is relative to this file's directory."""
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    with open(csv_path) as f:
        return list(csv.DictReader(f))


def in_collection_window() -> bool:
    """Return True if the current local time is inside the collection window."""
    hour = datetime.datetime.now(tz=_TZ).hour
    return hour >= COLLECTION_START_HOUR or hour < COLLECTION_END_HOUR


def pull_device(mothbox: dict):
    """Run a single rclone pull for one Mothbox device."""
    src = f'{mothbox["rcloneRemote"]}:/home/pi/Desktop/Mothbox/photos'
    dst = os.path.join(
        NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH,
        mothbox["deploymentName"],
    )
    os.makedirs(dst, exist_ok=True)

    cmd = [
        "rclone", "move",
        src,
        dst,
        "--transfers", "8",
        "--checkers", "8",
        "--retries", "5",
        "--low-level-retries", "10",
        "--timeout", "5m",
        "--contimeout", "30s",
        "--min-age", PHOTO_PULL_MIN_FILE_AGE,
        "-P",
    ]
    with open(PHOTO_PULL_LOG_PATH, "a") as log:
        try:
            subprocess.run(cmd, stdout=log, stderr=log, timeout=PHOTO_PULL_TRANSFER_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            log.write(
                f"\n[mothbox_photo_pull] Killed rclone after "
                f"{PHOTO_PULL_TRANSFER_TIMEOUT_SECONDS}s -- {mothbox['mothboxName']} likely "
                "went offline mid-transfer. Will retry next poll.\n"
            )
            log.flush()

    update_latest_photo(mothbox)


def run():
    mothboxes = load_mothbox_list()
    print(f"Photo-pull daemon started — monitoring {len(mothboxes)} device(s).", flush=True)
    generate_dashboard_html(mothboxes)
    while True:
        if in_collection_window():
            for mothbox in mothboxes:
                pull_device(mothbox)
        time.sleep(PHOTO_PULL_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
