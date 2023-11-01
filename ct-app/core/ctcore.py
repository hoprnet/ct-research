import asyncio
from tools.db_connection import DatabaseConnection
from .node import Node
from .peer import Peer


class CTCore:
    """Class description."""

    def __init__(self):
        """
        Initialisation of the class.
        """
        self.nodes = set[Node]()

        self.database_connection = DatabaseConnection

        self.tasks = set[asyncio.Task]()
        self.all_peers = set[Peer]()

    async def get_aggregated_peers(self):
        """
        Get aggregated peers.
        """

        for node in self.nodes:
            self.all_peers.update(await node.peers)

        print(f"{self.all_peers=}")

    async def start(self):
        """
        Start the node.
        """
        print("CTCore started")

        if self.tasks:
            return

        for node in self.nodes:
            self.tasks.add(asyncio.create_task(node.retrieve_peers()))
            self.tasks.add(asyncio.create_task(node.retrieve_outgoing_channels()))
            self.tasks.add(asyncio.create_task(node.open_channels()))
            self.tasks.add(asyncio.create_task(node.close_pending_channels()))
            self.tasks.add(asyncio.create_task(node.fund_channels()))

        self.tasks.add(asyncio.create_task(self.get_aggregated_peers()))

        await asyncio.gather(*self.tasks)

    def stop(self):
        """
        Stop the node.
        """
        for task in self.tasks:
            task.add_done_callback(self.tasks.discard)
            task.cancel()

    def __str__(self):
        return
