from .entry import SubgraphEntry

class Ticket(SubgraphEntry):
    """
    An Ticket represents a single entry in the subgraph.
    """

    def __init__(self, id: str, value: str, timestamp: str):
        """
        Create a new Ticket.
        :param id: The address of the ticket.
        :param value: The value of the ticket.
        :param timestamp: The timestamp of the ticket redemption.
        """

        self.id = id
        self.value = float(value)
        self.timestamp = timestamp


    @classmethod
    def fromSubgraphResult(cls, ticket: dict):
        """
        Create a new Ticket from the specified subgraph result.
        :param node: The subgraph result to create the Ticket from.
        """
        return cls(
            ticket["id"],
            ticket["amount"],
            ticket["redeemedAt"],
        )
