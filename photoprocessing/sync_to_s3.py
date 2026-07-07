"""
Upload a completed daily folder to Hetzner Object Storage and remove
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


def sync_and_cleanup(completed_folder_path: str):
    """Move a processed daily folder to S3, excluding MARKED-FOR-DELETION files.

    - rclone move transfers kept files to S3 and removes them from local disk.
    - MARKED-FOR-DELETION files are excluded from the move, then deleted locally.
      They are never uploaded to S3 (important when versioning is enabled on the bucket).
    """
    path = Path(completed_folder_path)
    base = Path(expanduser(PROCESSED_PHOTOS_DIRECTORY_PATH))
    rel = path.relative_to(base)
    
    # Prepend optional key prefix to place objects under a specific directory
    prefix = (S3_KEY_PREFIX or "").strip("/")
    if prefix:
        remote = f"{S3_REMOTE}:{S3_BUCKET}/{prefix}/{rel}"
    else:
        remote = f"{S3_REMOTE}:{S3_BUCKET}/{rel}"

    print(f"Moving {path} → {remote} (excluding MARKED-FOR-DELETION files)")
    subprocess.run(
        [
            "rclone", "move", str(path), remote,
            "--exclude", "MARKED-FOR-DELETION.*",
            "--transfers", "8",
        ],
        check=True,
    )

    # Delete MARKED-FOR-DELETION files locally — they were never sent to S3
    for f in path.rglob("MARKED-FOR-DELETION.*"):
        f.unlink()

    # Remove any empty directories left behind under the whole processed root.
    # rclone move removes files but leaves empty directory skeletons; this cleans them up.
    subprocess.run(
        ["rclone", "rmdirs", str(base)],
        check=True,
    )

    print(f"Sync and cleanup complete for {path.name}")


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
