from __future__ import annotations

from typing import Protocol

from ..config_parser import Parameters
from ..services.blokli_repository import GraphqlNetworkRepository
from ..services.blokli_repository import NetworkRepository
from ..types.network_state import NetworkState
from ..services.network_state_service import NetworkStateService
from ..services.network_sync_orchestrator import NetworkSyncOrchestrator
from ..types.message_queue import MessageQueue
from ..services.network_update_coordinator import NetworkUpdateCoordinator
from ..services.send_plan_coordinator import SendPlanCoordinator
from ..services.session_lifecycle_coordinator import SessionLifecycleCoordinator
from ..services.shutdown_coordinator import ShutdownCoordinator


class RuntimeNode(Protocol):
    network_state: NetworkState
    blokli_repository: NetworkRepository
    network_state_service: NetworkStateService
    network_sync_orchestrator: NetworkSyncOrchestrator
    network_update_coordinator: NetworkUpdateCoordinator
    send_plan_coordinator: SendPlanCoordinator
    session_lifecycle_coordinator: SessionLifecycleCoordinator
    shutdown_coordinator: ShutdownCoordinator


class NodeRuntimeFactory:
    @staticmethod
    def configure_runtime(node: RuntimeNode, params: Parameters) -> None:
        MessageQueue.configure_maxsize(params.sessions.message_queue_maxsize)

        blokli_url = params.blokli.url
        blokli_token = params.blokli.token

        repository = GraphqlNetworkRepository(blokli_url, blokli_token)
        state_service = NetworkStateService(node.network_state, repository)
        orchestrator = NetworkSyncOrchestrator(repository, state_service)

        node.blokli_repository = repository
        node.network_state_service = state_service
        node.network_sync_orchestrator = orchestrator
