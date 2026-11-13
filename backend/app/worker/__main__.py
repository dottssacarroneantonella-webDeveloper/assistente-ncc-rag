"""Worker separato: consuma gli eventi da RabbitMQ e prepara le risposte.

Avvio:  python -m app.worker   (con QUEUE_BACKEND=rabbitmq)
Si ferma in modo pulito con SIGINT/SIGTERM: i messaggi non confermati tornano in coda.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import Database
from app.queue.factory import create_queue
from app.rag.engine import RagEngine
from app.worker.processor import MessageProcessor
from app.worker.runtime import build_channels

logger = logging.getLogger("app.worker")


async def run() -> None:
    settings = get_settings()
    configure_logging()
    if settings.queue_backend != "rabbitmq":
        raise SystemExit("Il worker separato richiede QUEUE_BACKEND=rabbitmq")
    db = Database(settings)
    if settings.auto_create_schema:
        Base.metadata.create_all(db.engine)
    channels = build_channels(settings)
    processor = MessageProcessor(db, RagEngine(settings), settings, channels)
    queue = create_queue(settings)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    await queue.start_consuming(processor.handle, processor.on_failure)
    logger.info("Worker avviato, in attesa di messaggi")
    try:
        await stop.wait()
    finally:
        await queue.close()
        for channel in channels.values():
            await channel.close()
        db.engine.dispose()
        logger.info("Worker fermato")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
