"""
Some utility functions to move around folders to keep track of images we are processing.
"""


import os


from mothboxServerConfig import NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH, PROCESSED_PHOTOS_DIRECTORY_PATH, IN_PROGRESS_PHOTOS_DIRECTORY_PATH

inprogress_directory = os.path.expanduser(IN_PROGRESS_PHOTOS_DIRECTORY_PATH)
unprocessed_directory = os.path.expanduser(NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH)
completed_directory = os.path.expanduser(PROCESSED_PHOTOS_DIRECTORY_PATH)




def get_inprogress_daily_folders():
    """Check if there are any folders in the in-progress directory. Ideally, there should only be one or zero.
    The main purpose of this is because we expect frequent power outages; so we want to keep track of which 
    daily folder we are processing when the power goes out, so we only have to repeat one.
    """

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
    daily_folders = []
    for deployment_folder in os.listdir(unprocessed_directory):
        deployment_folder_path = os.path.join(unprocessed_directory, deployment_folder)
        if os.path.isdir(deployment_folder_path):
            for daily_folder in os.listdir(deployment_folder_path):
                daily_folder_path = os.path.join(deployment_folder_path, daily_folder)
                if os.path.isdir(daily_folder_path):
                    daily_folders.append(daily_folder_path)
    return daily_folders


def delete_empty_folders(folder_path):
    """Recursively delete empty folders under folder_path (including folder_path if it becomes empty)."""
    if not os.path.isdir(folder_path):
        return False
    for name in os.listdir(folder_path):
        child_path = os.path.join(folder_path, name)
        if os.path.isdir(child_path):
            delete_empty_folders(child_path)
    if not os.listdir(folder_path):
        os.rmdir(folder_path)
        return True
    return False


def move_daily_folder_to_inprogress(daily_folder_path):
    """Move a daily folder from the unprocessed directory to the in-progress directory. This is used to keep track of which daily folder we are currently processing, so that if there is a power outage, we can resume processing that folder without having to repeat any already-processed folders."""
    if not os.path.isdir(daily_folder_path):
        raise ValueError(f"{daily_folder_path} is not a valid directory.")
    deployment_name = os.path.basename(os.path.dirname(daily_folder_path))
    daily_folder_name = os.path.basename(daily_folder_path)

    # Rename the daily folder name so they fit the format required by the Mothbox
    # data processing scripts, instead of folder names format copied directly from the Mothboxes.
    # For example, rename "agileCigua_2026-04-02" to just "2026-04-02".
    if daily_folder_name.contains('_'):
        daily_folder_name=daily_folder_name.split('_')[-1]

    new_daily_folder_path = os.path.join(inprogress_directory, deployment_name, daily_folder_name)
    os.makedirs(os.path.dirname(new_daily_folder_path), exist_ok=True)
    os.rename(daily_folder_path, new_daily_folder_path)
    return new_daily_folder_path


def move_daily_folder_to_completed(daily_folder_path):
    """Move a daily folder from the unprocessed directory to the completed directory. This is used to keep track of which daily folder we have completed processing."""
    if not os.path.isdir(daily_folder_path):
        raise ValueError(f"{daily_folder_path} is not a valid directory.")
    deployment_name = os.path.basename(os.path.dirname(daily_folder_path))
    daily_folder_name = os.path.basename(daily_folder_path)

    new_daily_folder_path = os.path.join(completed_directory, deployment_name, daily_folder_name)
    os.makedirs(os.path.dirname(new_daily_folder_path), exist_ok=True)
    os.rename(daily_folder_path, new_daily_folder_path)
    return new_daily_folder_path