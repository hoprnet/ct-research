import asyncio

from tools.db_connection import DatabaseConnection

from .components.baseclass import Base
from .components.decorators import flagguard, formalin
from .components.lockedvar import LockedVar
from .model.peer import Peer
from .node import Node


class CTCore(Base):
    def __init__(self):
        self.nodes = set[Node]()

        self.database_connection = DatabaseConnection

        self.tasks = set[asyncio.Task]()
        self.all_peers = set[Peer]()
        self.connected = LockedVar("connected", False)

        self.started = False

    @property
    def print_prefix(self) -> str:
        return "ct-core"

    @flagguard(prefix="CORE_")
    @formalin(flag_prefix="CORE_")
    async def healthcheck(self):
        states = [await node.connected.get() for node in self.nodes]
        await self.connected.set(all(states))

        self._debug(f"Connection state: {await self.connected.get()}")

    @flagguard(prefix="CORE_")
    async def aggregate_peers(self):
        for node in self.nodes:
            self.all_peers.update(await node.peers.get())

    @flagguard(prefix="CORE_")
    async def get_subgraph_data(self):
        pass

    @flagguard(prefix="CORE_")
    async def get_topology_data(self):
        pass

    @flagguard(prefix="CORE_")
    async def apply_economic_model(self):
        pass

    @flagguard(prefix="CORE_")
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
            node.started = True
            await node.retrieve_address()
            self.tasks.update(node.tasks())

        self.started = True

        self.tasks.add(asyncio.create_task(self.healthcheck()))

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
        self.started = False

        for node in self.nodes:
            node.started = False

        for task in self.tasks:
            task.add_done_callback(self.tasks.discard)
            task.cancel()
