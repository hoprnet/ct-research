import socket

from core.api.protocol import Protocol
from core.baseclass import Base
from core.components import Singleton
from core.components.decorators import flagguard, formalin


class TCPUDPServer(Base, metaclass=Singleton):
    def __init__(self, protocol: Protocol, packet_size: int, batch_size: int):
        self.protocol = protocol
        self.socket = None
        self.conn = None  # Only used for TCP connection
        self.recv_buffer = packet_size * batch_size
        self.packet_size = packet_size
        self.params = None
        self.setup()

    @property
    def running(self):
        return self.socket is not None

    @property
    def port(self):
        if self.socket is None:
            return None
        return self.socket.getsockname()[1]

    def setup(self):
        if self.protocol is Protocol.TCP:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        elif self.protocol is Protocol.UDP:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        else:
            raise ValueError(f"Invalid protocol: {self.protocol}")

        self.socket.bind(("127.0.0.1", 12000))
        self.socket.settimeout(0.1)

        if self.protocol is Protocol.TCP:
            self.socket.listen()
            self.conn = self.socket.accept()[0]

    def stop(self):
        if self.protocol is Protocol.TCP:
            self.conn.close()
            self.conn = None
        self.socket.close()
        self.socket = None

    @flagguard
    @formalin
    async def listen_to_tcp_socket(self):

        data = self.conn.recv(self.recv_buffer)
        if len(data) == 0:
            return
        self.server_data(data)

    @flagguard
    @formalin
    async def listen_to_udp_socket(self):
        print(f"Doing it")
        try:
            data = self.socket.recv(self.recv_buffer)
        except socket.timeout:
            return
        else:
            self.server_data(data)

    def server_data(self, data: bytes):
        local_packet_count = len(data) // self.packet_size
        self.info(f"Received {local_packet_count} packet.")
