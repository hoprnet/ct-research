import asyncio
import logging
import socket
from datetime import datetime
from typing import Optional, Union

from prometheus_client import Gauge, Histogram

from ..api.hoprd_api import HoprdAPI
from ..api.response_objects import Channel, Session, SessionFailure
from ..components.balance import Balance
from ..components.logs import configure_logging
from ..components.messages.message_format import MessageFormat

CHANNELS_OPS = Gauge("ct_channel_operation", "Channel operation", ["op", "success"])
MESSAGES_RTT = Histogram(
    "ct_messages_delays",
    "Messages delays",
    ["relayer"],
    buckets=[0.5, 0.75, 1, 2, 3, 4, 5],
)
MESSAGES_STATS = Gauge("ct_messages_stats", "", ["type", "relayer"])
MESSAGE_SENDING_REQUEST = Gauge("ct_message_sending_request", "", ["relayer"])
SESSION_OPS = Gauge("ct_session_operation", "Session operation", ["relayer", "op", "success"])


configure_logging()
logger = logging.getLogger(__name__)


class NodeHelper:
    @classmethod
    async def open_channel(cls, api: HoprdAPI, address: str, amount: Balance):
        log_params = {"to": address, "amount": amount.as_str}
        logger.debug("Opening channel", log_params)
        channel = await api.open_channel(address, amount)

        if channel is not None:
            logger.info("Opened channel", log_params)
        else:
            logger.warning(f"Failed to open channel to {address}", log_params)
        CHANNELS_OPS.labels("opened", "yes" if channel else "no").inc()

    @classmethod
    async def close_channel(cls, api: HoprdAPI, channel: Channel, type: str):
        logs_params = {"channel": channel.id}
        logger.debug(f"Closing {type} channel", logs_params)

        ok = await api.close_channel(channel.id)

        if ok:
            logger.info(f"Closed {type} channel", logs_params)
        else:
            logger.warning(f"Failed to close {type}", logs_params)
        CHANNELS_OPS.labels(type, "yes" if ok else "no").inc()

    @classmethod
    async def fund_channel(cls, api: HoprdAPI, channel: Channel, amount: Balance):
        logs_params = {"channel": channel.id, "amount": amount.as_str}
        logger.debug("Funding channel", logs_params)

        ok = await api.fund_channel(channel.id, amount)

        if ok:
            logger.info("Fund channel", logs_params)
        else:
            logger.warning("Failed to fund channel", logs_params)
        CHANNELS_OPS.labels("fund", "yes" if ok else "no").inc()

    @classmethod
    async def open_session(
        cls, api: HoprdAPI, destination: str, relayer: str, listen_host: str
    ) -> Optional[Session]:
        logs_params = {
            "to": destination,
            "relayer": relayer,
            "listen_host": listen_host,
        }
        logger.debug("Opening session", logs_params)

        session = await api.post_udp_session(destination, relayer, listen_host)
        match session:
            case Session():
                logger.info("Opened session", {**logs_params, **session.as_dict})
                SESSION_OPS.labels(relayer, "opened", "yes").inc()
                return session
            case SessionFailure():
                logger.warning("Failed to open a session", {**logs_params, **session.as_dict})
                SESSION_OPS.labels(relayer, "opened", "no").inc()
                return None

    @classmethod
    async def close_session(
        cls,
        api: HoprdAPI,
        session: Session,
        relayer: Optional[str] = None,
    ):
        logs_params = {"relayer": relayer if relayer else ""}

        logger.debug("Closing the session", logs_params)

        ok = await api.close_session(session)

        if ok:
            logger.info("Closed the session", logs_params)
        else:
            logger.warning("Failed to close the session", logs_params)

        if relayer:
            SESSION_OPS.labels(relayer, "closed", "yes" if ok else "no").inc()

    @classmethod
    async def send_batch_messages(
        cls, api: HoprdAPI, sender: str, destination: str, message: MessageFormat
    ):
        async with SocketThroughNetwork(api, destination, message.relayer) as socket:
            if not socket:
                return

            message.sender = sender
            message.packet_size = socket.session.payload

            # taking into account the session opening packets
            batch_size: int = message.batch_size - 2

            [socket.send(message) for _ in range(batch_size)]
            await socket.receive(message.packet_size, batch_size * message.packet_size)


class SocketThroughNetwork:
    def __init__(
        self,
        api: HoprdAPI,
        destination: str,
        relayer: str,
        listen_host: Optional[str] = None,
        timeout: Optional[float] = 0.05,
    ):
        self.api = api
        self.destination = destination
        self.relayer = relayer
        self.listen_host = listen_host if listen_host else "127.0.0.1"
        self.timeout = timeout
        self.session = None
        self.socket = None

    async def __aenter__(self):
        self.session = await NodeHelper.open_session(
            self.api, self.destination, self.relayer, self.listen_host
        )

        if not self.session:
            return None

        try:
            self.socket = self.create_socket(self.timeout)
        except (socket.error, ValueError) as e:
            raise ValueError(f"Error while creating socket: {e}")

        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.session:
            await NodeHelper.close_session(self.api, self.session, self.relayer)
        else:
            return

        try:
            self.close_socket()
        except Exception as e:
            self.socket = None
            raise ValueError(f"Error closing socket: {e}") from e
        finally:
            self.socket = None

    def create_socket(self, timeout: Optional[float] = None) -> socket.socket:
        s: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)

        return s

    def close_socket(self):
        if self.socket:
            self.socket.close()

    def send(self, message: Union[MessageFormat, bytes]) -> bytes:
        """
        Sends data to the peer.
        """
        if isinstance(message, MessageFormat):
            MESSAGE_SENDING_REQUEST.labels(message.relayer).inc()

        payload: bytes = message.bytes() if isinstance(message, MessageFormat) else message
        data = self.socket.sendto(payload, (self.listen_host, self.session.port))

        if isinstance(message, MessageFormat):
            MESSAGES_STATS.labels("sent", message.relayer).inc()

        return data

    async def receive(self, chunk_size: int, total_size: int, timeout: float = 2) -> int:
        """
        Receives data from the peer. In case off multiple message in the same packet, which should
        not happen, they are already split and returned as a list.
        """
        recv_data = b""

        start_time = datetime.now().timestamp()

        while len(recv_data) < total_size:
            if (datetime.now().timestamp() - start_time) >= timeout:
                break

            try:
                recv_data += self.socket.recvfrom(chunk_size)[0]
            except socket.timeout:
                await asyncio.sleep(0.02)
                pass
            except ConnectionResetError:
                break

        now = int(datetime.now().timestamp() * 1000)
        recv_size: int = len(recv_data)

        try:
            recv_data: list[str] = [
                item for item in recv_data.decode().split(b"\0".decode()) if len(item) > 0
            ]
        except Exception:
            logger.error("Failed to decode received data")
        else:
            for data in recv_data:
                try:
                    message = MessageFormat.parse(data)
                except ValueError as e:
                    logger.error(f"Failed to parse message: {e}")
                    continue

                rtt = (now - message.timestamp) / 1000
                MESSAGES_STATS.labels("received", message.relayer).inc()
                MESSAGES_RTT.labels(message.relayer).observe(rtt)

        return recv_size
