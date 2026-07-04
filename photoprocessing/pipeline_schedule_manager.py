import os
import socket
import sys
import time
from pathlib import Path

import photoprocessing.folder_management as fm
from mothboxServerConfig import PROCESSED_PHOTOS_DIRECTORY_PATH, PIPELINE_IDLE_SLEEP_SECONDS
from photoprocessing.run_AI_pipeline import run_full_AI_pipeline, run_cluster, PipelineCrashError
from photoprocessing.sync_to_s3 import sync_and_cleanup, move_folder_to_crash_holding


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


def _completed_path_for(in_progress_folder: str) -> Path:
    """Compute the completed-directory path for an in-progress folder without moving it."""
    path = Path(in_progress_folder)
    deployment_name = path.parent.name
    daily_name = path.name
    return Path(os.path.expanduser(PROCESSED_PHOTOS_DIRECTORY_PATH)) / deployment_name / daily_name


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
            completed_path = _completed_path_for(daily_folder)
            fm.move_daily_folder_to_completed(daily_folder)
            sync_and_cleanup(str(completed_path))
        except PipelineCrashError as e:
            print(f"Pipeline crashed on {daily_folder}: {e}", flush=True)
            move_folder_to_crash_holding(daily_folder)
        processed_any = True

    # Process new unprocessed folders.
    for daily_folder in fm.get_unprocessed_daily_folders():
        print(f"Starting pipeline for new unprocessed folder: {daily_folder}", flush=True)
        daily_folder = fm.move_daily_folder_to_inprogress(daily_folder)
        try:
            run_full_AI_pipeline(daily_folder, overwrite_bot=False)
            completed_path = _completed_path_for(daily_folder)
            merged_folder = fm.move_daily_folder_to_completed(daily_folder)
            if merged_folder:
                print(f"Re-running perceptual clustering for merged folder: {merged_folder}", flush=True)
                try:
                    run_cluster(merged_folder)
                except PipelineCrashError as e:
                    print(f"Warning: re-clustering crashed for merged folder {merged_folder}: {e}", flush=True)
            sync_and_cleanup(str(merged_folder or completed_path))
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
