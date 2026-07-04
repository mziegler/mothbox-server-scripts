"""Continuous rsync daemon.

Pulls photos from every Mothbox device listed in mothbox-list.csv once per
RSYNC_POLL_INTERVAL_SECONDS, but only during the nightly collection window
defined in mothboxServerConfig.py.  Outside that window the loop sleeps and
does nothing.

Replaces the cron-based approach in scheduleRsync.py.  Run this as a
long-running process (e.g. via docker-compose service 'rsync').
"""

import csv
import datetime
import os
import subprocess
import time
import zoneinfo

from mothboxServerConfig import (
    NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH,
    RSYNC_LOG_PATH,
    CAMERA_TIMEZONE,
    COLLECTION_START_HOUR,
    COLLECTION_END_HOUR,
    RSYNC_POLL_INTERVAL_SECONDS,
)

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


def rsync_device(mothbox: dict):
    """Run a single rsync pull for one Mothbox device."""
    src = f'{mothbox["hostOrIP"]}:/home/pi/Desktop/Mothbox/photos/*'
    dst = os.path.join(
        NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH,
        mothbox["deploymentName"],
    ) + "/"
    os.makedirs(dst, exist_ok=True)
    cmd = ["rsync", "-rv", "--times", "--remove-source-files", "--mkpath", src, dst]
    with open(RSYNC_LOG_PATH, "a") as log:
        subprocess.run(cmd, stdout=log, stderr=log)


def run():
    mothboxes = load_mothbox_list()
    print(f"Rsync daemon started — monitoring {len(mothboxes)} device(s).", flush=True)
    while True:
        if in_collection_window():
            for mothbox in mothboxes:
                rsync_device(mothbox)
        time.sleep(RSYNC_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
