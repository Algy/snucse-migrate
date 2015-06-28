from urllib import urlopen
from threading import Thread, Lock, Semaphore
from Queue import Queue, Empty
from time import sleep

class ThreadPool:
    def __init__(self, thread_count=16, queue_size=1000, thread_timeout=0.1):
        self.thread_count = thread_count
        self.fifo = Queue(queue_size)
        self.thread_pool = [] 
        self.started = False
        self.thread_lock = Lock()
        self.thread_timeout = thread_timeout
        self.thread_idle = []
        self.processed_thunks = 0


    def _run(self, idx):
        while self.started:
            try:
                (elem, args, kwds) = self.fifo.get(block=True, timeout=self.thread_timeout)
                elem(*args, **kwds)
                with self.thread_lock:
                    self.processed_thunks += 1

            except Empty:
                pass
            '''
            except Exception as err:
                print "[WORKER EXCEPTION]", err
            '''

    def start(self):
        with self.thread_lock:
            if self.started:
                return 

            self.thread_pool = [Thread(target=self._run, args=(idx, )) for idx in range(self.thread_count)]
            self.thread_idle = [True] * self.thread_count
            for thread in self.thread_pool:
                thread.setDaemon(True)

            self.started = True
            for thread in self.thread_pool:
                thread.start()


    def end(self):
        with self.thread_lock:
            if not self.started:
                return

            self.started = False
            for thread in self.thread_pool: 
                thread.join()

    def count(self):
        with self.thread_lock:
            return self.processed_thunks
    
    def _issue_id(self):
        with self.id_lock:
            self.last_id += 1
            return self.last_id

    def __call__(self, thunk, args=(), kwds={}):
        self.fifo.put((thunk, args, kwds))

