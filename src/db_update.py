"""
Updates the database using Sqlite to match the folder
structure of the specified directory found in config.txt
"""
import os
import json
import sqlite3
import subprocess

import numpy as np


def progress_bar(i: int, total: int):
    """
    Terminal progress bar

    Parameters
    ----------
    i : int
        Current progress
    total : int
        Completion number
    """
    length = 50
    i += 1

    filled = int(i * length / total)
    percent = i * 100 / total
    bar_fill = '█' * filled + '-' * (length - filled)
    print(f'\rProgress: |{bar_fill}| {int(percent)}%\t', end='')

    if i == total:
        print()


def table_insert(data: list[tuple[str, str, str]], batch_size: int = 50):
    """
    Add folder and file data to the database

    Parameters
    ----------
    data : list[tuple[string, string, string]]
        Data to be inserted into the database
    batch_size : integer, default = 50
        How many entries to insert into the database per execution
    """
    update = 'INSERT OR REPLACE INTO file_mgr_item (name, path, type) VALUES (?,?,?)'
    batches = np.array_split(data, len(data) / batch_size)

    # Connect to the database
    with sqlite3.connect('db.sqlite3') as conn:
        # Insert data into the database
        for i, batch in enumerate(batches):
            conn.executemany(update, list(batch))
            progress_bar(i, len(batches))


def linux_count(directory: str) -> int:
    """
    Count the number of files and folders in the given directory using Linux command line

    Parameters
    ----------
    directory : string
        Directory to count files and folders

    Returns
    -------
    integer
        Number of files and folders in the given directory
    """
    process_output = subprocess.run(
            ['find', directory, '-printf', '.'],
            capture_output=True,
            check=True,
    )
    process_output = subprocess.run(
        ['wc', '-c'],
        input=process_output.stdout,
        capture_output=True,
        check=True,
    ).stdout

    return int(process_output.decode('utf-8').strip())


def universal_count(directory: str) -> int:
    """
    Count the number of files and folders in the given directory using Python for compatibility

    Parameters
    ----------
    directory : string
        Directory to count files and folders

    Returns
    -------
    integer
        Number of files and folders in the given directory
    """
    count = 0

    for _, dirs, files in os.walk(directory):
        count += len(files) + len(dirs)
        print(f'\rCount: {count}', end='')

    print()
    return count


def main():
    """
    Main function for updating the database
    """
    count = 0
    data = []

    # Get data directory location from config.txt
    with open('config.txt', mode='r', encoding='utf-8') as config:
        data_dir = '../' + json.load(config)['data_dir']

    # Calculate the total number of folders and files
    try:
        total = linux_count(data_dir)
    except (subprocess.CalledProcessError, FileNotFoundError):
        total = universal_count(data_dir)

    print(f'Total number of files and folders: {total}')

    # Loop through each folder and file in the data directory
    for root, _, files in os.walk(data_dir):
        root = root.replace(data_dir, '')

        dir_name = root.split('/')[-1]
        parent_dir = '/'.join(root.split('/')[:-1]) + '/'
        root += '/'

        if files:
            total -= np.count_nonzero(np.char.find(files, '.arf') != -1)
            total -= np.count_nonzero(np.char.find(files, '.rmf') != -1)
            files = np.delete(np.array(files), np.char.find(files, '.arf') != -1)
            files = np.delete(np.array(files), np.char.find(files, '.rmf') != -1)

        # If not top level directory, add folder to the database
        if dir_name:
            data.append((dir_name, parent_dir, 'dir'))
            count += 1
            progress_bar(count, total)

        # Add file to the database
        for file in files:
            data.append((file, root, 'file'))
            count += 1
            progress_bar(count, total)

    # Insert data into database
    table_insert(data)


if __name__ == '__main__':
    main()
