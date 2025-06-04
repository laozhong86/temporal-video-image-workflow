"""Image generation request and response models."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from .video_request import GenerationStatus


class ImageRequest(BaseModel):
    """Request model for image generation."""
    
    # Basic request info
    request_id: str = Field(..., description="Unique identifier for the request")
    prompt: str = Field(..., description="Text prompt for image generation")
    
    # Image parameters
    width: Optional[int] = Field(default=1024, description="Image width in pixels")
    height: Optional[int] = Field(default=1024, description="Image height in pixels")
    
    # Generation settings
    model: Optional[str] = Field(default="kling-image-v1", description="AI model to use")
    quality: Optional[str] = Field(default="standard", description="Generation quality")
    style: Optional[str] = Field(default=None, description="Image style")
    num_images: Optional[int] = Field(default=1, description="Number of images to generate")
    
    # Callback settings
    callback_url: Optional[str] = Field(default=None, description="URL for status callbacks")
    webhook_secret: Optional[str] = Field(default=None, description="Secret for webhook validation")
    
    # Metadata
    user_id: Optional[str] = Field(default=None, description="User identifier")
    tags: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Request creation time")


class ImageResponse(BaseModel):
    """Response model for image generation."""
    
    # Request info
    request_id: str = Field(..., description="Original request identifier")
    status: GenerationStatus = Field(..., description="Current generation status")
    
    # Result data
    image_urls: Optional[list[str]] = Field(default_factory=list, description="URLs of generated images")
    
    # Progress info
    progress: Optional[float] = Field(default=0.0, description="Generation progress (0-100)")
    estimated_completion: Optional[datetime] = Field(default=None, description="Estimated completion time")
    
    # Error info
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    error_code: Optional[str] = Field(default=None, description="Error code if failed")
    
    # Metadata
    started_at: Optional[datetime] = Field(default=None, description="Processing start time")
    completed_at: Optional[datetime] = Field(default=None, description="Processing completion time")
    processing_time: Optional[float] = Field(default=None, description="Total processing time in seconds")
    
    # Additional data
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional response data")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")