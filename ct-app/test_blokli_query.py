import asyncio

import click
from dotenv.cli import cli

from core.blokli.providers import HoprBalance, Redemptions, AccountSubscription
from scripts.lib.decorators import asynchronous


@click.command()
@click.option("--url", default="")
@asynchronous
async def main(url: str):
    blokli_url = f"{url}/graphql"


    # async with HoprBalance(blokli_url) as client:
    #     print(await client.get(address="0xdC0DeA7A62b02Ce24CC8ce8Dead861614D15c3C1"))

    # async with Redemptions(blokli_url) as client:
    #     print(await client.get(safe_address="0xdC0DeA7A62b02Ce24CC8ce8Dead861614D15c3C1"))
    #     print(await client.get(node_address="0xFE3AF421afB84EED445c2B8f1892E3984D3e41eA"))
    #     print(await client.get(
    #         node_address="0xFE3AF421afB84EED445c2B8f1892E3984D3e41eA", safe_address="0xdC0DeA7A62b02Ce24CC8ce8Dead861614D15c3C1")
    #     )
    #     print(await client.get(
    #         node_address="0xFE3AF421afB84EED445c2B8f1892E3984D3e41eb", safe_address="0xdC0DeA7A62b02Ce24CC8ce8Dead861614D15c3C1")
    #     )
    #     print(await client.get())
        

    async with AccountSubscription(blokli_url) as client:
        async for account in client.subscribe():
            print(account)

if __name__ == "__main__":
    asyncio.run(main())
