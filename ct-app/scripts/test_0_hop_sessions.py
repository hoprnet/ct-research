from core.api.response_objects import SessionFailure
import asyncio
import click
import sys

sys.path.insert(1, "./")

from scripts.lib.decorators import asynchronous
from core.api.hoprd_api import HoprdAPI


@click.command()
@asynchronous
async def main():
    src_api = HoprdAPI("http://localhost:3000", None, "/api/v4")
    mid_api = HoprdAPI("http://localhost:3001", None, "/api/v4")
    dst_api = HoprdAPI("http://localhost:3002", None, "/api/v4")

    src_addr = await src_api.address()
    mid_addr = await mid_api.address()
    dst_addr = await dst_api.address()

    print(f"src address: {src_addr}")
    print(f"mid address: {mid_addr}")
    print(f"dst address: {dst_addr}")

    idx = 0
    max = 10000
    batch = 200
    while True:
        tasks = [src_api.post_udp_session(dst_addr.native, None) for _ in range(batch)]
        results = await asyncio.gather(*tasks)

        successfull_session_count = sum(
            1 for result in results if not isinstance(result, SessionFailure)
        )

        if successfull_session_count == 0:
            print("Sessions creation failed")
            break
        else:
            idx += successfull_session_count
            print(f"\rCreated session #{idx}", end="", flush=True)

        if idx >= max:
            print(f"\nReached maximum number of sessions: {max}")
            break


if __name__ == "__main__":
    asyncio.run(main())
