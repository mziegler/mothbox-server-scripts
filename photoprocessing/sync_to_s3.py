"""
Upload completed daily folders to Hetzner Object Storage and remove
MARKED-FOR-DELETION files from local disk (without uploading them to S3).

Requires rclone to be configured on the host with a remote named
S3_REMOTE (default: "hetzner-s3") pointing at the Hetzner S3 endpoint.
"""

import subprocess
from pathlib import Path
from os.path import expanduser

from mothboxServerConfig import (
    S3_REMOTE,
    S3_BUCKET,
    S3_KEY_PREFIX,
    PROCESSED_PHOTOS_DIRECTORY_PATH,
    IN_PROGRESS_PHOTOS_DIRECTORY_PATH,
)


def sync_and_cleanup():
    """Sync the whole processed-photos root to S3, excluding MARKED-FOR-DELETION files.

    Moves the entire PROCESSED_PHOTOS_DIRECTORY_PATH tree on every call, not
    just the daily folder that just finished. rclone move only deletes local
    files it successfully uploads, so any folder left behind by a previous
    failed sync (a stale AccessDenied, a network blip, S3 downtime) is still
    sitting on local disk and gets swept up and retried automatically here —
    no separate backlog-scanning code needed. Safe to call this often: folders
    that already fully synced are simply absent locally, so there's nothing
    left for rclone to do for them.

    Does not raise on an rclone failure — logs a warning and returns instead,
    leaving whatever didn't upload in place for the next call to retry. This
    function runs inline in the pipeline daemon's main loop (see
    pipeline_schedule_manager.py); raising here would previously crash the
    whole daemon on any transient sync failure, silently abandoning whatever
    folder was in flight and everything queued behind it.
    """
    base = Path(expanduser(PROCESSED_PHOTOS_DIRECTORY_PATH))

    # Prepend optional key prefix to place objects under a specific directory
    prefix = (S3_KEY_PREFIX or "").strip("/")
    remote = f"{S3_REMOTE}:{S3_BUCKET}/{prefix}" if prefix else f"{S3_REMOTE}:{S3_BUCKET}"

    print(f"Syncing {base} → {remote} (excluding MARKED-FOR-DELETION files)")
    result = subprocess.run(
        [
            "rclone", "move", str(base), remote,
            "--exclude", "MARKED-FOR-DELETION.*",
            "--transfers", "8",
        ],
    )
    if result.returncode != 0:
        print(
            f"WARNING: rclone move to S3 failed (exit {result.returncode}). "
            f"Unsynced folders remain under {base} and will be retried on the next sync."
        )
        return

    # Delete MARKED-FOR-DELETION files locally — they were never sent to S3.
    # Safe regardless of the move's outcome above: these are excluded from
    # every sync attempt, so they're unrelated to whatever did or didn't upload.
    for f in base.rglob("MARKED-FOR-DELETION.*"):
        f.unlink()

    # Remove any empty directories left behind under the whole processed root.
    # rclone move removes files but leaves empty directory skeletons; this cleans them up.
    subprocess.run(
        ["rclone", "rmdirs", str(base)],
        check=True,
    )

    print("Sync and cleanup complete")


def move_folder_to_crash_holding(in_progress_folder: str):
    """Move a crashed in-progress folder to S3 holding-crashing/ for later retry.

    Uses rclone move so local files are deleted only after confirmed upload.
    If the upload fails, the folder remains on local disk for manual inspection.
    """
    path = Path(in_progress_folder)
    rel = path.relative_to(Path(expanduser(IN_PROGRESS_PHOTOS_DIRECTORY_PATH)))
    remote = f"{S3_REMOTE}:{S3_BUCKET}/holding-crashing/{rel}"

    print(f"Moving crashed folder {path} → {remote}")
    result = subprocess.run(
        ["rclone", "move", str(path), remote, "--transfers", "8"],
    )
    if result.returncode == 0:
        # Remove any empty parent deployment directory left behind
        try:
            path.parent.rmdir()
        except OSError:
            pass
        print(f"Crashed folder moved to holding-crashing: {rel}")
    else:
        print(
            f"WARNING: rclone move to holding-crashing failed (exit {result.returncode}). "
            f"Folder remains at {path} for manual inspection."
        )
