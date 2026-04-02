import csv
from crontab import CronTab
from mothboxServerConfig import NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH, RSYNC_LOG_PATH
import os

expandedPhotosPath = os.path.expanduser(NEW_UNPROCESSED_PHOTOS_DIRECTORY_PATH)
expandedLogPath = os.path.expanduser(RSYNC_LOG_PATH)

"""Load a CSV file containing mothbox information. Returns a list with one dict for each 
mothbox; having the keys "deploymentName", "mothboxName" and "hostOrIP."
"""
def load_mothbox_list(filename='mothbox-list.csv'):
    with open(filename) as csvfile:
        reader = csv.DictReader(csvfile)
        return [row for row in reader]


def schedule_frequent_photo_sync_jobs(startHour, endHour):
    # Load the list of mothboxes from the CSV file
    mothboxes = load_mothbox_list()

    # Create a new cron object for the current user
    cron = CronTab(user=True)

    for h in range(startHour, endHour if endHour > startHour else endHour + 24):
        hour = h % 24

    # Loop through each mothbox and create a cron job for it
    for mothbox in mothboxes:

        # Loop through each hour in the specified range; some trick to account for midnight since this is nightly
        hour_list = [h%24 for h in range(startHour, endHour if endHour > startHour else endHour + 24)]

        job = cron.new(
            command=f'rsync -rv --times --remove-source-files --mkpath {mothbox["hostOrIP"]}:/home/pi/Desktop/Mothbox/photos/* {os.path.join(expandedPhotosPath, mothbox["deploymentName"])}/ >> {expandedLogPath} 2>&1',
            comment=f'Generated-Mothbox-Rsync job for {mothbox["mothboxName"]}')
        job.hour.on(*hour_list)  # Schedule the job to run at the specified hour
        job.minute.every(1)  # Schedule the job to run every minute within the hour

        print(job)  # Print the job for debugging purposes

    # Write the cron jobs to the crontab
    cron.write()    

def remove_generated_jobs():
    # Create a new cron object for the current user
    cron = CronTab(user=True)

    # Find and remove all jobs with comments starting with "Generated-Mothbox-Rsync"
    for job in cron:
        if job.comment.startswith("Generated-Mothbox-Rsync"):
            cron.remove(job)

    # Write the updated crontab
    cron.write()


if __name__ == "__main__":
    remove_generated_jobs()
    schedule_frequent_photo_sync_jobs(18,6)


# TODO
# one option for removing empty directories: find . -type d -empty -delete
# do a separate log for each Mothbox. Maybe a separate log for each date, also?