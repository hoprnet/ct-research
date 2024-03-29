import click

from .gcpfile import GCPBucket
from .reward_entry import RewardEntry


@click.command()
@click.option("--start", help="Start date, inclusive (YYYYMMDD-HHMMSS format)")
@click.option("--end", help="End date, exclusive (YYYYMMDD-HHMMSS format)")
@click.option("--bucket", default="ct-platform-ct", help="GCP bucket name")
@click.option("--folder", default="expected_rewards", help="Folder name inside bucket")
def main(start: str, end: str, bucket: str, folder: str):
    files = GCPBucket(bucket).files_in_range(start, end, folder)

    # Get all entries from all files in the time range
    table_entries = sum([file.toTableEntry() for file in files], [])

    # Get unique list of peers
    peer_rewards = list(
        {RewardEntry(e.node_address, e.safe_address) for e in table_entries}
    )

    # Sum for each address the rewards_per_dist
    for entry in table_entries:
        index = peer_rewards.index(RewardEntry(entry.node_address))
        peer_rewards[index].reward += entry.protocol_reward_per_distribution

    # to csv using prints
    print("node_address,safe_address,reward")
    for peer in peer_rewards:
        if not peer.in_network:
            continue
        print(f"{peer.node_address},{peer.safe_address},{peer.reward}")


if __name__ == "__main__":
    main()
