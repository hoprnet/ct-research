from .database_connection import DatabaseConnection
from .models import Peer


class Utils:
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
