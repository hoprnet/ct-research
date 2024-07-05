import asyncio


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class MessageQueue(metaclass=Singleton):
    def __init__(self):
        self.queue = asyncio.Queue()

    async def publish(self, message):
        await self.queue.put(message)

    async def subscriber(self, consumer: str):
        while True:
            message = await self.queue.get()
            print(f"`{consumer}` received message: {message}")
