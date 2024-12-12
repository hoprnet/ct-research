from core.baseclass import Base
from core.subgraph.entries import Safe

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
        cls,
        topology: list,
        peers: list,
        nodes: list,
        allocations: list,
        eoa_balances: dict,
    ):
        for peer in peers:
            address = peer.node_address
            topo = next(filter(lambda t: t.address == address, topology), None)
            node = next(filter(lambda n: n.address == address, nodes), None)

            peer.safe = getattr(node, "safe", Safe.default())

            for allocation in allocations:
                if peer.safe.address in allocation.linked_safes:
                    peer.safe.additional_balance += (
                        allocation.unclaimed_amount / allocation.num_linked_safes
                    )

            for eoa_balance in eoa_balances:
                if peer.safe.address in eoa_balance.linked_safes:
                    peer.safe.additional_balance += (
                        eoa_balance.balance / eoa_balance.num_linked_safes
                    )

            if topo is not None:
                peer.channel_balance = topo.channels_balance
            else:
                peer.yearly_message_count = None

        cls().info("Merged topology, peers, and safes data.")

    @classmethod
    def associateEntitiesToNodes(cls, entities, nodes):
        entity_addresses = [e.address for e in entities]
        for n in nodes:
            for owner in n.safe.owners:
                try:
                    index = entity_addresses.index(owner)
                except ValueError:
                    continue

                entities[index].linked_safes.add(n.safe.address)

    @classmethod
    def allowManyNodePerSafe(cls, peers: list):
        """
        Split the stake managed by a safe address equaly between the nodes
        that the safe manages.
        :param peer: list of peers
        :returns: nothing.
        """
        safe_counts = {peer.safe.address: 0 for peer in peers}

        # Calculate the number of safe_addresses related to a node address
        for peer in peers:
            safe_counts[peer.safe.address] += 1

        # Update the input_dict with the calculated splitted_stake
        for peer in peers:
            peer.safe_address_count = safe_counts[peer.safe.address]

    @classmethod
    def exclude(cls, source_data: list, blacklist: list, text: str = "") -> list:
        """
        Removes elements from a dictionary based on a blacklist.
        :param source_data (dict): The dictionary to be updated.
        :param blacklist (list): A list containing the keys to be removed.
        :returns: A list containing the removed elements.
        """

        addresses = [peer.address for peer in source_data]
        indexes = [addresses.index(item)
                   for item in blacklist if item in addresses]

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

            if not c.status.is_open:
                continue

            if c.source_peer_id not in results:
                results[c.source_peer_id] = {
                    "source_node_address": c.source_address,
                    "channels_balance": 0,
                }

            results[c.source_peer_id]["channels_balance"] += int(
                c.balance) / 1e18

        return results
