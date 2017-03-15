from redis import Redis
from rq import Queue

redis_conn = Redis()
one_day = 86400         # seconds

clotho = Queue('clotho', connection=redis_conn, default_timeout=one_day)
lachesis = Queue('lachesis', connection=redis_conn, default_timeout=one_day)
atropos = Queue('atropos', connection=redis_conn, default_timeout=one_day)
