#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Temporal Activities for Video Generation

This module contains Temporal activities for video generation using Kling API proxy.
Integrates with the Kling API proxy service running on http://127.0.0.1:16882.
"""

# Import gen_image function from image activities
from activities.image_activities import gen_image

import asyncio
import httpx
from typing import Dict, Any, Optional
from temporalio import activity, workflow
from datetime import datetime, timedelta
import logging
from config.retry_policies import get_retry_policy
from config.concurrency_control import with_concurrency_control

# Configure logging
logger = logging.getLogger(__name__)


@activity.defn
@with_concurrency_control(timeout=300)
async def request_video(image_url: str) -> str:
    """
    Request video generation from Kling API proxy.
    
    This activity submits a video generation request to the Kling API proxy
    service and returns a job ID for tracking the generation progress.
    
    Args:
        image_url (str): URL or path to the source image for video generation
        
    Returns:
        str: Job ID for tracking the video generation progress
        
    Raises:
        Exception: If the API request fails or returns an error
    """
    activity.logger.info(f"Requesting video generation for image: {image_url}")
    
    try:
        # Kling API proxy endpoint
        api_endpoint = "http://127.0.0.1:16882/video/submit"
        
        # Prepare request payload
        payload = {
            "imageUrl": image_url,
            "callbackUrl": None,  # Will be handled via Temporal signals
            "positivePrompt": "高清，精美，流畅的动画效果",
            "negativePrompt": "模糊，低质量，卡顿",
            "debug": False
        }
        
        # Set timeout for the request
        timeout = httpx.Timeout(30.0)  # 30 seconds timeout for submission
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            activity.logger.info(f"Submitting video request to: {api_endpoint}")
            
            response = await client.post(
                api_endpoint,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Temporal-Video-Worker/1.0"
                }
            )
            
            # Check if request was successful
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            
            if not result.get("success", False):
                error_msg = result.get("message", "Unknown error occurred")
                activity.logger.error(f"Video request failed: {error_msg}")
                raise Exception(f"Video generation request failed: {error_msg}")
            
            # Extract job ID
            job_id = result.get("taskId")
            if not job_id:
                activity.logger.error("No job ID returned from API")
                raise Exception("No job ID returned from video generation API")
            
            activity.logger.info(f"Video generation request submitted successfully. Job ID: {job_id}")
            return job_id
            
    except httpx.TimeoutException:
        error_msg = "Timeout while submitting video generation request"
        activity.logger.error(error_msg)
        raise Exception(error_msg)
        
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
        activity.logger.error(error_msg)
        raise Exception(error_msg)
        
    except httpx.RequestError as e:
        error_msg = f"Request error: {str(e)}"
        activity.logger.error(error_msg)
        raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Unexpected error during video request: {str(e)}"
        activity.logger.error(error_msg)
        raise Exception(error_msg)


@activity.defn
@with_concurrency_control(timeout=180)
async def check_video_generation_status(job_id: str) -> Dict[str, Any]:
    """
    Check the status of video generation job.
    
    Args:
        job_id (str): Job ID returned from request_video
        
    Returns:
        Dict[str, Any]: Status information including completion status and video URL if ready
    """
    activity.logger.info(f"Checking video generation status for job: {job_id}")
    
    try:
        # Kling API proxy status endpoint
        api_endpoint = f"http://127.0.0.1:16882/api/tasks/{job_id}"
        
        timeout = httpx.Timeout(15.0)  # 15 seconds timeout for status check
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                api_endpoint,
                headers={
                    "User-Agent": "Temporal-Video-Worker/1.0"
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            status = result.get("status", "UNKNOWN")
            
            status_info = {
                "job_id": job_id,
                "status": status,
                "checked_at": datetime.utcnow().isoformat(),
                "completed": status == "COMPLETED",
                "failed": status in ["FAILED", "ERROR"],
                "video_url": None,
                "error_message": None
            }
            
            # If completed, get video URL
            if status == "COMPLETED":
                video_endpoint = f"http://127.0.0.1:16882/api/tasks/{job_id}/video"
                status_info["video_url"] = video_endpoint
                activity.logger.info(f"Video generation completed for job {job_id}")
            elif status in ["FAILED", "ERROR"]:
                status_info["error_message"] = result.get("error", "Video generation failed")
                activity.logger.error(f"Video generation failed for job {job_id}: {status_info['error_message']}")
            else:
                activity.logger.info(f"Video generation in progress for job {job_id}, status: {status}")
            
            return status_info
            
    except Exception as e:
        error_msg = f"Error checking video status: {str(e)}"
        activity.logger.error(error_msg)
        return {
            "job_id": job_id,
            "status": "ERROR",
            "checked_at": datetime.utcnow().isoformat(),
            "completed": False,
            "failed": True,
            "video_url": None,
            "error_message": error_msg
        }


@activity.defn
@with_concurrency_control(timeout=600)
async def download_generated_video(video_url: str, job_id: str) -> Dict[str, Any]:
    """
    Download the generated video from the API.
    
    Args:
        video_url (str): URL to download the video
        job_id (str): Job ID for reference
        
    Returns:
        Dict[str, Any]: Download result with local path or error information
    """
    activity.logger.info(f"Downloading generated video for job {job_id} from: {video_url}")
    
    try:
        timeout = httpx.Timeout(300.0)  # 5 minutes timeout for video download
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                video_url,
                headers={
                    "User-Agent": "Temporal-Video-Worker/1.0"
                }
            )
            
            response.raise_for_status()
            
            # For now, we'll return the video URL since we don't have local storage setup
            # In a real implementation, you would save the video content to local storage
            
            result = {
                "success": True,
                "job_id": job_id,
                "video_url": video_url,
                "downloaded_at": datetime.utcnow().isoformat(),
                "file_size": len(response.content) if hasattr(response, 'content') else 0
            }
            
            activity.logger.info(f"Video download completed for job {job_id}")
            return result
            
    except Exception as e:
        error_msg = f"Error downloading video: {str(e)}"
        activity.logger.error(error_msg)
        return {
            "success": False,
            "job_id": job_id,
            "error_message": error_msg,
            "downloaded_at": datetime.utcnow().isoformat()
        }


# Import existing activities from the activities directory
try:
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
except ImportError as e:
    logger.warning(f"Could not import some activities: {e}")