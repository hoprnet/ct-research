import asyncio

from core.blokli.providers import Health, Safes, Version


async def main():
    blokli_url = "https://blokli.rotsee.hoprnet.link/graphql"

    # version_result = await Version(blokli_url).get()
    # health_result = await Health(blokli_url).get()
    safe_result = await Safes(blokli_url).get()
    
    # print(version_result.version)
    # print(health_result.health)
    print(safe_result.address)

if __name__ == "__main__":
    asyncio.run(main())
