

from multiprocessing import Pool, Queue
from typing import Any


class PoolManager:

    def __init__(self, poolsz: int, queue: Queue, task: callable[[int, Queue],Any]):
        self.pool = Pool(poolsz)
        self.queue = queue
        self.task = task
        self.next_proc_id = 0
        self.queue_cnt = 0
        self.complete_cnt = 0

    def start(self):
        self.pool.apply_async(
            func=self.task, 
            args=(self.next_proc_id, self.queue), 
            callback=self.__task_complete
        )
        self.next_proc_id += 1
        self.queue_cnt += 1
    
    def __task_complete(self):
        self.complete_cnt += 1
        self.queue.put({'op': 'pool', 'queue_cnt': self.queue_cnt, 'complete_cnt': self.complete_cnt})

