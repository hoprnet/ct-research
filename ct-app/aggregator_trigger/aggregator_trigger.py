import asyncio
import requests
from tools.decorator import formalin
from tools import getlogger

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
        self.endpoint_url = endpoint

    @formalin(sleep=300)
    async def send_list_to_db(self):
        """
        Sends a request to the aggregator to send its data to the db
        """
        log.info("Sending request to aggregator to send data to db")
        try:
            response = requests.get(self.endpoint_url)
        except requests.exceptions.RequestException:
            log.exception("Error while sending request to aggregator")
            return False
        else:
            log.info(f"Response for `send_list`: {response}")
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

        await asyncio.gather(*self.tasks)
