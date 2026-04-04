import os
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from mothboxServerConfig import MARK_RAW_PHOTOS_FOR_DELETION, KEEP_ONE_OUT_OF_EVERY_N_PHOTOS, MATCHING_SUFFIXES_FOR_DELETION



def mark_raw_photos_for_deletion(daily_folder):
    """
    Mark raw photos for deletion by renaming them with a prefix: "MARKED-FOR-DELETION."

    Load settings from mothboxServerConfig to decide how many to keep.
    """


    if not MARK_RAW_PHOTOS_FOR_DELETION:
        print("MARK_RAW_PHOTOS_FOR_DELETION is set to False, so skipping marking photos for deletion.")
        return

    print(f"Marking {KEEP_ONE_OUT_OF_EVERY_N_PHOTOS-1} out of every {KEEP_ONE_OUT_OF_EVERY_N_PHOTOS} photos for deletion in daily folder: {daily_folder}")

    folder = Path(daily_folder)
    photos = []
    
    # Collect and parse photos
    for file in folder.iterdir():
        if file.is_file() and file.suffix.lower() in MATCHING_SUFFIXES_FOR_DELETION:
            name = file.stem
            parts = name.split('_')
            if len(parts) >= 8:
                try:
                    year = int(parts[1])
                    month = int(parts[2])
                    day = int(parts[3])
                    hour = int(parts[5])
                    minute = int(parts[6])
                    second = int(parts[7])
                    dt = datetime(year, month, day, hour, minute, second)
                    photos.append((dt, file))
                except ValueError:
                    pass  # Skip files with invalid timestamps
    
    # Sort photos by timestamp
    photos.sort(key=lambda x: x[0])
    
    # Group by hour
    groups = defaultdict(list)
    for dt, file in photos:
        key = dt.strftime('%Y-%m-%d-%H')
        groups[key].append((dt, file))
    
    # Process each hour group
    for key, group in groups.items():
        # Sort group by timestamp descending (most recent first)
        group.sort(key=lambda x: x[0], reverse=True)
        for i, (dt, file) in enumerate(group):
            if i % KEEP_ONE_OUT_OF_EVERY_N_PHOTOS != 0:
                # Mark for deletion by renaming

                # is it arleady marked for deletion? If not, rename it.
                if not file.name.startswith("MARKED-FOR-DELETION."):
                    new_name = "MARKED-FOR-DELETION." + file.name
                    file.rename(file.with_name(new_name))


def clear_prefixes(daily_folder):
    """Utility function to clear the "MARKED-FOR-DELETION." prefix from all files in the daily folder."""
    folder = Path(daily_folder)
    for file in folder.iterdir():
        if file.is_file() and file.name.startswith("MARKED-FOR-DELETION."):
            new_name = file.name[len("MARKED-FOR-DELETION."):]
            file.rename(file.with_name(new_name))