from __future__ import annotations

from typing import Protocol

from ..config_parser import Parameters
from ..services.blokli_repository import GraphqlNetworkRepository
from ..services.blokli_repository import NetworkRepository
from ..types.message_queue import MessageQueue


class RuntimeNode(Protocol):
    blokli_repository: NetworkRepository


class NodeRuntimeFactory:
    @staticmethod
    def configure_runtime(node: RuntimeNode, params: Parameters) -> None:
        MessageQueue.configure_maxsize(params.sessions.message_queue_maxsize)
        node.blokli_repository = GraphqlNetworkRepository(params.blokli.url, params.blokli.token)
