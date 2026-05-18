from .peers_discovery import PeerDiscoveryMixin
from .peer_relay import PeerRelayMixin
from .network_sync import NetworkSyncMixin


class PeersMixin(PeerDiscoveryMixin, NetworkSyncMixin, PeerRelayMixin):
    pass
