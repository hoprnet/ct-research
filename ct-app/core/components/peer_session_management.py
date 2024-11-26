import socket

from core.api.protocol import Protocol
from core.api.response_objects import Session


class PeerSessionManagement:

    def __init__(self, session: Session, ip: str):
        self.session = session
        self.ip = ip
        try:
            self.socket = self.create_socket()
        except (socket.error, ValueError) as e:
            raise ValueError(f"Error while creating socket: {e}")

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
        return (self.ip, self.session.port)

    def create_socket(self, timeout: int = 60):
        if self.session.protocol == Protocol.TCP.value:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        elif self.session.protocol == Protocol.UDP.value:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        else:
            raise ValueError(f"Invalid protocol: {self.session.protocol}")

        if self.session.protocol == Protocol.TCP.value:
            s.connect(self.address)
        s.settimeout(timeout)

        return s

    def __del__(self):
        if hasattr(self, "socket"):
            self.socket.close()
