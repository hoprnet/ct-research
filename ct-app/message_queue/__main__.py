import asyncio
from signal import SIGINT, SIGTERM

from .instance import Instance


def main():
    instance = Instance()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(SIGINT, instance.stop)
    loop.add_signal_handler(SIGTERM, instance.stop)

    start_time = loop.time()
    try:
        loop.run_until_complete(instance.start())
    except asyncio.CancelledError:
        print("Stopping the instance")
    finally:
        loop.close()

    print(f"Total runtime: {loop.time() - start_time:.2f}s")


if __name__ == "__main__":
    main()
