from celery import Celery

from tools import envvar

CELERY_BROKER_URL = envvar("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = envvar("CELERY_RESULT_BACKEND")
TASK_NAME = envvar("TASK_NAME")

app = Celery(
    name="client",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["celery_tasks"],
)
app.autodiscover_tasks(force=True)


node_list = ["0x1", "0x1"]
peer_id = "peer_a"
count = 10
node_index = 0

app.send_task(
    f"{TASK_NAME}.{node_list[node_index]}",
    args=(peer_id, count, node_list, node_index),
    queue=node_list[node_index],
)


# for task in tasks:
#     task.get()

# print("---- FINAL STATE ----")
# for idx, task in enumerate(tasks):
#     print(f"task{idx}: {task.state}")
