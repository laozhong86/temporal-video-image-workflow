"""Data models for the video generation workflow."""

from .video_request import VideoRequest, VideoResponse, GenerationStatus
from .image_request import ImageRequest, ImageResponse
from .core_models import (
    JobInput,
    Progress,
    Step,
    JobStatus,
    WorkflowState,
    JobResult
)

__all__ = [
    "VideoRequest",
    "VideoResponse", 
    "GenerationStatus",
    "ImageRequest",
    "ImageResponse",
    "JobInput",
    "Progress",
    "Step",
    "JobStatus",
    "WorkflowState",
    "JobResult"
]