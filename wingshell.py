#!/usr/bin/env python

import pprint
from pymssql import connect

from confidential import SQLSERVER_PASSWORD

class MyPrettyPrinter(pprint.PrettyPrinter):
    def format(self, object, context, maxlevels, level):
        if isinstance(object, unicode):
            return ('"' + object.encode('utf8') + '"', True, False)
        return pprint.PrettyPrinter.format(self, object, context, maxlevels, level)

mypprint = MyPrettyPrinter().pprint

def make_conn():
    return connect(host="gin.snucse.org", port=8192, user="sa", 
                   password=SQLSERVER_PASSWORD, 
                   database="kahlua_wings",
                   as_dict=True)


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
            cmd = raw_input().decode("utf-8")
            if cmd == "q":
                break
        conn.commit()
    conn.close()

def test():

    conn = make_conn()
    cursor = conn.cursor()

    cursor.execute('''select user_account from article where user_account is NOT NULL and user_uid is NULL''')


    


if __name__ == "__main__":
    repl()
    # test()
