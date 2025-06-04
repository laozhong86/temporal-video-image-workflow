"""Basic workflow definition for orchestrating image-to-video generation pipeline."""

import asyncio
from datetime import timedelta, datetime
from typing import Dict, Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy
from config.retry_policies import get_retry_policy

from models.core_models import JobInput, Progress, Step, JobStatus
from activities.image_activities import gen_image
from activities.video_activities import (
    submit_video_request,
    check_video_status,
    download_video_result
)
from activities.common_activities import (
    validate_request,
    log_activity,
    handle_error,
    cleanup_resources
)
from models.video_request import VideoRequest


@workflow.defn
class GenVideoWorkflow:
    """Workflow for orchestrating image-to-video generation pipeline with progress tracking."""
    
    def __init__(self):
        """Initialize workflow state."""
        self.workflow_id: str = ""
        self.job_input: Optional[JobInput] = None
        self.current_progress: Progress = Progress(
            step=Step.IMAGE,
            status=JobStatus.PENDING,
            percent=0
        )
        self.started_at: datetime = datetime.utcnow()
        self.temp_resources: list[str] = []
        self.image_url: Optional[str] = None
        self.video_url: Optional[str] = None
    
    @workflow.run
    async def run(self, job_input: JobInput) -> str:
        """Main workflow execution for image-to-video generation.
        
        Args:
            job_input: Job input containing prompt and generation parameters
            
        Returns:
            str: Final video URL or image URL based on job type
            
        Raises:
            Exception: If generation fails
        """
        self.workflow_id = workflow.info().workflow_id
        self.job_input = job_input
        
        workflow.logger.info(f"Starting GenVideoWorkflow for job type: {job_input.job_type}")
        
        try:
            # Step 1: Validate request
            await self._update_progress(
                Step.IMAGE,
                JobStatus.PROCESSING,
                5,
                "Validating request parameters"
            )
            
            validation_result = await workflow.execute_activity(
                validate_request,
                args=[job_input.to_temporal_payload()],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=get_retry_policy("validate_request")
            )
            
            if not validation_result.get("valid", False):
                await self._update_progress(
                    Step.IMAGE,
                    JobStatus.FAILED,
                    0,
                    f"Validation failed: {validation_result.get('error_message', 'Unknown error')}"
                )
                raise Exception(f"Request validation failed: {validation_result.get('error_message')}")
            
            # Log workflow start
            await workflow.execute_activity(
                log_activity,
                args=["gen_video_workflow_start", {
                    "workflow_id": self.workflow_id,
                    "job_type": job_input.job_type.value,
                    "prompt": job_input.prompt[:100]
                }],
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            # Step 2: Generate image
            await self._update_progress(
                Step.IMAGE,
                JobStatus.PROCESSING,
                20,
                "Starting image generation"
            )
            
            self.image_url = await workflow.execute_activity(
                gen_image,
                args=[job_input],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=get_retry_policy("gen_image")
            )
            
            await self._update_progress(
                Step.IMAGE,
                JobStatus.COMPLETED,
                50,
                "Image generation completed",
                asset_url=self.image_url
            )
            
            # If job type is IMAGE, return image URL
            if job_input.job_type == Step.IMAGE:
                await self._finalize_workflow(self.image_url)
                return self.image_url
            
            # Step 3: Generate video (if job type is VIDEO)
            if job_input.job_type == Step.VIDEO:
                await self._update_progress(
                    Step.VIDEO,
                    JobStatus.PROCESSING,
                    60,
                    "Starting video generation from image"
                )
                
                # Create video request
                video_request = VideoRequest(
                    prompt=job_input.prompt,
                    image_url=self.image_url,
                    duration=job_input.duration or 5,
                    width=job_input.width or 1024,
                    height=job_input.height or 1024,
                    fps=job_input.fps or 24,
                    model=job_input.model or "kling-v1",
                    quality=job_input.quality or "standard",
                    style=job_input.style or "realistic",
                    callback_url=f"http://localhost:8000/callback/{self.workflow_id}"
                )
                
                # Submit video generation request
                await self._update_progress(
                    Step.VIDEO,
                    JobStatus.PROCESSING,
                    65,
                    "Submitting video generation request"
                )
                
                submission_result = await workflow.execute_activity(
                    submit_video_request,
                    args=[video_request],
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=get_retry_policy("submit_video_request")
                )
                
                if not submission_result.get("success", False):
                    raise Exception(f"Video submission failed: {submission_result.get('error_message')}")
                
                external_job_id = submission_result.get("external_job_id")
                
                # Poll for video generation completion
                await self._update_progress(
                    Step.VIDEO,
                    JobStatus.PROCESSING,
                    70,
                    "Polling video generation status"
                )
                
                status_result = await workflow.execute_activity(
                    check_video_status,
                    args=[external_job_id, video_request.request_id],
                    start_to_close_timeout=timedelta(minutes=15),
                    retry_policy=get_retry_policy("check_video_status")
                )
                
                if not status_result.get("success", False):
                    raise Exception(f"Video generation failed: {status_result.get('error_message')}")
                
                # Get video result
                await self._update_progress(
                    Step.VIDEO,
                    JobStatus.PROCESSING,
                    90,
                    "Retrieving video result"
                )
                
                # Check if video generation is completed
                if status_result.get("status") != "completed":
                    raise Exception(f"Video generation not completed: {status_result.get('status')}")
                
                video_url = status_result.get("video_url")
                if not video_url:
                    raise Exception("Video URL not available in status result")
                
                # Download video result
                result = await workflow.execute_activity(
                    download_video_result,
                    args=[video_url, video_request.request_id],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=get_retry_policy("download_video_result")
                )
                
                if not result.get("success", False):
                    raise Exception(f"Failed to download video result: {result.get('error')}")
                
                self.video_url = video_url
                
                await self._update_progress(
                    Step.VIDEO,
                    JobStatus.COMPLETED,
                    100,
                    "Video generation completed",
                    asset_url=self.video_url
                )
                
                await self._finalize_workflow(self.video_url)
                return self.video_url
            
            # Should not reach here
            raise Exception(f"Unsupported job type: {job_input.job_type}")
            
        except Exception as e:
            # Handle workflow errors
            workflow.logger.error(f"Workflow failed: {str(e)}")
            
            await self._update_progress(
                self.current_progress.step,
                JobStatus.FAILED,
                self.current_progress.percent,
                f"Workflow failed: {str(e)}"
            )
            
            error_info = await workflow.execute_activity(
                handle_error,
                args=[e, {
                    "workflow": "gen_video_workflow",
                    "workflow_id": self.workflow_id,
                    "job_type": job_input.job_type.value if job_input else "unknown"
                }],
                start_to_close_timeout=timedelta(seconds=30)
            )
            
            raise Exception(error_info.get("error_message", str(e)))
        
        finally:
            # Cleanup temporary resources
            if self.temp_resources:
                await workflow.execute_activity(
                    cleanup_resources,
                    args=[self.temp_resources, "temp_files"],
                    start_to_close_timeout=timedelta(minutes=2)
                )
    
    async def _update_progress(
        self,
        step: Step,
        status: JobStatus,
        percent: int,
        message: Optional[str] = None,
        asset_url: Optional[str] = None
    ):
        """Update workflow progress.
        
        Args:
            step: Current workflow step
            status: Current status
            percent: Progress percentage (0-100)
            message: Optional progress message
            asset_url: Optional asset URL
        """
        self.current_progress = Progress(
            step=step,
            status=status,
            percent=percent,
            message=message,
            asset_url=asset_url,
            updated_at=workflow.utcnow()
        )
        
        workflow.logger.info(
            f"Progress update: {step.value} - {status.value} - {percent}% - {message or 'No message'}"
        )
    
    async def _finalize_workflow(self, result_url: str):
        """Finalize workflow execution.
        
        Args:
            result_url: Final result URL
        """
        # Log workflow completion
        await workflow.execute_activity(
            log_activity,
            args=["gen_video_workflow_complete", {
                "workflow_id": self.workflow_id,
                "job_type": self.job_input.job_type.value if self.job_input else "unknown",
                "result_url": result_url,
                "duration_seconds": (workflow.utcnow() - self.started_at).total_seconds()
            }],
            start_to_close_timeout=timedelta(seconds=10)
        )
    
    @workflow.query
    def get_progress(self) -> Progress:
        """Query current workflow progress.
        
        Returns:
            Progress: Current progress state
        """
        return self.current_progress
    
    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """Get current workflow status and progress.
        
        Returns:
            Dict containing current status information
        """
        return {
            "workflow_id": self.workflow_id,
            "status": self.current_progress.status,
            "step": self.current_progress.step,
            "percent": self.current_progress.percent,
            "message": self.current_progress.message,
            "error_message": self.current_progress.error_message,
            "started_at": self.started_at.isoformat(),
            "estimated_completion": self.current_progress.estimated_completion,
            "asset_url": self.current_progress.asset_url,
            "temp_resources": self.temp_resources,
            "image_url": self.image_url,
            "video_url": self.video_url
        }
    
    def update_progress(self, step: Step, status: JobStatus, percent: int, 
                       message: Optional[str] = None, 
                       error_message: Optional[str] = None,
                       asset_url: Optional[str] = None,
                       estimated_completion: Optional[str] = None) -> None:
        """Update workflow progress.
        
        Args:
            step: Current workflow step
            status: Current job status
            percent: Completion percentage (0-100)
            message: Optional progress message
            error_message: Optional error message
            asset_url: Optional URL to generated asset
            estimated_completion: Optional estimated completion time
        """
        self.current_progress = Progress(
            step=step,
            status=status,
            percent=percent,
            message=message,
            error_message=error_message,
            asset_url=asset_url,
            estimated_completion=estimated_completion
        )
    
    @workflow.signal
    async def cancel_generation(self):
        """Signal to cancel generation process."""
        workflow.logger.info(f"Cancellation requested for workflow: {self.workflow_id}")
        
        await self._update_progress(
            self.current_progress.step,
            JobStatus.FAILED,
            self.current_progress.percent,
            "Generation cancelled by user request"
        )
        
        # In a real implementation, you would:
        # 1. Cancel any running activities
        # 2. Clean up resources
        # 3. Update external systems
    
    @workflow.signal
    async def update_progress_signal(self, step: str, status: str, percent: int, message: str = ""):
        """Signal to update generation progress from external sources.
        
        Args:
            step: Current step name
            status: Current status
            percent: Progress percentage
            message: Optional message
        """
        try:
            step_enum = Step(step)
            status_enum = JobStatus(status)
            
            await self._update_progress(
                step_enum,
                status_enum,
                percent,
                message
            )
        except ValueError as e:
            workflow.logger.warning(f"Invalid progress update parameters: {e}")