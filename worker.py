"""
RQ Worker for processing music translation tasks

Connects to Redis and listens on the 'translations' queue
to execute background jobs
"""

import os
import logging
import time
import sys
import redis
from rq import Worker, Queue

# Configure logging for the worker
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# --- Redis Connection ---
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis-service')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
LISTEN_QUEUES = ['translations']

# --- Start Worker ---
if __name__ == '__main__':
    # Retry connection logic for robustness
    RETRIES = 5
    redis_conn = None
    while RETRIES > 0:
        try:
            redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
            redis_conn.ping()
            logging.info("Worker connected to Redis at %s:%d", REDIS_HOST, REDIS_PORT)
            break
        except redis.exceptions.ConnectionError as e:
            RETRIES -= 1
            logging.warning(
                "Worker failed to connect to Redis (%s). Retrying (%d left) ...",
                e,
                RETRIES
            )
            if RETRIES == 0:
                logging.error("Worker could not connect to Redis after multiple retries. Exiting.")
                sys.exit(1)
            time.sleep(5)

    if redis_conn:
        queues_to_listen = [Queue(queue_name, connection=redis_conn) for queue_name in LISTEN_QUEUES]
        worker = Worker(queues_to_listen)
        logging.info("RQ Worker started, listening on queues: %s", ', '.join(LISTEN_QUEUES))
        worker.work(with_scheduler=False)
    else:
        logging.error("No Redis connection, worker cannot start.")
