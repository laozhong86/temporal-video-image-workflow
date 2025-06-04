#!/usr/bin/env python3
"""
Models Module - Simplified Import

This module provides a simplified import interface for all model classes
used in the Temporal Video Generation System.

This file exists to maintain compatibility with test scripts that expect
a single models.py file, while the actual model definitions are organized
in the models/ directory.
"""

# Import all models from the models package
from models import (
    VideoRequest,
    VideoResponse,
    GenerationStatus,
    ImageRequest,
    ImageResponse
)

# Re-export all models for easy access
__all__ = [
    'VideoRequest',
    'VideoResponse', 
    'GenerationStatus',
    'ImageRequest',
    'ImageResponse'
]