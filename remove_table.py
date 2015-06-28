#!/usr/bin/env python
# -*- coding: utf-8 -*-

import psycopg2 
from confidential import POSTGRESQL_PASSWORD

def yes_or_no(question):
    first_res = raw_input(question)
    while True:
        if first_res != "y" and first_res != "n":
            first_res = raw_input("Please answer with y or n(y/n)")
        else:
            return first_res == "y"


if __name__ == "__main__":
    table = raw_input("Table Name?").strip()
    uid_ans = yes_or_no("Is it UID table?(y/n)")

    conn = psycopg2.connect(database="snucse", password=POSTGRESQL_PASSWORD, host="127.0.0.1", port="5432", user="snucse")#, cursor_factory=DictCursor)
    cursor = conn.cursor()

    try:
        uid_list = []

        if uid_ans:
            cursor.execute('''SELECT uid FROM "{table}"'''.format(table=table))
            while True:
                row = cursor.fetchone()
                if not row:
                    break
                uid_list.append(row[0])
        cursor.execute('''DROP TABLE "{table}" CASCADE'''.format(table=table))
        conn.commit()
        if uid_ans:
            for uid in uid_list:
                cursor.execute(('''DELETE FROM "Base" WHERE uid = %d'''.format(table=table))%uid)
            conn.commit()
    finally:
        conn.close()
    print "DONE. Byebye data~"
