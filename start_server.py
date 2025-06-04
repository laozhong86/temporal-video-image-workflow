#!/usr/bin/env python3
"""
Startup script for Temporal Video Generation Application

This script starts both the Temporal worker and FastAPI callback server.
It provides command-line options for configuration and supports graceful shutdown.
"""

import argparse
import asyncio
import logging
import signal
import sys
from typing import Optional

from main import TemporalApp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ApplicationManager:
    """Manages the lifecycle of the Temporal application."""
    
    def __init__(self, temporal_host: str, namespace: str, api_port: int):
        self.temporal_app = TemporalApp(
            temporal_host=temporal_host,
            namespace=namespace,
            api_port=api_port
        )
        self.shutdown_event = asyncio.Event()
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self._shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _shutdown(self):
        """Initiate graceful shutdown."""
        self.shutdown_event.set()
    
    async def run(self):
        """Run the application with graceful shutdown support."""
        try:
            logger.info("Starting Temporal Video Generation Application...")
            
            # Start the application in a task
            app_task = asyncio.create_task(self.temporal_app.run())
            
            # Wait for either the app to complete or shutdown signal
            done, pending = await asyncio.wait(
                [app_task, asyncio.create_task(self.shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # If app task completed, check for exceptions
            if app_task in done:
                try:
                    await app_task
                except Exception as e:
                    logger.error(f"Application error: {e}")
                    raise
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
        finally:
            logger.info("Cleaning up application...")
            await self.temporal_app.cleanup()
            logger.info("Application shutdown complete")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Temporal Video Generation Application",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--temporal-host",
        default="localhost:7233",
        help="Temporal server host and port"
    )
    
    parser.add_argument(
        "--namespace",
        default="default",
        help="Temporal namespace"
    )
    
    parser.add_argument(
        "--api-port",
        type=int,
        default=8000,
        help="FastAPI server port"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    
    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Configure logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    logger.info("=" * 60)
    logger.info("Temporal Video Generation Application")
    logger.info("=" * 60)
    logger.info(f"Temporal Host: {args.temporal_host}")
    logger.info(f"Namespace: {args.namespace}")
    logger.info(f"API Port: {args.api_port}")
    logger.info(f"Log Level: {args.log_level}")
    logger.info("=" * 60)
    
    # Create and run application manager
    app_manager = ApplicationManager(
        temporal_host=args.temporal_host,
        namespace=args.namespace,
        api_port=args.api_port
    )
    
    try:
        await app_manager.run()
    except Exception as e:
        logger.error(f"Failed to run application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)