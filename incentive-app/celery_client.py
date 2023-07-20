from os import environ

from celery import Celery

CELERY_BROKER_URL = environ.get("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = environ.get("CELERY_RESULT_BACKEND")

app = Celery(name="client", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)


task = app.send_task(
    "send_1_hop_message.0x11",
    args=(
        "peer",
        1,
    ),
)
print(task.get())
