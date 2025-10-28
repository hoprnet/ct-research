import ast
import logging
import os
from copy import deepcopy

from ..components.balance import Balance
from ..components.logs import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


class Utils:
    @classmethod
    async def mergeDataSources(
        cls,
        outgoing_channel_balance: dict[str, Balance],
        peers: list,
        nodes: list,
        allocations: list,
        eoa_balances: dict,
    ):
        # Pre-index nodes by address for O(1) lookup
        nodes_by_address = {}
        for node in nodes:
            if node and hasattr(node, "address") and node.address:
                nodes_by_address[node.address.lower()] = node

        # Pre-index allocations by safe address for O(1) lookup
        allocations_by_safe: dict[str, list] = {}
        for allocation in allocations:
            if hasattr(allocation, "linked_safes"):
                for safe_addr in allocation.linked_safes:
                    if safe_addr not in allocations_by_safe:
                        allocations_by_safe[safe_addr] = []
                    allocations_by_safe[safe_addr].append(allocation)

        # Pre-index eoa_balances by safe address for O(1) lookup
        eoa_balances_by_safe: dict[str, list] = {}
        for eoa_balance in eoa_balances:
            if hasattr(eoa_balance, "linked_safes"):
                for safe_addr in eoa_balance.linked_safes:
                    if safe_addr not in eoa_balances_by_safe:
                        eoa_balances_by_safe[safe_addr] = []
                    eoa_balances_by_safe[safe_addr].append(eoa_balance)

        # Now process peers with O(1) lookups
        for peer in peers:
            balance = outgoing_channel_balance.get(peer.address.native, None)

            node = (
                nodes_by_address.get(peer.node_address.lower(), None)
                if hasattr(peer, "node_address")
                else None
            )

            if node is None or not hasattr(node, "safe"):
                continue

            peer.safe = deepcopy(node.safe)
            peer.safe.additional_balance = Balance.zero("wxHOPR")

            # O(1) allocation lookup
            safe_allocations = allocations_by_safe.get(peer.safe.address, [])
            for allocation in safe_allocations:
                peer.safe.additional_balance += (
                    allocation.unclaimed_amount / allocation.num_linked_safes
                )

            # O(1) eoa_balance lookup
            safe_eoa_balances = eoa_balances_by_safe.get(peer.safe.address, [])
            for eoa_balance in safe_eoa_balances:
                peer.safe.additional_balance += eoa_balance.amount / eoa_balance.num_linked_safes

            if balance is not None:
                peer.channel_balance = balance
            else:
                peer.yearly_message_count = None

    @classmethod
    def associateEntitiesToNodes(cls, entities, nodes):
        entity_addresses = [e.address for e in entities]
        for n in nodes:
            if not n.safe:
                continue
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
        safe_counts = {peer.safe.address: 0 for peer in peers if peer.safe}

        # Calculate the number of safe_addresses related to a node address
        for peer in peers:
            if not peer.safe:
                continue
            safe_counts[peer.safe.address] += 1

        # Update the input_dict with the calculated splitted_stake
        for peer in peers:
            if not peer.safe:
                continue
            peer.safe_address_count = safe_counts[peer.safe.address]

    @classmethod
    async def balanceInChannels(cls, channels: list) -> dict[str, Balance]:
        """
        Returns a dict containing all unique saddress-balance links.
        :param channels: The list of channels.
        :returns: A dict containing all address-balance links.
        """

        results: dict[str, Balance] = {}
        for c in channels:
            if not (hasattr(c, "source") and hasattr(c, "status") and hasattr(c, "balance")):
                continue

            if not c.status.is_open:
                continue

            if c.source not in results:
                results[c.source] = Balance.zero("wxHOPR")

            results[c.source] += c.balance

        return results

    @classmethod
    def get_methods(cls, folder: str, target: str):
        keepalive_methods = []

        for root, _, files in os.walk(folder):
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r") as f:
                        source_code = f.read()
                    tree = ast.parse(source_code)
                except FileNotFoundError as e:
                    logger.error(f"Could not find file {file_path}: {e}")
                    continue
                except SyntaxError as e:
                    logger.error(f"Could not parse {file_path}: {e}")
                    continue

                for node in ast.walk(tree):
                    if not isinstance(node, ast.FunctionDef) and not isinstance(
                        node, ast.AsyncFunctionDef
                    ):
                        continue

                    for decorator in node.decorator_list:
                        try:
                            if isinstance(decorator, ast.Call):
                                args_name = [
                                    arg.id for arg in decorator.args if isinstance(arg, ast.Name)
                                ]

                                if not hasattr(decorator.func, "id") or (
                                    decorator.func.id != target and target not in args_name
                                ):
                                    continue

                            elif isinstance(decorator, ast.Name):
                                if not hasattr(decorator, "id") or decorator.id != target:
                                    continue
                            else:
                                continue
                        except AttributeError:
                            continue

                        keepalive_methods.append(f"{node.name}")
                        break

        return keepalive_methods
