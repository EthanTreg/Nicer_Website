import os
import json
import sqlite3


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


def table_insert(data: list[tuple[str, str, str]]):
    """
    Add folder and file data to the database

    Parameters
    ----------
    data : list[tuple[string, string, string]]
        Data to be inserted into the database
    """
    # Connect to the database
    connection = sqlite3.connect('db.sqlite3')
    cursor = connection.cursor()

    # Insert data into the database
    update = "INSERT OR REPLACE INTO file_mgr_item (name, path, type) VALUES (?,?,?)"
    cursor.executemany(update, data)

    # Commit changes & close the connection
    connection.commit()
    cursor.close()


def main():
    """
    Main function for updating the database
    """
    count = 0
    data = []

    # Get data directory location from config.txt
    with open('config.txt', mode='r', encoding='utf-8') as config:
        data_dir = json.load(config)['data_dir']

    # Calculate the total number of folders and files
    total = sum(len(files) + len(dirs) for _, dirs, files in os.walk(data_dir))
    print(f'Total number of files and folders: {total}')

    # Loop through each folder and file in the data directory
    for root, _, files in os.walk(data_dir):
        root = root.replace(data_dir, '')

        dir_name = root.split('/')[-1]
        dir_root = '/'.join(root.split('/')[:-1])

        # If top level directory
        if not root:
            root = None
        else:
            root += '/'

        # If parent directory is top level directory
        if not dir_root:
            dir_root = None
        else:
            dir_root += '/'

        # If not top level directory, add each folder to the database
        if dir_name:
            data.append((dir_name, dir_root, 'dir'))
            # table_insert(cursor, connection, dir_data)
            count += 1
            progress_bar(count, total)

        # Add each file to the database
        for file in files:
            data.append((file, root, 'file'))
            count += 1
            progress_bar(count, total)

    # Insert data into database
    table_insert(data)


if __name__ == '__main__':
    main()
