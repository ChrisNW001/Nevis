"""Main entry point for Nevis assistant."""

import asyncio
import logging
from dotenv import load_dotenv

from nevis.core.assistant import NevisAssistant

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run():
    """Run the Nevis assistant."""
    logger.info("Starting Nevis - Master AI Assistant")

    assistant = NevisAssistant()
    await assistant.initialize()

    logger.info("Nevis is ready")

    # Keep running until interrupted
    try:
        await assistant.run()
    except KeyboardInterrupt:
        logger.info("Shutting down Nevis...")
    finally:
        await assistant.shutdown()


def main():
    """Main entry point."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
