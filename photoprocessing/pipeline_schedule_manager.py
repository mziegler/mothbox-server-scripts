import os
import socket
import sys

import photoprocessing.folder_management as fm
from crontab import CronTab
from photoprocessing.run_AI_pipeline import run_full_AI_pipeline, run_cluster





def ensure_single_instance(port=48283):
    """
    Check to make sure that only one instance of this script is running.

    To do this, we will try to bind a socket to a specific port. If we succeed, we will keep 
    the socket open for the duration of the script. If we fail, we will assume that another 
    instance of the script is already running and exit.
    
    Port 48283 chosen arbitrarily, hopefully unlikely to conflict with other programs.
    """

    # Create a global variable to keep the socket alive for the script's duration
    global _lock_socket 
    _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _lock_socket.bind(('127.0.0.1', port))
    except socket.error:
        print("Another instance is already running. Exiting.")
        sys.exit(1)



def start_or_resume_pipeline():
    """Check if there are any in-progress folders. If so, resume processing the first one. If not, start processing the first unprocessed folder."""


    ensure_single_instance()


    # Check to see if there are any folders marked as in-progress. 
    # If so, run these first.
    inprogress_daily_folders = fm.get_inprogress_daily_folders()
    if inprogress_daily_folders:
        for daily_folder in inprogress_daily_folders:
            print(f"Resuming pipeline for in-progress folder: {daily_folder}")
            run_full_AI_pipeline(daily_folder, overwrite_bot=False)
            fm.move_daily_folder_to_completed(daily_folder)


    unprocessed_daily_folders = fm.get_unprocessed_daily_folders()
    for daily_folder in unprocessed_daily_folders:
        print(f"Starting pipeline for new unprocessed folder: {daily_folder}")
        daily_folder = fm.move_daily_folder_to_inprogress(daily_folder)
        run_full_AI_pipeline(daily_folder, overwrite_bot=False)

        merged_folder = fm.move_daily_folder_to_completed(daily_folder)
        if merged_folder:
            print(f"Re-running perceptual clustering for merged folder: {merged_folder}")
            run_cluster(merged_folder)

    else:
        print("No folders to process.")






if __name__ == "__main__":
    start_or_resume_pipeline()



#########################################################33
# Cron stuff



# run: once each morning, and upon system restart
CRON_COMMENT_PREFIX = "Mothbox-AI-Pipeline"


def _build_pipeline_command():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    python_executable = sys.executable
    current_file = os.path.abspath(__file__)
    rel_path = os.path.relpath(current_file, parent_dir)
    module_name = rel_path.replace(os.sep, '.').rstrip('.py')
    return f'cd {parent_dir} && {python_executable} -m {module_name}'


def schedule_pipeline_jobs():
    cron = CronTab(user=True)
    remove_pipeline_jobs(cron=cron, write=False)

    command = _build_pipeline_command()

    daily_job = cron.new(
        command=command,
        comment=f"{CRON_COMMENT_PREFIX}-daily",
    )
    daily_job.minute.on(0)
    daily_job.hour.on(6)

    reboot_job = cron.new(
        command=command,
        comment=f"{CRON_COMMENT_PREFIX}-reboot",
    )
    reboot_job.every_reboot()

    cron.write()


def remove_pipeline_jobs(cron=None, write=True):
    cron = cron or CronTab(user=True)

    for job in cron:
        if job.comment.startswith(CRON_COMMENT_PREFIX):
            cron.remove(job)

    if write:
        cron.write()