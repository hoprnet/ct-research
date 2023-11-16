import asyncio

from celery import Celery
from core.components.hoprd_api import HoprdAPI
from database import DatabaseConnection, Peer


class Utils:
    @classmethod
    def createBatches(cls, total_count: int, batch_size: int) -> list[int]:
        if total_count <= 0:
            return []

        full_batches: int = total_count // batch_size
        remainder: int = total_count % batch_size

        return [batch_size] * full_batches + [remainder] * bool(remainder)

    @classmethod
    def peerIDToInt(cls, peer_id: str) -> int:
        with DatabaseConnection() as session:
            existing_peer = session.query(Peer).filter_by(peer_id=peer_id).first()

            if existing_peer:
                return existing_peer.id
            else:
                new_peer = Peer(peer_id=peer_id)
                session.add(new_peer)
                session.commit()
                return new_peer.id

    @classmethod
    async def delayedMessageSend(
        cls,
        api: HoprdAPI,
        recipient: str,
        relayer: str,
        message: str,
        tag: int,
        sleep: float,
    ):
        await asyncio.sleep(sleep)

        return await api.send_message(recipient, message, [relayer], tag)

    @classmethod
    def taskSendMessage(
        cls,
        app: Celery,
        relayer_id: str,
        expected: int,
        ticket_price: int,
        timestamp: float = None,
        attempts: int = 0,
        task_name: str = "send_1_hop_message",
    ):
        app.send_task(
            task_name,
            args=(relayer_id, expected, ticket_price, timestamp, attempts),
            queue="send_messages",
        )

    @classmethod
    def taskStoreFeedback(
        cls,
        app: Celery,
        relayer_id: str,
        node_peer_id: str,
        expected: int,
        issued: float,
        relayed: int,
        send_status: str,
        timestamp: float,
    ):
        app.send_task(
            "feedback_task",
            args=(
                relayer_id,
                node_peer_id,
                expected,
                issued,
                relayed,
                send_status.value,
                timestamp,
            ),
            queue="feedback",
        )
