class Address:
    def __init__(self, id: str, address: str):
        self.id = id
        self.address = address

    @property
    def short_id(self):
        if len(self.id) <= 10:
            return self.id

        return self.id[-5:]

    def __eq__(self, other):
        return self.id == other.id and self.address == other.address

    def __hash__(self):
        return hash((self.id, self.address))

    def __repr__(self):
        return f"Address({self.id}, {self.address})"
