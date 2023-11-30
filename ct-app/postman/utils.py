import asyncio

from core.components.hoprd_api import MESSAGE_TAG, HoprdAPI
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
    async def send_messages_in_batches(
        cls,
        api: HoprdAPI,
        relayer: str,
        expected_count: int,
        recipient: str,
        timestamp: float,
        batch_size: int,
        delay_between_two_messages: float,
        message_delivery_timeout: float,
    ):
        relayed_count = 0
        issued_count = 0

        tag = MESSAGE_TAG + cls.peerIDToInt(relayer)

        batches = cls.createBatches(expected_count, batch_size)

        for batch_index, batch in enumerate(batches):
            tasks = set[asyncio.Task]()
            for it in range(batch):
                global_index = it + batch_index * batch_size
                message = f"{relayer}//{timestamp}-{global_index + 1}/{expected_count}"
                sleep = it * delay_between_two_messages

                tasks.add(
                    asyncio.create_task(
                        cls.delayedMessageSend(
                            api, recipient, relayer, message, tag, sleep
                        )
                    )
                )

            issued_count += sum(await asyncio.gather(*tasks))

            await asyncio.sleep(message_delivery_timeout)

            messages = await api.messages_pop_all(tag)
            relayed_count += len(messages)

        return relayed_count, issued_count
