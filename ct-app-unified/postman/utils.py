import asyncio

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
