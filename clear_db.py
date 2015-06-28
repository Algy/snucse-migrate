#!/usr/bin/env python
# -*- coding: utf-8 -*-

import psycopg2 
from confidential import POSTGRESQL_PASSWORD

if __name__ == "__main__":
    if raw_input("Do you really want to drop the db?(Y/y)").lower() == "y":
        conn = psycopg2.connect(database="snucse", password=POSTGRESQL_PASSWORD, host="127.0.0.1", port="5432", user="snucse")#, cursor_factory=DictCursor)
        cursor = conn.cursor()
        try:
            cursor.execute("drop schema public cascade; create schema public;")
            conn.commit()
        except Exception as e:
            print "[ERROR]", e
            conn.rollback()
        conn.close()
        print "DONE. Byebye data~"





