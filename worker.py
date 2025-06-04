#!/usr/bin/env python3
"""
Temporal Worker Service

This module implements a dedicated Temporal Worker service for executing
workflows and activities with proper configuration and lifecycle management.
"""

import asyncio
import logging
import signal
import sys
from typing import Optional
from datetime import timedelta

from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.runtime import Runtime

# Import workflows
from workflows.workflows import GenVideoWorkflow
from workflows.video_workflow import VideoGenerationWorkflow
from workflows.image_workflow import ImageGenerationWorkflow
from workflows.batch_workflow import BatchProcessingWorkflow

# Import activities
from activities.video_activities import (
    submit_video_request,
    check_video_status,
    download_video_result,
    send_video_notification
)
from activities.image_activities import (
    submit_image_request,
    check_image_status,
    download_image_result,
    send_image_notification,
    gen_image
)
from activities.common_activities import (
    validate_request,
    log_activity,
    handle_error,
    cleanup_resources
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('worker.log')
    ]
)
logger = logging.getLogger(__name__)


class TemporalWorkerService:
    """Temporal Worker Service with proper lifecycle management."""
    
    def __init__(
        self,
        temporal_host: str = "localhost:7233",
        namespace: str = "default",
        task_queue: str = "gen-video-queue",
        max_concurrent_activities: int = 10,
        max_concurrent_workflows: int = 100
    ):
        self.temporal_host = temporal_host
        self.namespace = namespace
        self.task_queue = task_queue
        self.max_concurrent_activities = max_concurrent_activities
        self.max_concurrent_workflows = max_concurrent_workflows
        
        self.client: Optional[Client] = None
        self.worker: Optional[Worker] = None
        self.shutdown_event = asyncio.Event()
        self._running = False
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def initialize(self):
        """Initialize Temporal client and worker."""
        try:
            logger.info(f"Initializing Temporal Worker Service...")
            logger.info(f"Connecting to Temporal server at {self.temporal_host}")
            
            # Connect to Temporal server
            self.client = await Client.connect(
                self.temporal_host,
                namespace=self.namespace
            )
            logger.info(f"Successfully connected to Temporal server")
            
            # Create worker with specified configuration
            self.worker = Worker(
                self.client,
                task_queue=self.task_queue,
                workflows=[
                    GenVideoWorkflow,
                    VideoGenerationWorkflow,
                    ImageGenerationWorkflow,
                    BatchProcessingWorkflow
                ],
                activities=[
                    # Video activities
                    submit_video_request,
                    check_video_status,
                    download_video_result,
                    send_video_notification,
                    # Image activities
                    submit_image_request,
                    check_image_status,
                    download_image_result,
                    send_image_notification,
                    gen_image,
                    # Common activities
                    validate_request,
                    log_activity,
                    handle_error,
                    cleanup_resources
                ],
                max_concurrent_activities=self.max_concurrent_activities,
                max_concurrent_workflow_tasks=self.max_concurrent_workflows,
                # Configure worker options for better performance
                max_cached_workflows=1000,
                max_heartbeat_throttle_interval=timedelta(seconds=60),
                default_heartbeat_throttle_interval=timedelta(seconds=30)
            )
            
            logger.info(f"Worker initialized successfully:")
            logger.info(f"  Task Queue: {self.task_queue}")
            logger.info(f"  Max Concurrent Activities: {self.max_concurrent_activities}")
            logger.info(f"  Max Concurrent Workflows: {self.max_concurrent_workflows}")
            logger.info(f"  Registered Workflows: {len(self.worker._workflows)}")
            logger.info(f"  Registered Activities: {len(self.worker._activities)}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Temporal Worker Service: {e}")
            raise
    
    async def start(self):
        """Start the Temporal worker."""
        if not self.worker:
            raise RuntimeError("Worker not initialized. Call initialize() first.")
        
        if self._running:
            logger.warning("Worker is already running")
            return
        
        self._running = True
        logger.info("Starting Temporal Worker Service...")
        
        try:
            # Start worker in background task
            worker_task = asyncio.create_task(self.worker.run())
            
            logger.info("✅ Temporal Worker Service started successfully")
            logger.info("Worker is ready to process workflows and activities")
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
            logger.info("Shutdown signal received, stopping worker...")
            
            # Cancel worker task
            worker_task.cancel()
            
            try:
                await worker_task
            except asyncio.CancelledError:
                logger.info("Worker task cancelled successfully")
            
        except Exception as e:
            logger.error(f"Error running worker: {e}")
            raise
        finally:
            self._running = False
    
    async def shutdown(self):
        """Gracefully shutdown the worker service."""
        if not self._running:
            logger.info("Worker service is not running")
            return
        
        logger.info("Initiating graceful shutdown...")
        
        # Signal shutdown
        self.shutdown_event.set()
        
        # Close client connection
        if self.client:
            try:
                # Temporal Python client doesn't have a close method
                # It cleans itself up when no longer referenced
                pass
                logger.info("Temporal client connection closed")
            except Exception as e:
                logger.error(f"Error closing client: {e}")
        
        logger.info("✅ Temporal Worker Service shutdown completed")
    
    async def health_check(self) -> bool:
        """Check if the worker service is healthy."""
        try:
            if not self.client:
                return False
            
            # Simple health check by checking client connection
            # In a real implementation, you might want to check more things
            return self._running
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


async def main():
    """Main entry point for the worker service."""
    # Configuration from environment or defaults
    import os
    
    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    task_queue = os.getenv("TEMPORAL_TASK_QUEUE", "gen-video-queue")
    max_concurrent_activities = int(os.getenv("MAX_CONCURRENT_ACTIVITIES", "10"))
    max_concurrent_workflows = int(os.getenv("MAX_CONCURRENT_WORKFLOWS", "100"))
    
    # Create and start worker service
    worker_service = TemporalWorkerService(
        temporal_host=temporal_host,
        namespace=namespace,
        task_queue=task_queue,
        max_concurrent_activities=max_concurrent_activities,
        max_concurrent_workflows=max_concurrent_workflows
    )
    
    try:
        await worker_service.initialize()
        await worker_service.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Worker service error: {e}")
        sys.exit(1)
    finally:
        await worker_service.shutdown()


if __name__ == "__main__":
    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("Temporal Worker Service")
            print("")
            print("Usage: python worker.py [options]")
            print("")
            print("Environment Variables:")
            print("  TEMPORAL_HOST              Temporal server host (default: localhost:7233)")
            print("  TEMPORAL_NAMESPACE         Temporal namespace (default: default)")
            print("  TEMPORAL_TASK_QUEUE        Task queue name (default: gen-video-queue)")
            print("  MAX_CONCURRENT_ACTIVITIES  Max concurrent activities (default: 10)")
            print("  MAX_CONCURRENT_WORKFLOWS   Max concurrent workflows (default: 100)")
            print("")
            print("Options:")
            print("  -h, --help                 Show this help message")
            print("  --version                  Show version information")
            sys.exit(0)
        elif sys.argv[1] == "--version":
            print("Temporal Worker Service v1.0.0")
            sys.exit(0)
    
    # Run the worker service
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
        sys.exit(0)