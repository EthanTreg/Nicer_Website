import sqlite3
import os

for root, _, files in os.walk('./data'):
    for file in files:
        connection = sqlite3.connect('db.sqlite3')
        cursor = connection.cursor()
        update = f"INSERT INTO Item (name, path, type) VALUES ({file}, {root}, 'File')"
