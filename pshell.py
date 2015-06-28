#!/usr/bin/env python

import pprint
import psycopg2 

from confidential import POSTGRESQL_PASSWORD
from psycopg2 import connect
from psycopg2.extras import DictCursor


class MyPrettyPrinter(pprint.PrettyPrinter):
    def format(self, object, context, maxlevels, level):
        if isinstance(object, unicode):
            return ('"' + object.encode('utf8') + '"', True, False)
        return pprint.PrettyPrinter.format(self, object, context, maxlevels, level)

mypprint = MyPrettyPrinter().pprint



def make_conn():
    def dict_factory(cursor, row): 
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d
    conn = connect(database="snucse", password=POSTGRESQL_PASSWORD, host="127.0.0.1", port="5432", user="snucse")#, cursor_factory=DictCursor)
    return conn


def repl_input():
    print ">>",
    s = ""
    first = False

    while True:
        line = raw_input()
        s += line + "\n"
        if not line:
            break
    return s.strip()
    

def repl():
    conn = make_conn()

    cursor = conn.cursor()
    while True:
        s = repl_input()
        if s == "quit" or s == "exit":
            print "[Bye!]"
            break
        try:
            cursor.execute(s)
        except Exception as e:
            print "[ERROR]", e
            conn.rollback()
            continue

        try:
            while True:
                row = cursor.fetchone()
                if not row:
                    break
                mypprint(row)
                cmd = raw_input()
                if cmd == "q":
                    break
        except psycopg2.ProgrammingError as e:
            print "[PROGRAMMING ERROR] ", e
        finally:
            conn.commit()
    conn.close()



if __name__ == "__main__":
    repl()
