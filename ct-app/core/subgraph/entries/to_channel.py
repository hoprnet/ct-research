from .entry import SubgraphEntry
from .ticket import Ticket

class ToChannel(SubgraphEntry):
    """
    An FromChannel represents a single entry in the subgraph.
    """

    def __init__(self, id: str, source: str, redeemed_ticket_count: int, tickets: list[Ticket]):
        """
        Create a new FromChannel.
        :param id: The id of the channel.
        :param source: The address of the source.
        :param redeemed_ticket_count: The number of tickets redeemed.
        :param tickets: A list of Ticket objects.
        """

        self.address = self.checksum(id)
        self.source = self.checksum(source)
        self.redeemed_ticket_count = int(redeemed_ticket_count)
        self.tickets = tickets


    @property
    def total_value(self):
        """
        Get the total value of all tickets in the channel.
        """
        return sum([t.value for t in self.tickets if t.value is not None])
        
    @classmethod
    def fromSubgraphResult(cls, channel: dict):
        """
        Create a new FromChannel from the specified subgraph result.
        :param node: The subgraph result to create the FromChannel from.
        """
        return cls(
            channel["id"],
            channel["source"]["id"],
            channel["redeemedTicketCount"],
            [Ticket.fromSubgraphResult(t) for t in channel["tickets"]]
        )
