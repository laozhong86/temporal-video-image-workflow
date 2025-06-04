"""Main application entry point for Temporal workflows."""

import asyncio
import logging
import threading
import uvicorn
from datetime import timedelta
from typing import Dict, Any

from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker

# Import workflows
from workflows.video_workflow import VideoGenerationWorkflow
from workflows.image_workflow import ImageGenerationWorkflow
from workflows.batch_workflow import BatchProcessingWorkflow
from workflows.kling_video_workflow import KlingVideoGenerationWorkflow
from workflows import GenVideoWorkflow

# Import activities
from activities.video_activities import (
    request_video,
    check_video_generation_status,
    download_generated_video,
    submit_video_request,
    check_video_status,
    download_video_result,
    send_video_notification
)
from activities.image_activities import (
    request_image,
    check_image_generation_status,
    download_generated_image,
    submit_image_request,
    check_image_status,
    download_image_result,
    send_image_notification,
    gen_image
)
from activities.batch_activities import (
    process_batch_request,
    check_batch_status,
    download_batch_results
)
from activities.common_activities import (
    validate_request,
    log_activity,
    handle_error,
    cleanup_resources
)
from models.video_request import VideoRequest
from models.image_request import ImageRequest
from models.batch_request import BatchRequest
from api_server import app as fastapi_app, signal_sender

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TemporalApp:
    """Main application class for managing Temporal workflows."""
    
    def __init__(self, temporal_host: str = "localhost:7233", namespace: str = "default", api_port: int = 8000):
        self.temporal_host = temporal_host
        self.namespace = namespace
        self.api_port = api_port
        self.client: Client = None
        self.worker: Worker = None
        self.api_server_thread = None
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def start_api_server(self):
        """Start FastAPI server in a separate thread."""
        def run_server():
            # Update signal sender configuration
            signal_sender.temporal_host = self.temporal_host
            signal_sender.namespace = self.namespace
            
            self.logger.info(f"Starting FastAPI server on port {self.api_port}")
            uvicorn.run(
                fastapi_app,
                host="0.0.0.0",
                port=self.api_port,
                log_level="info"
            )
        
        self.api_server_thread = threading.Thread(target=run_server, daemon=True)
        self.api_server_thread.start()
        self.logger.info(f"FastAPI server thread started on port {self.api_port}")
    
    async def initialize(self):
        """Initialize Temporal client and worker."""
        try:
            # Connect to Temporal server
            self.client = await Client.connect(
                self.temporal_host,
                namespace=self.namespace
            )
            logger.info(f"Connected to Temporal server at {self.temporal_host}")
            
            # Create worker
            self.worker = Worker(
                self.client,
                task_queue="generation-queue",
                workflows=[
                    VideoGenerationWorkflow,
                    ImageGenerationWorkflow,
                    BatchProcessingWorkflow,
                    KlingVideoGenerationWorkflow,
                    GenVideoWorkflow
                ],
                activities=[
                    # New video activities
                    request_video,
                    check_video_generation_status,
                    download_generated_video,
                    
                    # Original video activities
                    submit_video_request,
                    check_video_status,
                    download_video_result,
                    send_video_notification,
                    
                    # New image activities
                    request_image,
                    check_image_generation_status,
                    download_generated_image,
                    
                    # Original image activities
                    submit_image_request,
                    check_image_status,
                    download_image_result,
                    send_image_notification,
                    gen_image,
                    
                    # Batch activities
                    process_batch_request,
                    check_batch_status,
                    download_batch_results,
                    
                    # Common activities
                    validate_request,
                    log_activity,
                    handle_error,
                    cleanup_resources
                ]
            )
            logger.info("Worker initialized with workflows and activities")
            
        except Exception as e:
            logger.error(f"Failed to initialize Temporal app: {e}")
            raise
    
    async def start_worker(self):
        """Start the Temporal worker."""
        if not self.worker:
            raise RuntimeError("Worker not initialized. Call initialize() first.")
        
        logger.info("Starting Temporal worker...")
        await self.worker.run()
    
    async def submit_video_workflow(self, request_data: Dict[str, Any]) -> str:
        """Submit a video generation workflow.
        
        Args:
            request_data: Video generation request data
            
        Returns:
            Workflow ID
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        
        workflow_id = f"video_gen_{request_data.get('request_id', 'unknown')}"
        
        handle = await self.client.start_workflow(
            VideoGenerationWorkflow.run,
            args=[request_data],
            id=workflow_id,
            task_queue="generation-queue",
            execution_timeout=timedelta(hours=3)
        )
        
        logger.info(f"Started video generation workflow: {workflow_id}")
        return workflow_id
    
    async def submit_image_workflow(self, request_data: Dict[str, Any]) -> str:
        """Submit an image generation workflow.
        
        Args:
            request_data: Image generation request data
            
        Returns:
            Workflow ID
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        
        workflow_id = f"image_gen_{request_data.get('request_id', 'unknown')}"
        
        handle = await self.client.start_workflow(
            ImageGenerationWorkflow.run,
            args=[request_data],
            id=workflow_id,
            task_queue="generation-queue",
            execution_timeout=timedelta(hours=2)
        )
        
        logger.info(f"Started image generation workflow: {workflow_id}")
        return workflow_id
    
    async def submit_batch_workflow(self, batch_data: Dict[str, Any]) -> str:
        """Submit a batch processing workflow.
        
        Args:
            batch_data: Batch processing request data
            
        Returns:
            Workflow ID
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        
        workflow_id = f"batch_proc_{batch_data.get('batch_id', 'unknown')}"
        
        handle = await self.client.start_workflow(
            BatchProcessingWorkflow.run,
            args=[batch_data],
            id=workflow_id,
            task_queue="generation-queue",
            execution_timeout=timedelta(hours=6)
        )
        
        logger.info(f"Started batch processing workflow: {workflow_id}")
        return workflow_id
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get the status of a workflow.
        
        Args:
            workflow_id: ID of the workflow
            
        Returns:
            Workflow status information
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        
        try:
            handle = self.client.get_workflow_handle(workflow_id)
            
            # Try to query the workflow status
            try:
                status = await handle.query("get_status")
                return {
                    "workflow_id": workflow_id,
                    "status": "running",
                    "details": status
                }
            except Exception:
                # If query fails, workflow might be completed or failed
                try:
                    result = await handle.result()
                    return {
                        "workflow_id": workflow_id,
                        "status": "completed",
                        "result": result
                    }
                except Exception as e:
                    return {
                        "workflow_id": workflow_id,
                        "status": "failed",
                        "error": str(e)
                    }
        
        except Exception as e:
            return {
                "workflow_id": workflow_id,
                "status": "unknown",
                "error": str(e)
            }
    
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow.
        
        Args:
            workflow_id: ID of the workflow to cancel
            
        Returns:
            True if cancellation was successful
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        
        try:
            handle = self.client.get_workflow_handle(workflow_id)
            await handle.cancel()
            logger.info(f"Cancelled workflow: {workflow_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel workflow {workflow_id}: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown the Temporal app."""
        if self.worker:
            logger.info("Shutting down worker...")
            # Worker shutdown is handled by the run() method when interrupted
        
        if self.client:
            logger.info("Closing client connection...")
            # Client doesn't need explicit shutdown in current version


async def main():
    """Main function to run the Temporal worker and FastAPI server."""
    app = TemporalApp()
    
    try:
        # Run the application (includes initialization, FastAPI server, and worker)
        await app.run()
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise
    finally:
        await app.cleanup()
        logger.info("Application shutdown complete")


if __name__ == "__main__":
    # Example usage and testing
    async def test_workflows():
        """Test function to demonstrate workflow usage."""
        app = TemporalApp()
        await app.initialize()
        
        # Example video request
        video_request = {
            "request_id": "test_video_001",
            "type": "video",
            "prompt": "A beautiful sunset over the ocean",
            "duration": 10,
            "resolution": "1920x1080",
            "fps": 30,
            "style": "realistic",
            "webhook_url": "https://example.com/webhook",
            "user_id": "user123"
        }
        
        # Example image request
        image_request = {
            "request_id": "test_image_001",
            "type": "image",
            "prompt": "A majestic mountain landscape",
            "width": 1024,
            "height": 1024,
            "style": "photorealistic",
            "num_images": 2,
            "webhook_url": "https://example.com/webhook",
            "user_id": "user123"
        }
        
        # Example batch request
        batch_request = {
            "batch_id": "test_batch_001",
            "processing_strategy": "parallel",
            "max_concurrent": 3,
            "requests": [video_request, image_request]
        }
        
        try:
            # Submit workflows
            video_id = await app.submit_video_workflow(video_request)
            image_id = await app.submit_image_workflow(image_request)
            batch_id = await app.submit_batch_workflow(batch_request)
            
            print(f"Submitted workflows:")
            print(f"  Video: {video_id}")
            print(f"  Image: {image_id}")
            print(f"  Batch: {batch_id}")
            
            # Check status
            await asyncio.sleep(5)
            
            video_status = await app.get_workflow_status(video_id)
            image_status = await app.get_workflow_status(image_id)
            batch_status = await app.get_workflow_status(batch_id)
            
            print(f"\nWorkflow statuses:")
            print(f"  Video: {video_status}")
            print(f"  Image: {image_status}")
            print(f"  Batch: {batch_status}")
            
        except Exception as e:
            print(f"Test error: {e}")
        
        await app.shutdown()
    
    # Run main worker or test
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(test_workflows())
    else:
        asyncio.run(main())