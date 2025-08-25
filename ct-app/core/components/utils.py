import ast
import logging
import os

from ..components.balance import Balance
from ..components.logs import configure_logging
from ..subgraph.entries import Safe

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
        def filter_func(item, true_value):
            if item is None:
                return False
            if not hasattr(item, "address") or not (hasattr, true_value, "address"):
                return False
            if item.address is None or true_value.node_address is None:
                return False

            return item.address.lower() == true_value.node_address.lower()

        for peer in peers:
            balance = outgoing_channel_balance.get(peer.address.native, None)
            node = next(filter(lambda n: filter_func(n, peer), nodes), None)

            peer.safe = getattr(node, "safe", Safe.default())

            peer.safe.additional_balance = Balance.zero("wxHOPR")

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

            if balance is not None:
                peer.channel_balance = balance
            else:
                peer.yearly_message_count = None

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
