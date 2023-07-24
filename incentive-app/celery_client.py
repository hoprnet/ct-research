from celery import Celery

from tools import envvar


def main():
    app = Celery(
        name="client",
        broker=envvar("CELERY_BROKER_URL"),
        backend=envvar("CELERY_RESULT_BACKEND"),
        include=["celery_tasks"],
    )
    app.autodiscover_tasks(force=True)

    node_list = ["16Uiu2HAkzmoj11xg2euJpU2RpbSvXtqxyoCSLahn4QuY3k3aZgmg"]
    peer_id = "peer_a"
    count = 10
    node_index = 0

    app.send_task(
        f"{envvar('TASK_NAME')}.{node_list[node_index]}",
        args=(peer_id, count, node_list, node_index),
        queue=node_list[node_index],
    )


if __name__ == "__main__":
    main()


# for task in tasks:
#     task.get()

# print("---- FINAL STATE ----")
# for idx, task in enumerate(tasks):
#     print(f"task{idx}: {task.state}")
