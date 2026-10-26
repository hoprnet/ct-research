from .peers_discovery import PeerDiscoveryMixin
from .peer_relay import PeerRelayMixin


class PeersMixin(PeerDiscoveryMixin, PeerRelayMixin):
    pass
