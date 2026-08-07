import datetime
import socket
import sys
import time
import zoneinfo
from pathlib import Path

import photoprocessing.folder_management as fm
from mothboxServerConfig import (
    PIPELINE_IDLE_SLEEP_SECONDS,
    CAMERA_TIMEZONE,
    COLLECTION_END_HOUR,
    FOLDER_MIN_IDLE_MINUTES,
)
from photoprocessing.run_AI_pipeline import run_full_AI_pipeline, run_cluster, PipelineCrashError
from photoprocessing.sync_to_s3 import sync_and_cleanup, move_folder_to_crash_holding

_TZ = zoneinfo.ZoneInfo(CAMERA_TIMEZONE)


def ensure_single_instance(port=48283):
    """Prevent more than one pipeline daemon from running at the same time.

    Binds a socket to a loopback port for the lifetime of the process.
    Port 48283 chosen arbitrarily.
    """
    global _lock_socket
    _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _lock_socket.bind(('127.0.0.1', port))
    except socket.error:
        print("Another instance is already running. Exiting.")
        sys.exit(1)


def _folder_is_ready_to_process(unprocessed_folder: str) -> bool:
    """Return True if the Mothbox has finished running for this folder's night.

    Folder names are like "fluidRobin_2026-06-13", where the date is when the
    collection STARTED (evening of June 13).  Because the Mothbox runs overnight
    and turns off at COLLECTION_END_HOUR the following morning, this folder must
    not be processed until COLLECTION_END_HOUR on June 14.

    If the date cannot be parsed from the folder name, processing is allowed
    immediately (fail-open).
    """
    folder_name = Path(unprocessed_folder).name
    date_str = folder_name.split("_")[-1]  # e.g. "2026-06-13"
    try:
        start_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return True  # unparseable name — don't block

    # Collection ends at COLLECTION_END_HOUR on the day after it started.
    end_day = start_date + datetime.timedelta(days=1)
    ready_at = datetime.datetime(
        end_day.year, end_day.month, end_day.day,
        COLLECTION_END_HOUR, 0, 0,
        tzinfo=_TZ,
    )
    if datetime.datetime.now(tz=_TZ) < ready_at:
        return False

    # Guard against the race condition where the pipeline moves a folder while
    # the photo-pull daemon is actively writing to it.  The folder's mtime is
    # bumped every time it deposits a file; requiring a minimum idle period
    # ensures we only process folders that the photo-pull daemon has finished
    # with.
    folder_mtime = Path(unprocessed_folder).stat().st_mtime
    idle_seconds = time.time() - folder_mtime
    if idle_seconds < FOLDER_MIN_IDLE_MINUTES * 60:
        print(
            f"  {Path(unprocessed_folder).name} was last modified "
            f"{idle_seconds / 60:.1f} min ago — waiting for photo-pull to finish.",
            flush=True,
        )
        return False

    return True


def _process_pending_folders() -> bool:
    """Process all in-progress and unprocessed folders.

    Returns True if at least one folder was processed so the daemon can
    immediately check again rather than sleeping.
    """
    processed_any = False

    # Resume in-progress folders first (crash / power-outage recovery).
    for daily_folder in fm.get_inprogress_daily_folders():
        print(f"Resuming pipeline for in-progress folder: {daily_folder}", flush=True)
        try:
            run_full_AI_pipeline(daily_folder, overwrite_bot=False)
            fm.move_daily_folder_to_completed(daily_folder)
            sync_and_cleanup()
        except PipelineCrashError as e:
            print(f"Pipeline crashed on {daily_folder}: {e}", flush=True)
            move_folder_to_crash_holding(daily_folder)
        processed_any = True

    # Process new unprocessed folders.
    for daily_folder in fm.get_unprocessed_daily_folders():
        if not _folder_is_ready_to_process(daily_folder):
            print(
                f"Skipping {Path(daily_folder).name} — Mothbox still running for the night.",
                flush=True,
            )
            continue
        print(f"Starting pipeline for new unprocessed folder: {daily_folder}", flush=True)
        daily_folder = fm.move_daily_folder_to_inprogress(daily_folder)
        try:
            run_full_AI_pipeline(daily_folder, overwrite_bot=False)
            merged_folder = fm.move_daily_folder_to_completed(daily_folder)
            if merged_folder:
                print(f"Re-running perceptual clustering for merged folder: {merged_folder}", flush=True)
                try:
                    run_cluster(merged_folder)
                except PipelineCrashError as e:
                    print(f"Warning: re-clustering crashed for merged folder {merged_folder}: {e}", flush=True)
            sync_and_cleanup()
        except PipelineCrashError as e:
            print(f"Pipeline crashed on {daily_folder}: {e}", flush=True)
            move_folder_to_crash_holding(daily_folder)
        processed_any = True

    return processed_any


def run_pipeline_daemon():
    """Run the pipeline continuously as a long-running daemon.

    Processes all pending folders on each iteration.  When the queue is empty,
    sleeps for PIPELINE_IDLE_SLEEP_SECONDS before checking again.  When work is
    found, loops immediately so backlogs drain as fast as possible.
    """
    ensure_single_instance()
    print("Pipeline daemon started.", flush=True)
    while True:
        processed = _process_pending_folders()
        if not processed:
            print(
                f"No folders to process. Sleeping {PIPELINE_IDLE_SLEEP_SECONDS // 60} min.",
                flush=True,
            )
            time.sleep(PIPELINE_IDLE_SLEEP_SECONDS)


if __name__ == "__main__":
    run_pipeline_daemon()
