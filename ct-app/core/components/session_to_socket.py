import socket

from core.api.protocol import Protocol
from core.api.response_objects import Session


class SessionToSocket:
    def __init__(self, session: Session, timeout: int = 5):
        self.session = session
        self.connect_address = session.ip

        try:
            self.socket, self.conn = self.create_socket(timeout)
        except (socket.error, ValueError) as e:
            raise ValueError(f"Error while creating socket: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.socket.close()
        self.socket = None

    @property
    def port(self) -> int:
        """
        Returns the session port number.
        """
        return self.session.port

    @property
    def address(self):
        """
        Returns the socket address tuple.
        """

        return (self.connect_address, self.session.port)

    def create_socket(self, timeout: int = 1):
        if self.session.protocol == Protocol.UDP:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        else:
            raise ValueError(f"Invalid protocol: {self.session.protocol}")

        s.settimeout(timeout)

        conn = None

        return s, conn

    def send(self, data: bytes) -> int:
        """
        Sends data to the peer.
        """
        if self.session.protocol == Protocol.UDP:
            return self.socket.sendto(data, self.address)
        else:
            raise ValueError(f"Invalid protocol: {self.session.protocol}")

    def receive(self, size: int) -> bytes:
        """
        Receives data from the peer.
        """
        if self.session.protocol != Protocol.UDP:
            raise ValueError(f"Invalid protocol: {self.session.protocol}")

        try:
            data, _ = self.socket.recvfrom(size)
        except Exception:
            data = b""
            
        return data
