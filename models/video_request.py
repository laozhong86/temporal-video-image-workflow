"""Video generation request and response models."""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class GenerationStatus(str, Enum):
    """Status of video generation process."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoRequest(BaseModel):
    """Request model for video generation."""
    
    # Basic request info
    request_id: str = Field(..., description="Unique identifier for the request")
    prompt: str = Field(..., description="Text prompt for video generation")
    
    # Video parameters
    duration: Optional[int] = Field(default=5, description="Video duration in seconds")
    width: Optional[int] = Field(default=1280, description="Video width in pixels")
    height: Optional[int] = Field(default=720, description="Video height in pixels")
    fps: Optional[int] = Field(default=24, description="Frames per second")
    
    # Generation settings
    model: Optional[str] = Field(default="kling-v1", description="AI model to use")
    quality: Optional[str] = Field(default="standard", description="Generation quality")
    style: Optional[str] = Field(default=None, description="Video style")
    
    # Callback settings
    callback_url: Optional[str] = Field(default=None, description="URL for status callbacks")
    webhook_secret: Optional[str] = Field(default=None, description="Secret for webhook validation")
    
    # Metadata
    user_id: Optional[str] = Field(default=None, description="User identifier")
    tags: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Request creation time")


class VideoResponse(BaseModel):
    """Response model for video generation."""
    
    # Request info
    request_id: str = Field(..., description="Original request identifier")
    status: GenerationStatus = Field(..., description="Current generation status")
    
    # Result data
    video_url: Optional[str] = Field(default=None, description="URL of generated video")
    thumbnail_url: Optional[str] = Field(default=None, description="URL of video thumbnail")
    
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