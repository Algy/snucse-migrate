#!/usr/bin/env python

import pprint
from sqlite3 import connect


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
    conn = connect("./cloud.db")
    conn.row_factory = dict_factory
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
            continue

        while True:
            row = cursor.fetchone()
            if not row:
                break
            mypprint(row)
            cmd = raw_input()
            if cmd == "q":
                break
        conn.commit()
    conn.close()



if __name__ == "__main__":
    repl()
