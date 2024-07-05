import asyncio


class MessageQueue:
    def __init__(self):
        self.queue = asyncio.Queue()

    async def publish(self, message):
        await self.queue.put(message)

    async def subscribe(self, consumer: str):
        result = await self.queue.get()
        print(f"`{consumer}` received message: {result}")


async def main():
    message_queue = MessageQueue()

    await asyncio.gather(
        message_queue.subscribe("consumer1"),
        message_queue.subscribe("consumer2"),
        message_queue.subscribe("consumer3"),
    )

    await message_queue.publish("Hello 1")
    await message_queue.publish("Hello 2")


if __name__ == "__main__":
    asyncio.run(main())
