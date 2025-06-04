import asyncio
import httpx
from temporalio import activity
from typing import Dict, Any
from models.core_models import JobInput
from config.retry_policies import (
    get_retry_policy, 
    should_send_heartbeat, 
    is_retryable_error,
    ValidationError,
    APIError,
    NetworkError,
    TimeoutError,
    RateLimitError
)
from config.concurrency_control import with_concurrency_control

# Mock models for existing functions
class ImageRequest:
    def __init__(self, prompt: str, style: str = "realistic"):
        self.prompt = prompt
        self.style = style
        self.width = 1024
        self.height = 1024

class ImageResponse:
    def __init__(self, image_url: str, status: str = "completed"):
        self.image_url = image_url
        self.status = status

class GenerationStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@activity.defn
@with_concurrency_control(timeout=300)
async def submit_image_request(request: ImageRequest) -> Dict[str, Any]:
    """Submit an image generation request to external service.
    
    Args:
        request: Image generation request containing prompt and parameters
        
    Returns:
        Dict containing job_id and status
    """
    activity.logger.info(f"Submitting image request: {request.prompt[:50]}...")
    
    # Send heartbeat for submission
    if should_send_heartbeat("submit_image_request"):
        activity.heartbeat()
    
    try:
        # Validate input
        if not request.prompt or not request.prompt.strip():
            raise ValidationError("Image prompt cannot be empty")
        
        # Simulate API call to external image generation service
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Mock external API endpoint
            api_url = "https://api.example-image-service.com/generate"
            
            payload = {
                "prompt": request.prompt,
                "style": request.style,
                "width": request.width,
                "height": request.height
            }
            
            # Simulate API response
            response = {
                "job_id": f"img_{hash(request.prompt) % 10000}",
                "status": GenerationStatus.PENDING,
                "estimated_time": 30
            }
            
            activity.logger.info(f"Image request submitted with job_id: {response['job_id']}")
            return response
            
    except ValidationError as e:
        activity.logger.error(f"Validation error submitting image request: {str(e)}")
        raise  # Don't retry validation errors
    except (httpx.TimeoutException, asyncio.TimeoutError) as e:
        activity.logger.warning(f"Timeout submitting image request: {str(e)}")
        raise TimeoutError(f"Submission timeout: {str(e)}")
    except (httpx.ConnectError, httpx.NetworkError) as e:
        activity.logger.warning(f"Network error submitting image request: {str(e)}")
        raise NetworkError(f"Network error: {str(e)}")
    except Exception as e:
        activity.logger.error(f"Unexpected error submitting image request: {str(e)}")
        if is_retryable_error(e):
            raise APIError(f"API error: {str(e)}")
        else:
            raise


@activity.defn
@with_concurrency_control(timeout=180)
async def check_image_status(job_id: str) -> Dict[str, Any]:
    """Check the status of an image generation job.
    
    Args:
        job_id: The job identifier returned from submit_image_request
        
    Returns:
        Dict containing status and progress information
    """
    activity.logger.info(f"Checking status for job: {job_id}")
    
    # Send heartbeat for status checking
    if should_send_heartbeat("check_image_status"):
        activity.heartbeat()
    
    try:
        # Validate input
        if not job_id or not job_id.strip():
            raise ValidationError("Job ID cannot be empty")
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Mock status check API
            api_url = f"https://api.example-image-service.com/status/{job_id}"
            
            # In real implementation, make actual HTTP request
            # response = await client.get(api_url, headers=headers)
            # 
            # if response.status_code == 404:
            #     raise ValidationError(f"Job not found: {job_id}")
            # elif response.status_code == 429:
            #     raise RateLimitError(f"Rate limit exceeded: {response.text}")
            # elif response.status_code >= 500:
            #     raise APIError(f"Server error: {response.status_code} - {response.text}")
            # elif response.status_code >= 400:
            #     raise ValidationError(f"Client error: {response.status_code} - {response.text}")
            
            # Simulate different status responses
            import random
            progress = random.randint(0, 100)
            
            if progress < 30:
                status = GenerationStatus.PENDING
            elif progress < 100:
                status = GenerationStatus.PROCESSING
            else:
                status = GenerationStatus.COMPLETED
            
            response = {
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "estimated_remaining": max(0, 30 - progress // 3)
            }
            
            activity.logger.info(f"Job {job_id} status: {status} ({progress}%)")
            return response
            
    except ValidationError as e:
        activity.logger.error(f"Validation error checking image status: {str(e)}")
        raise  # Don't retry validation errors
    except (httpx.TimeoutException, asyncio.TimeoutError) as e:
        activity.logger.warning(f"Timeout checking image status: {str(e)}")
        raise TimeoutError(f"Status check timeout: {str(e)}")
    except (httpx.ConnectError, httpx.NetworkError) as e:
        activity.logger.warning(f"Network error checking image status: {str(e)}")
        raise NetworkError(f"Network error: {str(e)}")
    except Exception as e:
        activity.logger.error(f"Unexpected error checking image status: {str(e)}")
        if is_retryable_error(e):
            raise APIError(f"API error: {str(e)}")
        else:
            raise


@activity.defn
@with_concurrency_control(timeout=600)
async def download_image_result(job_id: str) -> Dict[str, Any]:
    """Download the generated image result.
    
    Args:
        job_id: The job identifier for the completed generation
        
    Returns:
        Dict containing image URL and metadata
    """
    activity.logger.info(f"Downloading result for job: {job_id}")
    
    try:
        async with httpx.AsyncClient() as client:
            # Mock result download API
            result_url = f"https://api.example-image-service.com/result/{job_id}"
            
            # Simulate downloading image
            image_url = f"https://cdn.example-service.com/images/{job_id}.png"
            
            # Mock local storage path
            local_path = f"/tmp/generated_images/{job_id}.png"
            
            response = {
                "job_id": job_id,
                "image_url": image_url,
                "local_path": local_path,
                "file_size": 1024 * 512,  # 512KB
                "format": "PNG",
                "dimensions": {"width": 1024, "height": 1024}
            }
            
            activity.logger.info(f"Image downloaded successfully: {image_url}")
            return response
            
    except Exception as e:
        activity.logger.error(f"Failed to download result for job {job_id}: {str(e)}")
        return {
            "job_id": job_id,
            "error": str(e),
            "success": False
        }


@activity.defn
@with_concurrency_control(timeout=120)
async def send_image_notification(request: ImageRequest, response: ImageResponse) -> Dict[str, Any]:
    """Send notification about image generation completion.
    
    Args:
        request: Original image request
        response: Generated image response
        
    Returns:
        Dict containing notification status
    """
    activity.logger.info(f"Sending notification for image generation")
    
    try:
        # Mock notification service (webhook, email, etc.)
        notification_data = {
            "event": "image_generation_completed",
            "prompt": request.prompt,
            "image_url": response.image_url,
            "status": response.status,
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        async with httpx.AsyncClient() as client:
            # Mock webhook endpoint
            webhook_url = "https://api.client-app.com/webhooks/image-completed"
            
            # Simulate sending notification
            activity.logger.info("Notification sent successfully")
            
            return {
                "notification_sent": True,
                "webhook_url": webhook_url,
                "event_type": "image_generation_completed"
            }
            
    except Exception as e:
        activity.logger.error(f"Failed to send notification: {str(e)}")
        return {
            "notification_sent": False,
            "error": str(e)
        }


@activity.defn
@with_concurrency_control(timeout=600)
async def gen_image(job_input: JobInput) -> str:
    """Generate image using ComfyUI API.
    
    Args:
        job_input: Job input containing prompt and generation parameters
        
    Returns:
        str: Final image URL
        
    Raises:
        Exception: If image generation fails
    """
    activity.logger.info(f"Starting image generation with prompt: {job_input.prompt[:50]}...")
    
    # ComfyUI API base URL
    base_url = "http://81.70.239.227:6889"
    timeout = httpx.Timeout(300.0)  # 5 minutes timeout
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Step 1: Submit image generation job
            submit_payload = {
                "prompt": job_input.prompt,
                "style": job_input.style,
                "width": getattr(job_input, 'width', 1024),
                "height": getattr(job_input, 'height', 1024)
            }
            
            activity.logger.info("Submitting image generation request to ComfyUI")
            submit_response = await client.post(
                f"{base_url}/img/submit",
                json=submit_payload
            )
            submit_response.raise_for_status()
            submit_data = submit_response.json()
            
            job_id = submit_data.get("job_id")
            if not job_id:
                raise Exception("No job_id returned from ComfyUI submit endpoint")
            
            activity.logger.info(f"Image generation job submitted with ID: {job_id}")
            
            # Step 2: Poll for status with exponential backoff
            poll_intervals = [1, 2, 4]  # seconds
            max_polls = 150  # Maximum number of polls (about 5 minutes)
            
            for poll_count in range(max_polls):
                # Wait before polling (except first time)
                if poll_count > 0:
                    interval_index = min(poll_count, len(poll_intervals) - 1)
                    sleep_time = poll_intervals[interval_index]
                    activity.logger.info(f"Waiting {sleep_time}s before next status check")
                    await asyncio.sleep(sleep_time)
                
                # Check job status
                activity.logger.info(f"Checking status for job {job_id} (poll #{poll_count + 1})")
                status_response = await client.get(f"{base_url}/img/status/{job_id}")
                status_response.raise_for_status()
                status_data = status_response.json()
                
                status = status_data.get("status")
                progress = status_data.get("progress", 0)
                
                activity.logger.info(f"Job {job_id} status: {status}, progress: {progress}%")
                
                if status == "completed":
                    activity.logger.info(f"Image generation completed for job {job_id}")
                    break
                elif status == "failed":
                    error_msg = status_data.get("error", "Unknown error")
                    raise Exception(f"Image generation failed: {error_msg}")
                elif status in ["cancelled", "timeout"]:
                    raise Exception(f"Image generation {status} for job {job_id}")
            
            # If we reach here, we've exhausted all polls
            if True:  # This will only execute if loop completes without break
                raise Exception(f"Image generation timed out after {max_polls} polls")
            
            # Step 3: Get the final result
            activity.logger.info(f"Fetching result for completed job {job_id}")
            result_response = await client.get(f"{base_url}/img/result/{job_id}")
            result_response.raise_for_status()
            result_data = result_response.json()
            
            image_url = result_data.get("image_url")
            if not image_url:
                raise Exception("No image_url returned from ComfyUI result endpoint")
            
            activity.logger.info(f"Image generation successful. URL: {image_url}")
            return image_url
            
    except httpx.TimeoutException:
        error_msg = "ComfyUI API request timed out"
        activity.logger.error(error_msg)
        raise Exception(error_msg)
    except httpx.HTTPStatusError as e:
        error_msg = f"ComfyUI API returned error {e.response.status_code}: {e.response.text}"
        activity.logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        activity.logger.error(f"Image generation failed: {str(e)}")
        raise