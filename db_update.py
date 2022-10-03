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
    print(bar_fill, end='\r')
    print(f'\rProgress: |{bar_fill}| {int(percent)}%\t', end='')

    if i == total:
        print()


def table_insert(cursor, connection, data):
    update = "INSERT OR REPLACE INTO file_mgr_item (name, path, type) VALUES (?,?,?)"
    cursor.execute(update, data)
    connection.commit()


def main():
    with open('config.txt', mode='r', encoding='utf8') as config:
        data_dir = json.load(config)['data_dir'] + '/'

    total = sum(len(files) + len(dirs) for _, dirs, files in os.walk(data_dir))
    count = 0
    print(total)

    connection = sqlite3.connect('db.sqlite3')
    cursor = connection.cursor()

    for root, _, files in os.walk(data_dir):
        root = root.replace(data_dir, '')

        dir_name = root.split('/')[-1]
        dir_root = '/'.join(root.split('/')[:-1])

        if not root:
            root = None

        if not dir_root:
            dir_root = None

        if dir_name:
            dir_data = (dir_name, dir_root, 'dir')
            table_insert(cursor, connection, dir_data)
            count += 1

        for file in files:
            file_data = (file, root, 'file')
            table_insert(cursor, connection, file_data)
            count += 1
            progress_bar(count, total)

    cursor.close()


if __name__ == '__main__':
    main()
