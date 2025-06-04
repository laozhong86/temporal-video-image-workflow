"""Video generation activities for Temporal workflows."""

import asyncio
import httpx
from typing import Dict, Any
from temporalio import activity
from datetime import datetime, timedelta

from models.video_request import VideoRequest, VideoResponse, GenerationStatus
from config.retry_policies import (
    get_retry_policy,
    is_retryable_error,
    APIError,
    NetworkError,
    TimeoutError,
    RateLimitError,
    ValidationError,
    should_send_heartbeat,
    HEARTBEAT_INTERVAL
)
from config.concurrency_control import with_concurrency_control


@activity.defn
@with_concurrency_control(timeout=300)
async def submit_video_request(request: VideoRequest) -> Dict[str, Any]:
    """Submit video generation request to external API.
    
    Args:
        request: Video generation request
        
    Returns:
        Dict containing submission result and external job ID
    """
    activity.logger.info(f"Submitting video request: {request.request_id}")
    
    # Send heartbeat for long-running operations
    if should_send_heartbeat("submit_video_request"):
        activity.heartbeat()
    
    try:
        # Simulate API call to external video generation service
        async with httpx.AsyncClient(timeout=30.0) as client:
            # This would be replaced with actual API endpoint
            api_url = "https://api.kling.ai/v1/videos/generate"
            
            payload = {
                "prompt": request.prompt,
                "duration": request.duration,
                "width": request.width,
                "height": request.height,
                "fps": request.fps,
                "model": request.model,
                "quality": request.quality,
                "style": request.style,
                "callback_url": request.callback_url
            }
            
            # Validate request before submission
            if not request.prompt or len(request.prompt.strip()) == 0:
                raise ValidationError("Prompt cannot be empty")
            
            # For demo purposes, simulate successful submission
            # In real implementation, make actual HTTP request
            # response = await client.post(api_url, json=payload, headers=headers)
            # 
            # if response.status_code == 429:
            #     raise RateLimitError(f"Rate limit exceeded: {response.text}")
            # elif response.status_code >= 500:
            #     raise APIError(f"Server error: {response.status_code} - {response.text}")
            # elif response.status_code >= 400:
            #     raise ValidationError(f"Client error: {response.status_code} - {response.text}")
            
            # Simulated response
            external_job_id = f"kling_{request.request_id}_{int(datetime.utcnow().timestamp())}"
            
            result = {
                "success": True,
                "external_job_id": external_job_id,
                "status": GenerationStatus.PROCESSING,
                "submitted_at": datetime.utcnow().isoformat(),
                "estimated_completion": (datetime.utcnow() + timedelta(minutes=5)).isoformat()
            }
            
            activity.logger.info(f"Video request submitted successfully: {external_job_id}")
            return result
            
    except ValidationError as e:
        activity.logger.error(f"Validation error in video request: {str(e)}")
        raise  # Don't retry validation errors
    except (httpx.TimeoutException, asyncio.TimeoutError) as e:
        activity.logger.warning(f"Timeout submitting video request: {str(e)}")
        raise TimeoutError(f"Request timeout: {str(e)}")
    except (httpx.ConnectError, httpx.NetworkError) as e:
        activity.logger.warning(f"Network error submitting video request: {str(e)}")
        raise NetworkError(f"Network error: {str(e)}")
    except Exception as e:
        activity.logger.error(f"Unexpected error submitting video request: {str(e)}")
        if is_retryable_error(e):
            raise APIError(f"API error: {str(e)}")
        else:
            raise


@activity.defn
@with_concurrency_control(timeout=180)
async def check_video_status(external_job_id: str, request_id: str) -> Dict[str, Any]:
    """Check status of video generation job.
    
    Args:
        external_job_id: External service job ID
        request_id: Original request ID
        
    Returns:
        Dict containing current status and progress
    """
    activity.logger.info(f"Checking video status: {external_job_id}")
    
    # Send heartbeat for status checking
    if should_send_heartbeat("check_video_status"):
        activity.heartbeat()
    
    try:
        # Validate input
        if not external_job_id or not external_job_id.strip():
            raise ValidationError("External job ID cannot be empty")
        
        # Simulate API call to check status
        async with httpx.AsyncClient(timeout=15.0) as client:
            # This would be replaced with actual status endpoint
            api_url = f"https://api.kling.ai/v1/videos/{external_job_id}/status"
            
            # For demo purposes, simulate status check
            # In real implementation, make actual HTTP request
            # response = await client.get(api_url, headers=headers)
            # 
            # if response.status_code == 404:
            #     raise ValidationError(f"Job not found: {external_job_id}")
            # elif response.status_code == 429:
            #     raise RateLimitError(f"Rate limit exceeded: {response.text}")
            # elif response.status_code >= 500:
            #     raise APIError(f"Server error: {response.status_code} - {response.text}")
            # elif response.status_code >= 400:
            #     raise ValidationError(f"Client error: {response.status_code} - {response.text}")
            
            # Simulated progressive status
            import random
            progress = min(100, random.randint(20, 100))
            
            if progress >= 100:
                status = GenerationStatus.COMPLETED
                video_url = f"https://storage.kling.ai/videos/{external_job_id}.mp4"
                thumbnail_url = f"https://storage.kling.ai/thumbnails/{external_job_id}.jpg"
            else:
                status = GenerationStatus.PROCESSING
                video_url = None
                thumbnail_url = None
            
            result = {
                "status": status,
                "progress": progress,
                "video_url": video_url,
                "thumbnail_url": thumbnail_url,
                "checked_at": datetime.utcnow().isoformat()
            }
            
            activity.logger.info(f"Video status checked: {status}, progress: {progress}%")
            return result
            
    except ValidationError as e:
        activity.logger.error(f"Validation error checking video status: {str(e)}")
        raise  # Don't retry validation errors
    except (httpx.TimeoutException, asyncio.TimeoutError) as e:
        activity.logger.warning(f"Timeout checking video status: {str(e)}")
        raise TimeoutError(f"Status check timeout: {str(e)}")
    except (httpx.ConnectError, httpx.NetworkError) as e:
        activity.logger.warning(f"Network error checking video status: {str(e)}")
        raise NetworkError(f"Network error: {str(e)}")
    except Exception as e:
        activity.logger.error(f"Unexpected error checking video status: {str(e)}")
        if is_retryable_error(e):
            raise APIError(f"API error: {str(e)}")
        else:
            raise


@activity.defn
@with_concurrency_control(timeout=600)
async def download_video_result(video_url: str, request_id: str) -> Dict[str, Any]:
    """Download and store video result.
    
    Args:
        video_url: URL of generated video
        request_id: Original request ID
        
    Returns:
        Dict containing download result and local storage info
    """
    activity.logger.info(f"Downloading video result: {video_url}")
    
    # Send heartbeat for download operations
    if should_send_heartbeat("download_video_result"):
        activity.heartbeat()
    
    try:
        # Validate input
        if not video_url or not video_url.strip():
            raise ValidationError("Video URL cannot be empty")
        if not request_id or not request_id.strip():
            raise ValidationError("Request ID cannot be empty")
        
        # Simulate video download and storage
        async with httpx.AsyncClient(timeout=60.0) as client:
            # In real implementation, download the video file
            # response = await client.get(video_url)
            # 
            # if response.status_code == 404:
            #     raise ValidationError(f"Video not found: {video_url}")
            # elif response.status_code == 403:
            #     raise ValidationError(f"Access denied: {video_url}")
            # elif response.status_code >= 500:
            #     raise APIError(f"Server error downloading video: {response.status_code}")
            # elif response.status_code >= 400:
            #     raise ValidationError(f"Client error downloading video: {response.status_code}")
            # 
            # video_data = response.content
            
            # Send heartbeat during processing
            if should_send_heartbeat("download_video_result"):
                activity.heartbeat()
            
            # Save to local storage or cloud storage
            # local_path = f"storage/videos/{request_id}.mp4"
            # with open(local_path, "wb") as f:
            #     f.write(video_data)
            
            # Simulated result
            local_path = f"storage/videos/{request_id}.mp4"
            file_size = 1024 * 1024 * 10  # 10MB simulated
            
            result = {
                "success": True,
                "local_path": local_path,
                "file_size": file_size,
                "downloaded_at": datetime.utcnow().isoformat()
            }
            
            activity.logger.info(f"Video downloaded successfully: {local_path}")
            return result
            
    except ValidationError as e:
        activity.logger.error(f"Validation error downloading video: {str(e)}")
        raise  # Don't retry validation errors
    except (httpx.TimeoutException, asyncio.TimeoutError) as e:
        activity.logger.warning(f"Timeout downloading video: {str(e)}")
        raise TimeoutError(f"Download timeout: {str(e)}")
    except (httpx.ConnectError, httpx.NetworkError) as e:
        activity.logger.warning(f"Network error downloading video: {str(e)}")
        raise NetworkError(f"Network error: {str(e)}")
    except Exception as e:
        activity.logger.error(f"Unexpected error downloading video: {str(e)}")
        if is_retryable_error(e):
            raise APIError(f"API error: {str(e)}")
        else:
            raise


@activity.defn
@with_concurrency_control(timeout=120)
async def send_video_notification(callback_url: str, video_data: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    """Send notification about video generation completion.
    
    Args:
        callback_url: URL to send notification to
        video_data: Video generation result data
        request_id: Original request ID
        
    Returns:
        Dict containing notification result
    """
    activity.logger.info(f"Sending video notification for request: {request_id}")
    
    # Send heartbeat for notification operations
    if should_send_heartbeat("send_video_notification"):
        activity.heartbeat()
    
    try:
        # Validate input
        if not request_id or not request_id.strip():
            raise ValidationError("Request ID cannot be empty")
        if not video_data:
            raise ValidationError("Video data cannot be empty")
        
        if not callback_url:
            activity.logger.warning("No callback URL provided, skipping notification")
            return {"success": True, "message": "No callback URL provided"}
        
        if not callback_url.strip():
            raise ValidationError("Callback URL cannot be empty")
        
        # Prepare notification payload
        notification_data = {
            "request_id": request_id,
            "status": "completed",
            "video_data": video_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Send webhook notification
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                callback_url,
                json=notification_data,
                headers={"Content-Type": "application/json"}
            )
            
            # Handle different response codes
            if response.status_code == 200:
                activity.logger.info(f"Notification sent successfully to {callback_url}")
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "sent_at": datetime.utcnow().isoformat()
                }
            elif response.status_code == 404:
                raise ValidationError(f"Callback URL not found: {callback_url}")
            elif response.status_code == 429:
                raise RateLimitError(f"Rate limit exceeded for callback: {response.text}")
            elif response.status_code >= 500:
                raise APIError(f"Server error at callback: {response.status_code} - {response.text}")
            elif response.status_code >= 400:
                raise ValidationError(f"Client error at callback: {response.status_code} - {response.text}")
            else:
                activity.logger.warning(f"Unexpected response status {response.status_code}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text
                }
                
    except ValidationError as e:
        activity.logger.error(f"Validation error sending notification: {str(e)}")
        raise  # Don't retry validation errors
    except (httpx.TimeoutException, asyncio.TimeoutError) as e:
        activity.logger.warning(f"Timeout sending notification: {str(e)}")
        raise TimeoutError(f"Notification timeout: {str(e)}")
    except (httpx.ConnectError, httpx.NetworkError) as e:
        activity.logger.warning(f"Network error sending notification: {str(e)}")
        raise NetworkError(f"Network error: {str(e)}")
    except Exception as e:
        activity.logger.error(f"Unexpected error sending notification: {str(e)}")
        if is_retryable_error(e):
            raise APIError(f"API error: {str(e)}")
        else:
            raise