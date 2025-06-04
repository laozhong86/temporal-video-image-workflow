#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kling Video Generation Workflow with Async Callback Handling

This workflow demonstrates the use of request_video activity with
workflow.wait_condition() for handling async callbacks via kling_done signal.
"""

import asyncio
from datetime import timedelta
from typing import Dict, Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

from models.video_request import VideoRequest, VideoResponse, GenerationStatus
from activities import request_video, check_video_generation_status, download_generated_video
from activities.common_activities import (
    validate_request,
    log_activity,
    handle_error,
    cleanup_resources
)
from config.retry_policies import get_retry_policy


@workflow.defn
class KlingVideoGenerationWorkflow:
    """Workflow for handling Kling API video generation with async callbacks."""
    
    def __init__(self):
        self.request_id: str = ""
        self.kling_job_id: str = ""
        self.kling_completed: bool = False
        self.kling_result: Dict[str, Any] = {}
        self.temp_resources: list[str] = []
    
    @workflow.run
    async def run(self, image_url: str, request_id: Optional[str] = None) -> VideoResponse:
        """Main workflow execution using request_video activity with async callback.
        
        Args:
            image_url: URL or path to the source image for video generation
            request_id: Optional request ID for tracking
            
        Returns:
            VideoResponse with generation results
        """
        self.request_id = request_id or f"kling_video_{workflow.uuid4()}"
        workflow.logger.info(f"Starting Kling video generation workflow for request: {self.request_id}")
        
        try:
            # Step 1: Log workflow start
            await workflow.execute_activity(
                log_activity,
                args=["kling_video_workflow_start", {
                    "request_id": self.request_id,
                    "image_url": image_url
                }],
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            # Step 2: Submit video generation request using new request_video activity
            workflow.logger.info(f"Submitting video generation request for image: {image_url}")
            
            self.kling_job_id = await workflow.execute_activity(
                request_video,
                args=[image_url],
                start_to_close_timeout=timedelta(seconds=60),  # 60 seconds for submission
                retry_policy=get_retry_policy("request_video")
            )
            
            workflow.logger.info(f"Video generation submitted successfully. Job ID: {self.kling_job_id}")
            
            # Step 3: Wait for completion using workflow.wait_condition() with 600s timeout
            workflow.logger.info(f"Waiting for video generation completion (timeout: 600s)")
            
            # Wait for kling_done signal or timeout after 600 seconds
            completion_success = await workflow.wait_condition(
                lambda: self.kling_completed,
                timeout=timedelta(seconds=600)  # 10 minutes timeout as specified in task
            )
            
            if not completion_success:
                # Timeout occurred
                workflow.logger.error(f"Video generation timeout for job: {self.kling_job_id}")
                return VideoResponse(
                    request_id=self.request_id,
                    status=GenerationStatus.FAILED,
                    error_message="Video generation timeout (600s exceeded)",
                    error_code="TIMEOUT"
                )
            
            # Step 4: Process completion result
            workflow.logger.info(f"Video generation completed for job: {self.kling_job_id}")
            
            # Check if generation was successful
            if not self.kling_result.get("success", False):
                error_message = self.kling_result.get("error", "Unknown error during video generation")
                return VideoResponse(
                    request_id=self.request_id,
                    status=GenerationStatus.FAILED,
                    error_message=error_message,
                    error_code="GENERATION_FAILED"
                )
            
            # Step 5: Get video URL from result
            video_url = self.kling_result.get("video_url")
            if not video_url:
                return VideoResponse(
                    request_id=self.request_id,
                    status=GenerationStatus.FAILED,
                    error_message="No video URL in completion result",
                    error_code="NO_VIDEO_URL"
                )
            
            # Step 6: Download the generated video
            download_result = await workflow.execute_activity(
                download_generated_video,
                args=[video_url, self.kling_job_id],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=get_retry_policy("download_generated_video")
            )
            
            # Step 7: Create successful response
            response = VideoResponse(
                request_id=self.request_id,
                status=GenerationStatus.COMPLETED,
                video_url=video_url,
                completed_at=workflow.utcnow(),
                metadata={
                    "kling_job_id": self.kling_job_id,
                    "download_success": download_result.get("success", False),
                    "file_size": download_result.get("file_size", 0)
                }
            )
            
            if download_result.get("success"):
                response.metadata["local_path"] = download_result.get("local_path")
                if download_result.get("local_path"):
                    self.temp_resources.append(download_result["local_path"])
            
            # Log workflow completion
            await workflow.execute_activity(
                log_activity,
                args=["kling_video_workflow_complete", {
                    "request_id": self.request_id,
                    "kling_job_id": self.kling_job_id,
                    "status": "completed",
                    "video_url": video_url
                }],
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            return response
            
        except Exception as e:
            # Handle workflow errors
            workflow.logger.error(f"Error in Kling video generation workflow: {str(e)}")
            
            error_info = await workflow.execute_activity(
                handle_error,
                args=[e, {
                    "workflow": "kling_video_generation",
                    "request_id": self.request_id,
                    "kling_job_id": self.kling_job_id
                }],
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
    
    async def run_with_polling_fallback(self, image_url: str, request_id: Optional[str] = None) -> VideoResponse:
        """Alternative workflow method that uses polling as fallback if signals are not available.
        
        Args:
            image_url: URL or path to the source image for video generation
            request_id: Optional request ID for tracking
            
        Returns:
            VideoResponse with generation results
        """
        self.request_id = request_id or f"kling_video_polling_{workflow.uuid4()}"
        workflow.logger.info(f"Starting Kling video generation with polling fallback: {self.request_id}")
        
        try:
            # Submit video generation request
            self.kling_job_id = await workflow.execute_activity(
                request_video,
                args=[image_url],
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=get_retry_policy("request_video")
            )
            
            # Try to wait for signal first (shorter timeout)
            signal_received = await workflow.wait_condition(
                lambda: self.kling_completed,
                timeout=timedelta(seconds=30)  # Wait 30 seconds for signal
            )
            
            if signal_received:
                # Signal received, process result
                workflow.logger.info("Signal received, processing result")
                if self.kling_result.get("success"):
                    video_url = self.kling_result.get("video_url")
                    if video_url:
                        return VideoResponse(
                            request_id=self.request_id,
                            status=GenerationStatus.COMPLETED,
                            video_url=video_url,
                            completed_at=workflow.utcnow()
                        )
            
            # Fallback to polling
            workflow.logger.info("No signal received, falling back to polling")
            return await self._poll_for_completion_with_timeout()
            
        except Exception as e:
            workflow.logger.error(f"Error in polling fallback workflow: {str(e)}")
            return VideoResponse(
                request_id=self.request_id,
                status=GenerationStatus.FAILED,
                error_message=str(e)
            )
    
    async def _poll_for_completion_with_timeout(self) -> VideoResponse:
        """Poll for completion with 600-second timeout.
        
        Returns:
            VideoResponse with final status
        """
        max_polls = 120  # 600 seconds / 5 seconds per poll
        poll_count = 0
        
        while poll_count < max_polls:
            # Check status using new activity
            status_result = await workflow.execute_activity(
                check_video_generation_status,
                args=[self.kling_job_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=get_retry_policy("check_video_generation_status")
            )
            
            if status_result["completed"]:
                # Generation completed successfully
                video_url = status_result.get("video_url")
                return VideoResponse(
                    request_id=self.request_id,
                    status=GenerationStatus.COMPLETED,
                    video_url=video_url,
                    completed_at=workflow.utcnow(),
                    processing_time=poll_count * 5
                )
            elif status_result["failed"]:
                # Generation failed
                return VideoResponse(
                    request_id=self.request_id,
                    status=GenerationStatus.FAILED,
                    error_message=status_result.get("error_message", "Video generation failed")
                )
            
            # Wait before next poll
            await asyncio.sleep(5)  # Poll every 5 seconds
            poll_count += 1
        
        # Timeout reached
        return VideoResponse(
            request_id=self.request_id,
            status=GenerationStatus.FAILED,
            error_message="Video generation timeout (600s exceeded)",
            error_code="TIMEOUT"
        )
    
    @workflow.signal
    async def kling_done(self, result: Dict[str, Any]):
        """Signal handler for Kling API video generation completion.
        
        Args:
            result: Result data from Kling API callback containing:
                   - success: bool
                   - video_url: str (if successful)
                   - error: str (if failed)
                   - job_id: str
        """
        workflow.logger.info(f"Kling video generation signal received for job: {self.kling_job_id}")
        self.kling_completed = True
        self.kling_result = result
        
        # Log signal reception
        await workflow.execute_activity(
            log_activity,
            args=["kling_done_signal_received", {
                "request_id": self.request_id,
                "kling_job_id": self.kling_job_id,
                "success": result.get("success", False),
                "has_video_url": bool(result.get("video_url"))
            }],
            start_to_close_timeout=timedelta(seconds=10)
        )
    
    @workflow.signal
    async def cancel_generation(self):
        """Signal to cancel video generation."""
        workflow.logger.info(f"Cancellation requested for Kling video generation: {self.request_id}")
        # Mark as cancelled to break wait condition
        self.kling_completed = True
        self.kling_result = {
            "success": False,
            "error": "Generation cancelled by user",
            "cancelled": True
        }
    
    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """Query current workflow status.
        
        Returns:
            Dict containing current workflow state
        """
        return {
            "request_id": self.request_id,
            "kling_job_id": self.kling_job_id,
            "kling_completed": self.kling_completed,
            "has_result": bool(self.kling_result),
            "temp_resources_count": len(self.temp_resources)
        }