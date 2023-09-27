class Peer:
    def __init__(self, id: str, address: str):
        """
        Initialisation of the class.
        """
        self.id = id
        self.address = address

    @property
    def short_id(self):
        return self.id[-5:]
