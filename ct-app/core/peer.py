from . import utils as utils


class Peer:
    """Class description."""

    def __init__(self, id: str):
        """
        Initialisation of the class.
        """
        self.id = id

    def __str__(self):
        return f"Peer(id='{self.id}')"

    def __repr__(self):
        return str(self)

    @classmethod
    def random(cls):
        return cls(utils.random_string(5))
