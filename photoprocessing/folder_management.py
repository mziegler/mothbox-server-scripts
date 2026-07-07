"""
Some utility functions to move around folders to keep track of images we are processing.
"""


import os
import shutil
import subprocess

from mothboxServerConfig import NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH, PROCESSED_PHOTOS_DIRECTORY_PATH, IN_PROGRESS_PHOTOS_DIRECTORY_PATH


def _merge_directories(src: str, dst: str):
    """Recursively move all contents of src into dst, merging subdirectories.

    Unlike shutil.move, this handles the case where a subdirectory with the
    same name already exists in dst (e.g. _processed/) by recursing into it
    rather than trying to nest src inside dst.
    """
    os.makedirs(dst, exist_ok=True)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            _merge_directories(s, d)
            os.rmdir(s)   # remove now-empty source subdirectory
        else:
            shutil.move(s, d)


inprogress_directory = os.path.expanduser(IN_PROGRESS_PHOTOS_DIRECTORY_PATH)
unprocessed_directory = os.path.expanduser(NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH)
completed_directory = os.path.expanduser(PROCESSED_PHOTOS_DIRECTORY_PATH)




def get_inprogress_daily_folders():
    """Check if there are any folders in the in-progress directory. Ideally, there should only be one or zero.
    The main purpose of this is because we expect frequent power outages; so we want to keep track of which 
    daily folder we are processing when the power goes out, so we only have to repeat one.
    """

    # First, recursively delete any empty folders in the in-progress directory.
    delete_empty_inprogress_folders()

    daily_folders = []
    for deployment_folder in os.listdir(inprogress_directory):
        deployment_folder_path = os.path.join(inprogress_directory, deployment_folder)
        if os.path.isdir(deployment_folder_path):
            for daily_folder in os.listdir(deployment_folder_path):
                daily_folder_path = os.path.join(deployment_folder_path, daily_folder)
                if os.path.isdir(daily_folder_path):
                    daily_folders.append(daily_folder_path)
    return daily_folders


def get_unprocessed_daily_folders():
    """Return a list of daily folders in the unprocessed directory."""

    # First, recursively delete any empty folders in the unprocessed directory.
    delete_empty_unprocessed_folders()

    daily_folders = []
    for deployment_folder in os.listdir(unprocessed_directory):
        deployment_folder_path = os.path.join(unprocessed_directory, deployment_folder)
        if os.path.isdir(deployment_folder_path):
            for daily_folder in os.listdir(deployment_folder_path):
                daily_folder_path = os.path.join(deployment_folder_path, daily_folder)
                if os.path.isdir(daily_folder_path):
                    daily_folders.append(daily_folder_path)
    return daily_folders


def delete_empty_folders(folder_path=unprocessed_directory):
    """Recursively delete empty folders under folder_path (but not folder_path itself)."""
    if not os.path.isdir(folder_path):
        return
    subprocess.run(["rclone", "rmdirs", folder_path, "--leave-root"], check=True)


def delete_empty_unprocessed_folders():
    """
    Delete empty folders in the unprocessed directory.

    This is useful because:
    1) We might leave behind some empty deployment folders when moving
    around the daily folders.
    2) Rsync might leave some empty folders behind on the Mothboxes.

    """
    delete_empty_folders(unprocessed_directory)


def delete_empty_inprogress_folders():
    """Delete empty folders in the in-progress directory.
    
    This is useful because: We might leave behind some empty deployment folders when moving
    around the daily folders.
    """
    delete_empty_folders(inprogress_directory)


def move_daily_folder_to_inprogress(daily_folder_path):
    """Move a daily folder from the unprocessed directory to the in-progress directory. 
    
    This is used to keep track of which daily folder we are currently processing, so that if there is a power outage, we can resume processing that folder without having to repeat any already-processed folders.
    
    Returns the new path of the folder in the in-progress directory.
    """
    if not os.path.isdir(daily_folder_path):
        raise ValueError(f"{daily_folder_path} is not a valid directory.")
    deployment_name = os.path.basename(os.path.dirname(daily_folder_path))
    daily_folder_name = os.path.basename(daily_folder_path)

    # Rename the daily folder name so they fit the format required by the Mothbox
    # data processing scripts, instead of folder names format copied directly from the Mothboxes.
    # For example, rename "agileCigua_2026-04-02" to just "2026-04-02".
    if '_' in daily_folder_name:
        daily_folder_name=daily_folder_name.split('_')[-1]

    new_daily_folder_path = os.path.join(inprogress_directory, deployment_name, daily_folder_name)
    os.makedirs(os.path.dirname(new_daily_folder_path), exist_ok=True)
    os.rename(daily_folder_path, new_daily_folder_path)
    return new_daily_folder_path


def move_daily_folder_to_completed(daily_folder_path):
    """Move a daily folder from the unprocessed directory to the completed directory. 
    This is used to keep track of which daily folder we have completed processing.
    
    If there is already a folder for this date/deployment in the completed directory,
    the folders will be merged.
    -- In this case, this function returns the folder path of the merged folder
       so we can re-run the perceptual clustering step.
    -- (Otherwise, return false)
    """
    if not os.path.isdir(daily_folder_path):
        raise ValueError(f"{daily_folder_path} is not a valid directory.")
    deployment_name = os.path.basename(os.path.dirname(daily_folder_path))
    daily_folder_name = os.path.basename(daily_folder_path)

    new_daily_folder_path = os.path.join(completed_directory, deployment_name, daily_folder_name)
    if os.path.exists(new_daily_folder_path):
        _merge_directories(daily_folder_path, new_daily_folder_path)
        print("Folders were merged.")

        # Return the path of the merged folder, so we can re-run the perceptual clustering step.
        return new_daily_folder_path

    else:
        os.makedirs(os.path.dirname(new_daily_folder_path), exist_ok=True)
        os.rename(daily_folder_path, new_daily_folder_path)
    return False


