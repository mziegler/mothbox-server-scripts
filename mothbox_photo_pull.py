"""Continuous photo-pull daemon.

Runs each Mothbox device's rclone transfer as a non-blocking background
process, so multiple devices' pulls -- including any backlog-clearing,
which can take minutes to hours over a slow/high-latency link -- proceed
independently instead of one device blocking another. The public
latest-photo/dashboard data (see livestream.py) is refreshed on its own
fixed PHOTO_PULL_POLL_INTERVAL_SECONDS cadence, decoupled from whatever
any in-flight transfer is doing, so the livestream stays close to
real-time regardless of backlog size.

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
from livestream import generate_dashboard_data, update_latest_photo

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


def _start_pull(mothbox: dict):
    """Launch a single device's rclone pull as a background process.

    Returns (proc, log_fh, start_time); the caller is responsible for
    reaping it (see _reap_pulls) and closing log_fh once it's done.
    """
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
        # Newest-captured photos first, so during a big backlog the true
        # latest photo lands locally within the first few transfers instead
        # of waiting behind the entire rest of the backlog.
        "--order-by", "modtime,descending",
        "-v",
    ]
    log = open(PHOTO_PULL_LOG_PATH, "a")
    proc = subprocess.Popen(cmd, stdout=log, stderr=log)
    return proc, log, time.monotonic()


def _reap_pulls(active: dict):
    """Close out any finished or timed-out pulls, mutating `active` in place."""
    for mothbox_name in list(active):
        proc, log, start_time = active[mothbox_name]
        elapsed = time.monotonic() - start_time

        if proc.poll() is not None:
            log.close()
            del active[mothbox_name]
        elif elapsed > PHOTO_PULL_TRANSFER_TIMEOUT_SECONDS:
            proc.kill()
            proc.wait()
            log.write(
                f"\n[mothbox_photo_pull] Killed rclone after {elapsed:.0f}s -- "
                f"{mothbox_name} likely went offline mid-transfer. Will retry next poll.\n"
            )
            log.close()
            del active[mothbox_name]


def run():
    mothboxes = load_mothbox_list()
    print(f"Photo-pull daemon started — monitoring {len(mothboxes)} device(s).", flush=True)
    active = {}
    while True:
        _reap_pulls(active)

        if in_collection_window():
            for mothbox in mothboxes:
                if mothbox["mothboxName"] not in active:
                    active[mothbox["mothboxName"]] = _start_pull(mothbox)

        for mothbox in mothboxes:
            update_latest_photo(mothbox)
        generate_dashboard_data(mothboxes)

        time.sleep(PHOTO_PULL_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
