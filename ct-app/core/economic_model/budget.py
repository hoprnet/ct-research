from prometheus_client import Gauge

TICKET_STATS = Gauge("ct_ticket_stats", "Ticket stats", ["type"])


class Budget:
    def __init__(self):
        self.ticket_price = None
        self.winning_probability = None

    @property
    def ticket_price(self):
        return self._ticket_price

    @property
    def winning_probability(self):
        return self._winning_probability

    @ticket_price.setter
    def ticket_price(self, value):
        if value is not None:
            self._ticket_price = value
            TICKET_STATS.labels("price").set(value)

    @winning_probability.setter
    def winning_probability(self, value):
        if value is not None:
            self._winning_probability = value
            TICKET_STATS.labels("win_prob").set(value)
