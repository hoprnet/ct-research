import asyncio

from tools.db_connection import DatabaseConnection

from .components.baseclass import Base
from .components.decorators import flagguard
from .model.peer import Peer
from .node import Node


class CTCore(Base):
    def __init__(self):
        self.nodes = set[Node]()

        self.database_connection = DatabaseConnection

        self.tasks = set[asyncio.Task]()
        self.all_peers = set[Peer]()

    @property
    def print_prefix(self) -> str:
        return "ct-core"

    @flagguard
    async def aggregate_peers(self):
        for node in self.nodes:
            self.all_peers.update(await node.peers.get())

    @flagguard
    async def get_subgraph_data(self):
        pass

    @flagguard
    async def get_topology_data(self):
        pass

    @flagguard
    async def apply_economic_model(self):
        pass

    @flagguard
    async def distribute_rewards(self):
        pass

    async def start(self):
        """
        Start the node.
        """
        print("CTCore started")

        if self.tasks:
            return

        for node in self.nodes:
            await node.retrieve_address()
            self.tasks.update(node.tasks())

        self.tasks.add(asyncio.create_task(self.aggregate_peers()))
        self.tasks.add(asyncio.create_task(self.get_subgraph_data()))
        self.tasks.add(asyncio.create_task(self.get_topology_data()))

        self.tasks.add(asyncio.create_task(self.apply_economic_model()))
        self.tasks.add(asyncio.create_task(self.distribute_rewards()))

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
