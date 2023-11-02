from .address import Address


class Peer:
    def __init__(self, address: Address):
        self.address = address

    def __repr__(self):
        return f"Peer(address: {self.address})"
