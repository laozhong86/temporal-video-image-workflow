"""Video generation workflow using Temporal."""

import asyncio
from datetime import timedelta, datetime
from typing import Dict, Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from config.retry_policies import get_retry_policy

from models.video_request import VideoRequest, VideoResponse, GenerationStatus
from models.core_models import WorkflowState, Progress, JobStatus, Step, JobInput
from models.state_persistence import WorkflowStateManager
from activities.video_activities import (
    submit_video_request,
    check_video_status,
    download_video_result,
    send_video_notification
)
# Import new video generation activity from activities.py file
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from activities import request_video, check_video_generation_status, download_generated_video
from activities.common_activities import (
    validate_request,
    log_activity,
    handle_error,
    cleanup_resources
)


@workflow.defn
class VideoGenerationWorkflow:
    """Workflow for handling video generation requests."""
    
    def __init__(self):
        self.request_id: str = ""
        self.external_job_id: str = ""
        self.temp_resources: list[str] = []
        self.kling_job_id: str = ""
        self.kling_completed: bool = False
        self.kling_result: Dict[str, Any] = {}
        self.state_manager: WorkflowStateManager = None
        self.workflow_state: WorkflowState = None
    
    @workflow.run
    async def run(self, request_data: Dict[str, Any]) -> VideoResponse:
        """Main workflow execution.
        
        Args:
            request_data: Raw video generation request data
            
        Returns:
            VideoResponse with generation results
        """
        workflow.logger.info(f"Starting video generation workflow")
        
        try:
            # Step 1: Validate request
            validation_result = await workflow.execute_activity(
                validate_request,
                args=[request_data, "video"],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=get_retry_policy("validate_request")
            )
            
            if not validation_result["valid"]:
                return VideoResponse(
                    request_id=request_data.get("request_id", "unknown"),
                    status=GenerationStatus.FAILED,
                    error_message=validation_result["error_message"]
                )
            
            # Create validated request object
            request = VideoRequest(**validation_result["validated_data"])
            self.request_id = request.request_id
            
            # Initialize state management
            self.state_manager = WorkflowStateManager(self.request_id)
            
            # Create initial workflow state
            job_input = JobInput(
                job_type=JobType.VIDEO_GENERATION,
                prompt=request.prompt,
                user_id=getattr(request, 'user_id', None),
                metadata={
                    "aspect_ratio": getattr(request, 'aspect_ratio', None),
                    "duration": getattr(request, 'duration', None),
                    "style": getattr(request, 'style', None)
                }
            )
            
            initial_progress = Progress(
                step=Step.VALIDATION,
                status=JobStatus.IN_PROGRESS,
                percent=10,
                message="Request validated successfully"
            )
            
            self.workflow_state = WorkflowState.create_initial_state(
                workflow_id=self.request_id,
                job_input=job_input,
                initial_progress=initial_progress
            )
            
            # Initialize state in Temporal search attributes
            await self.state_manager.initialize_state(self.workflow_state)
            
            # Log workflow start
            await workflow.execute_activity(
                log_activity,
                args=["video_workflow_start", {"request_id": self.request_id}],
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            # Step 2: Submit video generation request
            # Update state: Starting submission
            await self.state_manager.update_progress(Progress(
                step=Step.SUBMISSION,
                status=JobStatus.IN_PROGRESS,
                percent=20,
                message="Submitting video generation request"
            ))
            
            submission_result = await workflow.execute_activity(
                submit_video_request,
                args=[request],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=get_retry_policy("submit_video_request")
            )
            
            if not submission_result["success"]:
                # Record error in state
                await self.state_manager.record_error(
                    f"Submission failed: {submission_result['error']}"
                )
                return VideoResponse(
                    request_id=self.request_id,
                    status=GenerationStatus.FAILED,
                    error_message=submission_result["error"]
                )
            
            self.external_job_id = submission_result["external_job_id"]
            
            # Update state: Submission successful
            await self.state_manager.update_progress(Progress(
                step=Step.PROCESSING,
                status=JobStatus.IN_PROGRESS,
                percent=30,
                message=f"Request submitted successfully. Job ID: {self.external_job_id}"
            ))
            
            # Step 3: Poll for completion
            video_response = await self._poll_for_completion(request)
            
            # Step 4: Download result if successful
            if video_response.status == GenerationStatus.COMPLETED and video_response.video_url:
                # Update state: Starting download
                await self.state_manager.update_progress(Progress(
                    step=Step.DOWNLOAD,
                    status=JobStatus.IN_PROGRESS,
                    percent=80,
                    message="Downloading generated video"
                ))
                
                download_result = await workflow.execute_activity(
                    download_video_result,
                    args=[video_response.video_url, self.request_id],
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=get_retry_policy("download_video_result")
                )
                
                if download_result["success"]:
                    video_response.metadata["local_path"] = download_result["local_path"]
                    video_response.metadata["file_size"] = download_result["file_size"]
                    self.temp_resources.append(download_result["local_path"])
                    
                    # Update state: Download completed
                    await self.state_manager.update_progress(Progress(
                        step=Step.DOWNLOAD,
                        status=JobStatus.COMPLETED,
                        percent=90,
                        message=f"Video downloaded successfully. Size: {download_result['file_size']} bytes"
                    ))
                else:
                    # Record download error
                    await self.state_manager.record_error(
                        f"Download failed: {download_result.get('error', 'Unknown error')}"
                    )
            
            # Step 5: Send notification
            await workflow.execute_activity(
                send_video_notification,
                args=[request, video_response],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=get_retry_policy("send_video_notification")
            )
            
            # Complete workflow state management
            result_urls = [video_response.video_url] if video_response.video_url else []
            await self.state_manager.complete_workflow(result_urls)
            
            # Update final progress
            final_status = JobStatus.COMPLETED if video_response.status == GenerationStatus.COMPLETED else JobStatus.FAILED
            await self.state_manager.update_progress(Progress(
                step=Step.COMPLETION,
                status=final_status,
                percent=100,
                message=f"Workflow completed with status: {video_response.status}"
            ))
            
            # Log workflow completion
            await workflow.execute_activity(
                log_activity,
                args=["video_workflow_complete", {
                    "request_id": self.request_id,
                    "status": video_response.status,
                    "processing_time": video_response.processing_time,
                    "state_audit_entries": len(self.state_manager.get_audit_entries())
                }],
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            return video_response
            
        except Exception as e:
            # Record error in state management if available
            if self.state_manager:
                await self.state_manager.record_error(
                    f"Workflow exception: {str(e)}",
                    retry_count=getattr(self.workflow_state, 'retry_count', 0) if self.workflow_state else 0
                )
                
                # Update final error state
                await self.state_manager.update_progress(Progress(
                    step=Step.ERROR_HANDLING,
                    status=JobStatus.FAILED,
                    percent=0,
                    message=f"Workflow failed with error: {str(e)}"
                ))
            
            # Handle workflow errors
            error_info = await workflow.execute_activity(
                handle_error,
                args=[e, {"workflow": "video_generation", "request_id": self.request_id}],
                start_to_close_timeout=timedelta(seconds=30)
            )
            
            return VideoResponse(
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
    
    async def _poll_for_completion(self, request: VideoRequest) -> VideoResponse:
        """Poll external service for video generation completion.
        
        Args:
            request: Original video request
            
        Returns:
            VideoResponse with final status
        """
        max_polls = 60  # Maximum 30 minutes (30 seconds * 60)
        poll_count = 0
        
        while poll_count < max_polls:
            # Check status
            status_result = await workflow.execute_activity(
                check_video_status,
                args=[self.external_job_id, self.request_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=get_retry_policy("check_video_status")
            )
            
            status = status_result["status"]
            progress = status_result.get("progress", 0)
            
            # Update state with polling progress
            if self.state_manager:
                # Calculate overall progress (30% base + 50% for processing)
                overall_progress = 30 + int(progress * 0.5) if progress else 30 + (poll_count * 2)
                overall_progress = min(overall_progress, 80)  # Cap at 80% until download
                
                await self.state_manager.update_progress(Progress(
                    step=Step.PROCESSING,
                    status=JobStatus.IN_PROGRESS,
                    percent=overall_progress,
                    message=f"Processing video... Poll #{poll_count + 1}, Progress: {progress}%"
                ))
            
            # Create response object
            response = VideoResponse(
                request_id=self.request_id,
                status=status,
                progress=progress,
                video_url=status_result.get("video_url"),
                thumbnail_url=status_result.get("thumbnail_url")
            )
            
            # Check if completed or failed
            if status in [GenerationStatus.COMPLETED, GenerationStatus.FAILED]:
                if status == GenerationStatus.COMPLETED:
                    response.completed_at = workflow.utcnow()
                    # Calculate processing time (simplified)
                    response.processing_time = poll_count * 30  # Approximate
                    
                    # Update state: Processing completed
                    if self.state_manager:
                        await self.state_manager.update_progress(Progress(
                            step=Step.PROCESSING,
                            status=JobStatus.COMPLETED,
                            percent=75,
                            message=f"Video generation completed after {poll_count + 1} polls"
                        ))
                elif status == GenerationStatus.FAILED:
                    # Record processing failure
                    if self.state_manager:
                        await self.state_manager.record_error(
                            f"Video generation failed: {status_result.get('error_message', 'Unknown error')}"
                        )
                
                return response
            
            # Wait before next poll
            await asyncio.sleep(30)  # Wait 30 seconds
            poll_count += 1
        
        # Timeout reached
        if self.state_manager:
            await self.state_manager.record_error(
                f"Video generation timeout after {max_polls} polls ({max_polls * 30} seconds)"
            )
        
        return VideoResponse(
            request_id=self.request_id,
            status=GenerationStatus.FAILED,
            error_message="Video generation timeout",
            error_code="TIMEOUT"
        )
    
    @workflow.signal
    async def kling_done(self, result: Dict[str, Any]):
        """Signal handler for Kling API video generation completion.
        
        Args:
            result: Result data from Kling API callback
        """
        workflow.logger.info(f"Kling video generation completed for job: {self.kling_job_id}")
        self.kling_completed = True
        self.kling_result = result
    
    @workflow.signal
    async def cancel_generation(self):
        """Signal to cancel video generation."""
        workflow.logger.info(f"Cancellation requested for video generation: {self.request_id}")
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