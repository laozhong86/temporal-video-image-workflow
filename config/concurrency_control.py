# -*- coding: utf-8 -*-
"""
Global Concurrency Control for Temporal Activities

This module provides semaphore-based concurrency control to ensure only one task
executes simultaneously for reliability testing and resource management.
"""

import asyncio
import logging
from typing import Optional, Any, Callable
from functools import wraps
from temporalio import activity
from datetime import timedelta

# Configure logging
logger = logging.getLogger(__name__)

# Global semaphore for concurrency control
# Using asyncio.Semaphore(1) to ensure only one task executes at a time
GLOBAL_SEMAPHORE: Optional[asyncio.Semaphore] = None

# Semaphore timeout configuration
SEMAPHORE_TIMEOUT = 300  # 5 minutes timeout for semaphore acquisition


def get_global_semaphore() -> asyncio.Semaphore:
    """
    Get or create the global semaphore for concurrency control.
    
    Returns:
        asyncio.Semaphore: Global semaphore instance
    """
    global GLOBAL_SEMAPHORE
    if GLOBAL_SEMAPHORE is None:
        GLOBAL_SEMAPHORE = asyncio.Semaphore(1)
        logger.info("Global semaphore initialized with capacity 1")
    return GLOBAL_SEMAPHORE


class SemaphoreTimeoutError(Exception):
    """Raised when semaphore acquisition times out."""
    pass


class ConcurrencyControlContext:
    """
    Async context manager for semaphore-based concurrency control.
    
    Provides automatic acquisition and release of the global semaphore
    with timeout handling and deadlock prevention.
    """
    
    def __init__(self, timeout: float = SEMAPHORE_TIMEOUT, activity_name: str = "unknown"):
        self.timeout = timeout
        self.activity_name = activity_name
        self.semaphore = get_global_semaphore()
        self.acquired = False
    
    async def __aenter__(self):
        """Acquire the semaphore with timeout."""
        try:
            logger.info(f"Attempting to acquire semaphore for activity: {self.activity_name}")
            
            # Use asyncio.wait_for to implement timeout
            await asyncio.wait_for(
                self.semaphore.acquire(),
                timeout=self.timeout
            )
            
            self.acquired = True
            logger.info(f"Semaphore acquired for activity: {self.activity_name}")
            
            # Send heartbeat to indicate activity is starting
            if hasattr(activity, 'heartbeat'):
                activity.heartbeat()
            
            return self
            
        except asyncio.TimeoutError:
            error_msg = f"Timeout acquiring semaphore for activity: {self.activity_name} (timeout: {self.timeout}s)"
            logger.error(error_msg)
            raise SemaphoreTimeoutError(error_msg)
        except Exception as e:
            error_msg = f"Error acquiring semaphore for activity: {self.activity_name}: {str(e)}"
            logger.error(error_msg)
            raise
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release the semaphore."""
        if self.acquired:
            try:
                self.semaphore.release()
                logger.info(f"Semaphore released for activity: {self.activity_name}")
                
                # Log any exception that occurred during activity execution
                if exc_type is not None:
                    logger.warning(f"Activity {self.activity_name} completed with exception: {exc_type.__name__}: {exc_val}")
                else:
                    logger.info(f"Activity {self.activity_name} completed successfully")
                    
            except Exception as e:
                logger.error(f"Error releasing semaphore for activity: {self.activity_name}: {str(e)}")
        
        # Don't suppress any exceptions
        return False


def with_concurrency_control(timeout: float = SEMAPHORE_TIMEOUT):
    """
    Decorator to add concurrency control to Temporal activities.
    
    Args:
        timeout (float): Timeout in seconds for semaphore acquisition
        
    Returns:
        Callable: Decorated function with concurrency control
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            activity_name = getattr(func, '__name__', 'unknown')
            
            async with ConcurrencyControlContext(timeout=timeout, activity_name=activity_name):
                # Send periodic heartbeats during long-running operations
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    logger.error(f"Activity {activity_name} failed: {str(e)}")
                    raise
        
        return wrapper
    return decorator


@activity.defn
async def acquire_global_semaphore(activity_name: str, timeout: float = SEMAPHORE_TIMEOUT) -> bool:
    """
    Temporal Activity to acquire the global semaphore for distributed coordination.
    
    This activity can be used in workflows to ensure distributed coordination
    across multiple workers.
    
    Args:
        activity_name (str): Name of the activity requesting the semaphore
        timeout (float): Timeout in seconds for semaphore acquisition
        
    Returns:
        bool: True if semaphore was acquired successfully
        
    Raises:
        SemaphoreTimeoutError: If semaphore acquisition times out
    """
    activity.logger.info(f"Acquiring global semaphore for distributed activity: {activity_name}")
    
    try:
        semaphore = get_global_semaphore()
        
        await asyncio.wait_for(
            semaphore.acquire(),
            timeout=timeout
        )
        
        activity.logger.info(f"Global semaphore acquired for distributed activity: {activity_name}")
        return True
        
    except asyncio.TimeoutError:
        error_msg = f"Timeout acquiring global semaphore for activity: {activity_name} (timeout: {timeout}s)"
        activity.logger.error(error_msg)
        raise SemaphoreTimeoutError(error_msg)
    except Exception as e:
        error_msg = f"Error acquiring global semaphore for activity: {activity_name}: {str(e)}"
        activity.logger.error(error_msg)
        raise


@activity.defn
async def release_global_semaphore(activity_name: str) -> bool:
    """
    Temporal Activity to release the global semaphore for distributed coordination.
    
    Args:
        activity_name (str): Name of the activity releasing the semaphore
        
    Returns:
        bool: True if semaphore was released successfully
    """
    activity.logger.info(f"Releasing global semaphore for distributed activity: {activity_name}")
    
    try:
        semaphore = get_global_semaphore()
        semaphore.release()
        
        activity.logger.info(f"Global semaphore released for distributed activity: {activity_name}")
        return True
        
    except Exception as e:
        error_msg = f"Error releasing global semaphore for activity: {activity_name}: {str(e)}"
        activity.logger.error(error_msg)
        raise


# Utility functions for semaphore management

def reset_global_semaphore():
    """
    Reset the global semaphore. Useful for testing or recovery scenarios.
    """
    global GLOBAL_SEMAPHORE
    GLOBAL_SEMAPHORE = None
    logger.info("Global semaphore reset")


def get_semaphore_status() -> dict:
    """
    Get the current status of the global semaphore.
    
    Returns:
        dict: Semaphore status information
    """
    semaphore = get_global_semaphore()
    return {
        "locked": semaphore.locked(),
        "value": semaphore._value if hasattr(semaphore, '_value') else None,
        "waiters": len(semaphore._waiters) if hasattr(semaphore, '_waiters') else 0
    }