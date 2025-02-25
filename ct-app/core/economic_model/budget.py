from ..components.metrics import TICKET_STATS


class Budget:
    def __init__(self):
        self.ticket_price = None

    @property
    def ticket_price(self):
        return self._ticket_price

    @ticket_price.setter
    def ticket_price(self, value):
        if value is not None:
            self._ticket_price = value
            TICKET_STATS.labels("price").set(value)