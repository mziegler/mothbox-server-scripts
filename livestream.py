"""Maintains the public "latest photo" livestream feed.

Copies the newest synced photo for each Mothbox device to a stable,
world-servable path, and writes a small mothboxes.json status file
describing every device (display name, latest-photo timestamp, and
computed schedule/outage status). Both are read by the 'livestream'
nginx container defined in docker-compose.yml, which serves them
alongside the static frontend in livestream/static/ (hand-written, not
generated here) and sits behind a CDN cache (e.g. Cloudflare) so public
viewers never hit this VM directly.
"""

import datetime
import json
import os
import shutil
import zoneinfo

from mothboxServerConfig import (
    NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH,
    LATEST_PHOTOS_DIRECTORY_PATH,
    LATEST_PHOTO_EXTENSIONS,
    LIVESTREAM_REFRESH_SECONDS,
    LIVESTREAM_ENABLED,
    LIVESTREAM_STALE_MINUTES,
    LIVESTREAM_BOOT_GRACE_MINUTES,
    MOTHBOX_ON_HOURS,
    CAMERA_TIMEZONE,
)

_TZ = zoneinfo.ZoneInfo(CAMERA_TIMEZONE)


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


def _find_newest_photo(mothbox: dict):
    """Return the path of a device's most recently synced photo, or None."""
    deployment_dir = os.path.join(NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH, mothbox["deploymentName"])
    daily_folder = _latest_daily_folder(deployment_dir)
    if daily_folder is None:
        return None
    return _newest_photo_in_folder(daily_folder)


def _parse_photo_timestamp(photo_path: str):
    """Extract the capture time embedded in a photo's filename.

    Filenames look like "fluidRobin_2026_06_26__20_49_06_HDR0.jpg" -- splitting
    the stem on "_" gives year/month/day at indices 1-3, an empty segment at
    index 4 (from the double underscore), and hour/minute/second at indices
    5-7. Same convention as photoprocessing/mark_raw_photos_for_deletion.py.
    Returns a CAMERA_TIMEZONE-aware datetime, or None if the filename doesn't
    match this pattern.
    """
    parts = os.path.splitext(os.path.basename(photo_path))[0].split('_')
    if len(parts) < 8:
        return None
    try:
        year, month, day = int(parts[1]), int(parts[2]), int(parts[3])
        hour, minute, second = int(parts[5]), int(parts[6]), int(parts[7])
        return datetime.datetime(year, month, day, hour, minute, second, tzinfo=_TZ)
    except ValueError:
        return None


def _expected_state(now_local: datetime.datetime) -> str:
    """Return "on" or "off" -- whether the Mothbox hardware is expected to be
    powered on right now, per MOTHBOX_ON_HOURS. Hours outside the nightly
    window are simply not in that set, so they naturally fall out as "off"
    too, with no separate case needed.
    """
    return "on" if now_local.hour in MOTHBOX_ON_HOURS else "off"


def _minutes_since_on_transition(now_local: datetime.datetime) -> float:
    """How many minutes since the current "on" run began.

    Walks back hour by hour while the preceding hour is also in
    MOTHBOX_ON_HOURS, so a schedule with back-to-back on-hours (e.g. a
    continuous overnight run rather than alternating) only counts the run's
    original start as a boot, not every hour boundary within it. Capped at
    24 steps in case a deployment's MOTHBOX_ON_HOURS never turns off.
    """
    hour_start = now_local.replace(minute=0, second=0, microsecond=0)
    for _ in range(24):
        if (hour_start - datetime.timedelta(hours=1)).hour not in MOTHBOX_ON_HOURS:
            break
        hour_start -= datetime.timedelta(hours=1)
    return (now_local - hour_start).total_seconds() / 60


def _next_on_time(now_local: datetime.datetime) -> datetime.datetime:
    """Return the next hour boundary (in CAMERA_TIMEZONE) at which the
    device is expected to be on, searching forward from now_local. Shown on
    the dashboard as "next scheduled on-time" while a device is off.
    """
    candidate = now_local.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
    for _ in range(24):
        if candidate.hour in MOTHBOX_ON_HOURS:
            return candidate
        candidate += datetime.timedelta(hours=1)
    return candidate


def _image_url(mothbox: dict, latest_dt):
    """Return the image URL for a device's latest photo, relative to the
    static frontend's docroot (nginx serves this directory under /data --
    see livestream/nginx.conf), cache-busted with the photo's own capture
    time so browsers/CDN only re-fetch when a genuinely new photo has
    arrived. None if no photo has been copied yet.
    """
    dest = os.path.join(LATEST_PHOTOS_DIRECTORY_PATH, f'{mothbox["mothboxName"]}.jpg')
    if latest_dt is None or not os.path.exists(dest):
        return None
    return f'data/{mothbox["mothboxName"]}.jpg?t={int(latest_dt.timestamp())}'


def _device_status(mothbox: dict, now_local: datetime.datetime) -> dict:
    """Compute the full status payload for one device, combining its latest
    photo's age with the expected on/off schedule state. A device that's
    expected to be off is never flagged as a problem, however stale its
    photo -- only a stale photo while expected ON indicates a possible
    power outage or technical problem, and even then only once it's had
    LIVESTREAM_BOOT_GRACE_MINUTES to boot and take its first photo of the
    new on-cycle (its last photo on file, from the previous cycle, is
    otherwise stale enough on its own to immediately look like an outage).
    """
    newest_path = _find_newest_photo(mothbox)
    latest_dt = _parse_photo_timestamp(newest_path) if newest_path else None
    expected_state = _expected_state(now_local)

    if latest_dt is None:
        status = "no-photo-yet"
        age_minutes = None
    else:
        age_minutes = (now_local - latest_dt).total_seconds() / 60
        if expected_state == "off":
            status = "expected-off"
        elif age_minutes <= LIVESTREAM_STALE_MINUTES:
            status = "ok"
        elif _minutes_since_on_transition(now_local) < LIVESTREAM_BOOT_GRACE_MINUTES:
            status = "starting-up"
        else:
            status = "possible-outage"

    return {
        "mothboxName": mothbox["mothboxName"],
        "friendlyName": mothbox.get("friendlyName") or mothbox["mothboxName"],
        "description": mothbox.get("description") or "",
        "imageUrl": _image_url(mothbox, latest_dt),
        "latestPhotoTimestamp": latest_dt.isoformat() if latest_dt else None,
        "expectedState": expected_state,
        "status": status,
        "ageMinutes": round(age_minutes, 1) if age_minutes is not None else None,
    }


def _write_json_atomic(data: dict):
    """Atomically write mothboxes.json so nginx never serves a half-written file."""
    os.makedirs(LATEST_PHOTOS_DIRECTORY_PATH, exist_ok=True)
    dest = os.path.join(LATEST_PHOTOS_DIRECTORY_PATH, "mothboxes.json")
    tmp_dest = dest + ".tmp"
    with open(tmp_dest, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_dest, dest)


def update_latest_photo(mothbox: dict):
    """Copy the most recently synced photo for one device to a stable public path."""
    if not LIVESTREAM_ENABLED:
        return

    newest_path = _find_newest_photo(mothbox)
    if newest_path is None:
        return

    os.makedirs(LATEST_PHOTOS_DIRECTORY_PATH, exist_ok=True)
    dest = os.path.join(LATEST_PHOTOS_DIRECTORY_PATH, f'{mothbox["mothboxName"]}.jpg')
    tmp_dest = dest + ".tmp"
    shutil.copyfile(newest_path, tmp_dest)
    os.replace(tmp_dest, dest)  # atomic rename avoids ever serving a half-written file


def generate_dashboard_data(mothboxes):
    """Write mothboxes.json, the sole dynamic input to the static livestream frontend.

    If LIVESTREAM_ENABLED is False, writes a minimal disabled payload instead,
    so a still-running nginx container doesn't keep serving whatever status
    happened to be generated last -- the static frontend renders its own
    "disabled" message when it sees enabled: false.
    """
    if not LIVESTREAM_ENABLED:
        print("LIVESTREAM_ENABLED is set to False, so writing a disabled notice instead of the dashboard.")
        _write_json_atomic({"enabled": False, "devices": []})
        return

    now_local = datetime.datetime.now(tz=_TZ)
    data = {
        "enabled": True,
        "generatedAt": now_local.isoformat(),
        "refreshSeconds": LIVESTREAM_REFRESH_SECONDS,
        "schedule": {
            "onHours": sorted(MOTHBOX_ON_HOURS),
            "timezone": CAMERA_TIMEZONE,
            "nextOnTime": _next_on_time(now_local).isoformat(),
        },
        "devices": [_device_status(mb, now_local) for mb in mothboxes],
    }
    _write_json_atomic(data)
