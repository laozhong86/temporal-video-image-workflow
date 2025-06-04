"""Temporal activities for video and image generation."""

from .video_activities import (
    submit_video_request,
    check_video_status,
    download_video_result,
    send_video_notification
)
from .image_activities import (
    submit_image_request,
    check_image_status,
    download_image_result,
    send_image_notification,
    gen_image
)
from .common_activities import (
    validate_request,
    log_activity,
    handle_error
)

# Import from activities.py file
import sys
import os
import importlib.util
activities_py_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'activities.py')
spec = importlib.util.spec_from_file_location("activities_module", activities_py_path)
activities_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activities_module)
request_video = activities_module.request_video
check_video_generation_status = activities_module.check_video_generation_status
download_generated_video = activities_module.download_generated_video

__all__ = [
    # Video activities
    "submit_video_request",
    "check_video_status",
    "download_video_result",
    "send_video_notification",
    # Image activities
    "submit_image_request",
    "check_image_status",
    "download_image_result",
    "send_image_notification",
    "gen_image",
    # Common activities
    "validate_request",
    "log_activity",
    "handle_error",
    # Activities from activities.py
    "request_video",
    "check_video_generation_status",
    "download_generated_video"
]