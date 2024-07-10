from prometheus_client import Gauge

TICKET_PRICE = Gauge("ticket_price", "Ticket price")
TICKET_WINNING_PROB = Gauge("ticket_winning_prob", "Ticket winning probability")


class Budget:
    def __init__(self):
        self.ticket_price = 1
        self.winning_probability = 1

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
            TICKET_PRICE.set(value)

    @winning_probability.setter
    def winning_probability(self, value):
        if value is not None:
            self._winning_probability = value
            TICKET_WINNING_PROB.set(value)
