#!/usr/bin/env python3
"""
Worker Service Module - Simplified Import

This module provides a simplified import interface for the Temporal Worker Service
used in the Temporal Video Generation System.

This file exists to maintain compatibility with test scripts that expect
a worker_service.py file, while the actual implementation is in worker.py.
"""

# Import the main worker service class
from worker import TemporalWorkerService

# Re-export for easy access
__all__ = [
    'TemporalWorkerService'
]