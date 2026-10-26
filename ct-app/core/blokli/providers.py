from .blokli_provider import BlokliProvider
from .entries import BlokliChannelGraphEntry, BlokliTicketParameters


class TicketParametersSubscription(BlokliProvider[BlokliTicketParameters]):
    query_file: str = "queries/ticket_parameters.graphql"


class ChannelGraphSubscription(BlokliProvider[BlokliChannelGraphEntry]):
    query_file: str = "queries/channel_graph.graphql"
