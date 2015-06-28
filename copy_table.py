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
    dest_database = raw_input("To?").strip()

    conn = psycopg2.connect(database="snucse", password=POSTGRESQL_PASSWORD, host="127.0.0.1", port="5432", user="snucse")#, cursor_factory=DictCursor)
    conn.set_isolation_level(0)
    cursor = conn.cursor()

    try:
        cursor.execute('''
                CREATE DATABASE %s WITH TEMPLATE snucse OWNER snucse 
        '''%dest_database)
        conn.commit()
    finally:
        conn.close()
    print "DONE."
