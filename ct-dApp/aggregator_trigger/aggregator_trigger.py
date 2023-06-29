import asyncio
import requests
from ct.decorator import wakeupcall

class AggregatorTrigger:
    """ Class description."""
    def __init__(self, host: str, port: int, route: str):
        """
        Initialisation of the class.
        """
        self.started = False
        self.tasks = set[asyncio.Task]()
        self.endpoint_url = f"http://{host}:{port}{route}"

    @wakeupcall(minutes=1)
    async def send_list_to_db(self):
        try:
            response = requests.get(self.endpoint_url)
        # catch request exceptions
        except requests.exceptions.RequestException as e:
            print("Request exception: ", e)
            return
        else:
            print("Response: ", response)
            return

    def stop(self):
        """
        Stops the tasks of this node
        """
        self.started = False
        for task in self.tasks:
            task.cancel()
        self.tasks.clear()
    
    async def start(self):
        """
        Starts the tasks of this node
        """
        if self.tasks:
            return
    
        self.started = True
        self.tasks.add(asyncio.create_task(self.send_list_to_db()))

        await asyncio.gather(*self.tasks)