from .runtime_state import NodeRuntimeState


class PeerAllocationMixin(NodeRuntimeState):
    def reconcile_peer_allocations(self) -> None:
        reachable_nodes = set(self.peers.keys())
        self.network_state.reachable_nodes = reachable_nodes

        safe_counts: dict[str, int] = {}
        for node_address in reachable_nodes:
            safe_address = self.network_state.node_to_safe.get(node_address)
            if safe_address is None:
                continue
            safe_counts[safe_address] = safe_counts.get(safe_address, 0) + 1

        for peer in self.peers.values():
            safe_address = self.network_state.node_to_safe.get(peer.address.native)
            safe_balance = (
                self.network_state.safe_balances.get(safe_address) if safe_address else None
            )
            count = safe_counts.get(safe_address, 0) if safe_address else 0
            peer.set_allocation(safe_address, safe_balance, count)
            channel_balance = self.network_state.outgoing_channel_balances.get(peer.address.native)
            if channel_balance is not None:
                peer.channel_balance = channel_balance
