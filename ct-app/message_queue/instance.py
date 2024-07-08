import asyncio

from .message_queue import MessageQueue

task = asyncio.create_task


class Peer:
    def __init__(self, name: str, delay: float):
        self.name = name
        self.delay = delay
        self.count = 0

    async def relay(self):
        queue = MessageQueue()

        while True:
            await queue.publish(f"Message from peer {self.name} ({self.count})")
            self.count += 1
            await asyncio.sleep(self.delay)


class Instance:
    def __init__(self):
        self.tasks = set[asyncio.Task]()
        self.count = 0

        self.peers = [
            Peer(f"peer{idx}", delay)
            for idx, delay in enumerate([0.10, 0.12, 0.15, 0.4])
        ]

    async def long_running(self):
        while True:
            await asyncio.sleep(2)
            print("Long running task done")

    async def start(self):
        print("Starting the instance")
        self.tasks.add(task(self.long_running()))

        for i in range(5):
            self.tasks.add(task(MessageQueue().consume(f"consumer{i}")))

        for peer in self.peers:
            self.tasks.add(task(peer.relay()))

        await asyncio.gather(*self.tasks)

    def stop(self):
        for peer in self.peers:
            print(f"{peer.name}: count={peer.count}")

        for task in self.tasks:
            task.add_done_callback(self.tasks.discard)
            task.cancel()
