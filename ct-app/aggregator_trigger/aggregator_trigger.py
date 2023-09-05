import asyncio

import requests

from tools import getlogger
from tools.decorator import formalin

log = getlogger()


class AggregatorTrigger:
    """This class is used to trigger the aggregator to send its data to the db
    every hour:minute:second.
    """

    def __init__(self, endpoint: str):
        """
        Initialisation of the class.
        :param host: The host of the aggregator
        :param port: The port of the aggregator
        :param route: The route to the 'send_list_to_db' method
        """
        self.started = False
        self.tasks = set[asyncio.Task]()
        self.endpoint = endpoint

    @formalin(sleep=60 * 15)
    async def send_list_to_db(self):
        """
        Sends a request to the aggregator to send its data to the db
        """
        log.info("Sending request to Aggregator to send data to db")

        to_db_url = f"{self.endpoint}/aggregator/to_db"

        try:
            response = requests.get(to_db_url)
        except requests.exceptions.RequestException:
            log.exception("Error sending request to Aggregator to store in db")
            return False
        else:
            log.info(f"Response for `send_list`: {response}")
            return True

    @formalin(sleep=60 * 2)
    async def check_nodes_timestamps(self):
        """
        Sends a request to the aggregator to check if the nodes stores are updated
        recently enough
        """
        log.info("Sending request to Aggregator to check nodes timestamps")

        check_timestamps_url = f"{self.endpoint}/aggregator/check_timestamps"

        try:
            response = requests.get(check_timestamps_url)
        except requests.exceptions.RequestException:
            log.exception("Error sending request to aggregator to check timestamps")
            return False
        else:
            log.info(f"Response for `check_timestamps`: {response}")
            return True

    def stop(self):
        """
        Stops the tasks of this node
        """
        log.info("Stopping AggTrigger instance")

        self.started = False
        for task in self.tasks:
            task.cancel()
        self.tasks.clear()

    async def start(self):
        """
        Starts the automatic triggering of the aggregator
        """
        log.info("Starting AggTrigger instance")
        if self.tasks:
            return

        self.started = True
        self.tasks.add(asyncio.create_task(self.send_list_to_db()))
        self.tasks.add(asyncio.create_task(self.check_nodes_timestamps()))

        await asyncio.gather(*self.tasks)
