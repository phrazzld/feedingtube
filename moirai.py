from redis import Redis
from rq import Queue
import feedtube

redis_conn = Redis()
one_day = 86400 #seconds

clotho = Queue('clotho', connection=redis_conn, default_timeout=one_day)
lachesis = Queue('lachesis', connection=redis_conn, default_timeout=one_day)
atropos = Queue('atropos', connection=redis_conn, default_timeout=one_day)

def queue_up(email, tag, amount):
    if amount >= 150:
        atropos.enqueue(feedtube.get_food, email, tag, amount)
    elif amount >= 50:
        lachesis.enqueue(feedtube.get_food, email, tag, amount)
    else:
        clotho.enqueue(feedtube.get_food, email, tag, amount)
