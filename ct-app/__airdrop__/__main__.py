import click

from .gcpfile import GCPBucket
from .reward_entry import RewardEntry


@click.command()
@click.option("--start", help="Start date, inclusive (YYYYMMDD-HHMMSS format")
@click.option("--end", help="End date, exclusive (YYYYMMDD-HHMMSS format")
def main(start: str, end: str = None):
    files = GCPBucket("ct-platform-ct").files_in_range(start, end, "expected_rewards")

    # Get all entries from all files in the time range
    table_entries = sum([file.toTableEntry() for file in files], [])

    # Get unique list of peers
    peer_rewards = list(
        {RewardEntry(e.source_node_address, e.safe_address) for e in table_entries}
    )

    # Sum for each address the rewards_per_dist
    for entry in table_entries:
        index = peer_rewards.index(RewardEntry(entry.source_node_address))
        peer_rewards[index].reward += entry.reward_per_dist

    # to csv using prints
    print("node_address,safe_address,reward")
    for peer in peer_rewards:
        if not peer.in_network:
            continue
        print(f"{peer.node_address},{peer.safe_address},{peer.reward}")


if __name__ == "__main__":
    main()
