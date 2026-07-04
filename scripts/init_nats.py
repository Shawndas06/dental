import asyncio

from shared.config import get_settings
from shared.nats import EventPublisher


async def main() -> None:
    publisher = EventPublisher(get_settings().nats_url)
    await publisher.connect()
    await publisher.close()
    print("NATS JetStream streams are ready")


if __name__ == "__main__":
    asyncio.run(main())
