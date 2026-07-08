from rq import Queue, Worker

from app.workers.queue import QUEUE_NAME, get_redis_connection


def main() -> None:
    connection = get_redis_connection()
    worker = Worker([Queue(QUEUE_NAME, connection=connection)], connection=connection)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
