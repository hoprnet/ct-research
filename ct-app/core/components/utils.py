from core.model.subgraph import SafeEntry

from .baseclass import Base
from .channelstatus import ChannelStatus
from .environment_utils import EnvironmentUtils


class Utils(Base):
    @classmethod
    def nodesCredentials(
        cls, address_prefix: str, keyenv: str
    ) -> tuple[list[str], list[str]]:
        """
        Returns a tuple containing the addresses and keys of the nodes.
        :param address_prefix: The prefix of the environment variables containing addresses.
        :param keyenv: The prefix of the environment variables containing keys.
        :returns: A tuple containing the addresses and keys.
        """
        addresses = EnvironmentUtils.envvarWithPrefix(address_prefix).values()
        keys = EnvironmentUtils.envvarWithPrefix(keyenv).values()

        return list(addresses), list(keys)

    @classmethod
    async def mergeDataSources(
        cls, topology: list, peers: list, nodes: list, allocations: list
    ):
        merged_result: list = []
        addresses = [item.address.address for item in peers]
        for address in addresses:
            peer = next(filter(lambda p: p.address.address == address, peers), None)
            topo = next(filter(lambda t: t.node_address == address, topology), None)
            node = next(filter(lambda s: s.node_address == address, nodes), None)

            safe = getattr(node, "safe", SafeEntry.default())

            for allocation in allocations:
                if safe.address in allocation.linked_safes:
                    safe.additional_balance += (
                        allocation.allocatedAmount / allocation.num_linked_safes
                    )

            if topo is not None and safe != SafeEntry.default() and peer is not None:
                peer.channel_balance = topo.channels_balance
                peer.safe = safe
            else:
                await peer.yearly_message_count.set(None)

            merged_result.append(peer)

        cls().info(f"Merged topology and subgraph data ({len(merged_result)} entries).")

        return merged_result

    @classmethod
    def associateAllocationsAndSafes(cls, allocations, nodes):
        allocations_addresses = [a.address for a in allocations]
        for n in nodes:
            for owner in n.safe.owners:
                try:
                    index = allocations_addresses.index(owner)
                except ValueError:
                    continue

                allocations[index].linked_safes.append(n.safe.address)

    @classmethod
    def allowManyNodePerSafe(cls, peers: list):
        """
        Split the stake managed by a safe address equaly between the nodes
        that the safe manages.
        :param peer: list of peers
        :returns: nothing.
        """
        safe_counts = {peer.safe_address: 0 for peer in peers}

        # Calculate the number of safe_addresses related to a node address
        for peer in peers:
            safe_counts[peer.safe_address] += 1

        # Update the input_dict with the calculated splitted_stake
        for peer in peers:
            peer.safe_address_count = safe_counts[peer.safe_address]

    @classmethod
    def exclude(cls, source_data: list, blacklist: list, text: str = "") -> list:
        """
        Removes elements from a dictionary based on a blacklist.
        :param source_data (dict): The dictionary to be updated.
        :param blacklist (list): A list containing the keys to be removed.
        :returns: A list containing the removed elements.
        """

        addresses = [peer.address for peer in source_data]
        indexes = [addresses.index(item) for item in blacklist if item in addresses]

        # Remove elements from the list
        excluded = []
        for index in sorted(indexes, reverse=True):
            peer = source_data.pop(index)
            excluded.append(peer)

        cls().info(f"Excluded {text} ({len(excluded)} entries).")

        return excluded

    @classmethod
    async def balanceInChannels(cls, channels: list) -> dict[str, dict]:
        """
        Returns a dict containing all unique source_peerId-source_address links.
        :param channels: The list of channels.
        :returns: A dict containing all peerIds-balanceInChannels links.
        """

        results: dict[str, dict] = {}
        for c in channels:
            if not (
                hasattr(c, "source_peer_id")
                and hasattr(c, "source_address")
                and hasattr(c, "status")
                and hasattr(c, "balance")
            ):
                continue

            if ChannelStatus(c.status) != ChannelStatus.Open:
                continue

            if c.source_peer_id not in results:
                results[c.source_peer_id] = {
                    "source_node_address": c.source_address,
                    "channels_balance": 0,
                }

            results[c.source_peer_id]["channels_balance"] += int(c.balance) / 1e18

        return results
