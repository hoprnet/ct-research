import asyncio

from celery import Celery
from tools import envvar, getlogger

log = getlogger()

app = Celery(
    name=envvar("PROJECT_NAME"),
    broker=envvar("CELERY_BROKER_URL"),
    # backend=envvar("CELERY_RESULT_BACKEND"),
)


# the name of the task is the name of the "<task_name>.<node_address>"
@app.task(name=f"{envvar('TASK_NAME')}")
def foo_task():
    return asyncio.run(foo_task())


async def async_foo():
    pass
