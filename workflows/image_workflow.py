"""Image generation workflow using Temporal."""

import asyncio
from datetime import timedelta
from typing import Dict, Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from config.retry_policies import get_retry_policy

from models.image_request import ImageRequest, ImageResponse
from models.video_request import GenerationStatus
from activities.image_activities import (
    submit_image_request,
    check_image_status,
    download_image_result,
    send_image_notification
)
from activities.common_activities import (
    validate_request,
    log_activity,
    handle_error,
    cleanup_resources
)


@workflow.defn
class ImageGenerationWorkflow:
    """Workflow for handling image generation requests."""
    
    def __init__(self):
        self.request_id: str = ""
        self.external_job_id: str = ""
        self.temp_resources: list[str] = []
    
    @workflow.run
    async def run(self, request_data: Dict[str, Any]) -> ImageResponse:
        """Main workflow execution.
        
        Args:
            request_data: Raw image generation request data
            
        Returns:
            ImageResponse with generation results
        """
        workflow.logger.info(f"Starting image generation workflow")
        
        try:
            # Step 1: Validate request
            validation_result = await workflow.execute_activity(
                validate_request,
                args=[request_data, "image"],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=get_retry_policy("validate_request")
            )
            
            if not validation_result["valid"]:
                return ImageResponse(
                    request_id=request_data.get("request_id", "unknown"),
                    status=GenerationStatus.FAILED,
                    error_message=validation_result["error_message"]
                )
            
            # Create validated request object
            request = ImageRequest(**validation_result["validated_data"])
            self.request_id = request.request_id
            
            # Log workflow start
            await workflow.execute_activity(
                log_activity,
                args=["image_workflow_start", {"request_id": self.request_id}],
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            # Step 2: Submit image generation request
            submission_result = await workflow.execute_activity(
                submit_image_request,
                args=[request],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=get_retry_policy("submit_image_request")
            )
            
            if not submission_result["success"]:
                return ImageResponse(
                    request_id=self.request_id,
                    status=GenerationStatus.FAILED,
                    error_message=submission_result["error"]
                )
            
            self.external_job_id = submission_result["external_job_id"]
            
            # Step 3: Poll for completion
            image_response = await self._poll_for_completion(request)
            
            # Step 4: Download results if successful
            if image_response.status == GenerationStatus.COMPLETED and image_response.image_urls:
                download_result = await workflow.execute_activity(
                    download_image_result,
                    args=[image_response.image_urls, self.request_id],
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=get_retry_policy("download_image_result")
                )
                
                if download_result["success"]:
                    image_response.metadata["downloaded_files"] = download_result["downloaded_files"]
                    image_response.metadata["total_size"] = download_result["total_size"]
                    
                    # Track temp resources for cleanup
                    for file_info in download_result["downloaded_files"]:
                        self.temp_resources.append(file_info["local_path"])
            
            # Step 5: Send notification
            await workflow.execute_activity(
                send_image_notification,
                args=[request, image_response],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=get_retry_policy("send_image_notification")
            )
            
            # Log workflow completion
            await workflow.execute_activity(
                log_activity,
                args=["image_workflow_complete", {
                    "request_id": self.request_id,
                    "status": image_response.status,
                    "processing_time": image_response.processing_time,
                    "image_count": len(image_response.image_urls) if image_response.image_urls else 0
                }],
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            return image_response
            
        except Exception as e:
            # Handle workflow errors
            error_info = await workflow.execute_activity(
                handle_error,
                args=[e, {"workflow": "image_generation", "request_id": self.request_id}],
                start_to_close_timeout=timedelta(seconds=30)
            )
            
            return ImageResponse(
                request_id=self.request_id,
                status=GenerationStatus.FAILED,
                error_message=error_info["error_message"],
                error_code=error_info["error_type"]
            )
        
        finally:
            # Cleanup temporary resources
            if self.temp_resources:
                await workflow.execute_activity(
                    cleanup_resources,
                    args=[self.temp_resources, "temp_files"],
                    start_to_close_timeout=timedelta(minutes=2)
                )
    
    async def _poll_for_completion(self, request: ImageRequest) -> ImageResponse:
        """Poll external service for image generation completion.
        
        Args:
            request: Original image request
            
        Returns:
            ImageResponse with final status
        """
        max_polls = 40  # Maximum 20 minutes (30 seconds * 40)
        poll_count = 0
        
        while poll_count < max_polls:
            # Check status
            status_result = await workflow.execute_activity(
                check_image_status,
                args=[self.external_job_id, self.request_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=get_retry_policy("check_image_status")
            )
            
            status = status_result["status"]
            progress = status_result.get("progress", 0)
            
            # Create response object
            response = ImageResponse(
                request_id=self.request_id,
                status=status,
                progress=progress,
                image_urls=status_result.get("image_urls", [])
            )
            
            # Check if completed or failed
            if status in [GenerationStatus.COMPLETED, GenerationStatus.FAILED]:
                if status == GenerationStatus.COMPLETED:
                    response.completed_at = workflow.utcnow()
                    # Calculate processing time (simplified)
                    response.processing_time = poll_count * 30  # Approximate
                
                return response
            
            # Wait before next poll
            await workflow.sleep(30)  # Wait 30 seconds
            poll_count += 1
        
        # Timeout reached
        return ImageResponse(
            request_id=self.request_id,
            status=GenerationStatus.FAILED,
            error_message="Image generation timeout",
            error_code="TIMEOUT"
        )
    
    @workflow.signal
    async def cancel_generation(self):
        """Signal to cancel image generation."""
        workflow.logger.info(f"Cancellation requested for image generation: {self.request_id}")
        # In a real implementation, you would:
        # 1. Call external API to cancel the job
        # 2. Set workflow state to cancelled
        # 3. Clean up resources
    
    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """Query current workflow status.
        
        Returns:
            Dict containing current workflow state
        """
        return {
            "request_id": self.request_id,
            "external_job_id": self.external_job_id,
            "temp_resources_count": len(self.temp_resources)
        }
    
    @workflow.signal
    async def update_progress(self, progress: float):
        """Signal to update generation progress.
        
        Args:
            progress: Current progress percentage (0-100)
        """
        workflow.logger.info(f"Progress update for {self.request_id}: {progress}%")
        # In a real implementation, you might:
        # 1. Update internal state
        # 2. Send progress notifications
        # 3. Update external monitoring systems