# -*- coding: utf-8 -*-
import failback

from threadutil import ThreadPool
from pprint import pprint
from time import time, sleep
from pymssql import connect
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import scoped_session, sessionmaker


PASSWORD_ENC = [35, 45, 34, 41, 38, 35, 42, 33, 38, 44, 48, 117, 32, 44, 33, 44, 123, 116] 
PASSWORD_KEY = 71
PASSWORD_DEC = "".join([chr(x ^ PASSWORD_KEY) for x in PASSWORD_ENC])

#
# Util functions
#

def make_conn():
    return connect(host="gin.snucse.org", port=8192, user="sa", 
                   password=PASSWORD_DEC, 
                   database="kahlua_wings",
                   as_dict=True)

def check_performance(fun):
    def inner(*args, **kwds):
        st = time()
        result = fun(*args, **kwds)
        ed = time()
        print "Time elapsed: %f (s)" % (ed - st)
        return result
    return inner

#
# Savers
# 

SAVER_ACCUMULATION_LIMIT = 1
SAVER_FLUSH_TIME_LIMIT = 0.0
class EngineSaver:
    def __init__(self, db):
        self.acc_count = 0
        self.first_arrival_time = None
        self.db = db

    def __call__(self, obj):
        if isinstance(obj, BaseCustomSaver):
            obj.save(self.db)
        else:
            self.db.add(obj)
        cur_time = time()
        if self.acc_count == 0:
            self.first_arrival_time = cur_time
        self.acc_count += 1
        if self.acc_count > SAVER_ACCUMULATION_LIMIT or \
           cur_time - self.first_arrival_time >= SAVER_FLUSH_TIME_LIMIT:
           self.flush()

    def flush(self):
        self.db.commit()
        self.acc_count = 0

#
# Main functions
#
class BaseCustomSaver:
    def save(self, db):
        raise NotImplementedError

#
# Pipeline
#

def make_thunk(saver, obj):
    def thunk():
        if isinstance(obj, (tuple, list, )):
            for item in obj:
                saver(item)
        else:
            saver(obj)
    return thunk

                      
@check_performance
def invoke_pipeline(cursor, cursor2, 
                    gatherer, converter, saver):

    cnt = 0
    thread_pool = ThreadPool(1)
    thread_pool.start()

    for obj in converter(gatherer(cursor, cursor2)):
        thunk = make_thunk(saver, obj)
        thread_pool(thunk)
        cnt += 1
    while thread_pool.count() < cnt:
        sleep(1)
    thread_pool.end()

#
# Main execution script
#


class Migrater:
    def __init__(self, url):
        self.engine = create_engine(url)
        self.metadata = MetaData(self.engine)
        self.db = scoped_session(sessionmaker(bind=self.engine)) # public attr

    def start(self):
        self.conn = make_conn()
        self.conn2 = make_conn()
        self.cursor = self.conn.cursor() # public attr
        self.cursor2 = self.conn2.cursor() # public attr
        self.saver = EngineSaver(self.db)

        print "CONFIGURATING FAILBACKs"
        failback.config_failback(self.cursor)


    def migrate(self, gatherer, converter):
        invoke_pipeline(self.cursor, self.cursor2, gatherer, converter, self.saver)
        self.saver.flush()

    def close(self):
        self.conn.close()
        self.conn2.close()


    def ensure_table(self, table_obj):
        table_obj.metadata.create_all(self.engine)



