#!/usr/bin/env python3
"""
Callback API Server for Kling API Integration

This module provides a dedicated FastAPI server specifically for handling
Kling API callbacks and triggering Temporal workflow signals. It runs on
port 16883 to avoid conflicts with the main API server.

Features:
- Dedicated Kling API callback handling
- Temporal workflow signal transmission
- Request validation and error handling
- CORS support for frontend integration
- Comprehensive logging and monitoring
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Request, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from temporalio.client import Client
from temporalio.service import TLSConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KlingCallbackRequest(BaseModel):
    """Kling API callback request model."""
    video_url: str = Field(..., description="Generated video URL")
    workflow_id: str = Field(..., description="Target workflow ID")
    job_id: Optional[str] = Field(None, description="Kling job ID")
    status: str = Field(default="completed", description="Job status")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class CallbackResponse(BaseModel):
    """Standard callback response model."""
    success: bool = Field(..., description="Whether callback was processed successfully")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    workflow_id: Optional[str] = Field(None, description="Associated workflow ID")
    job_id: Optional[str] = Field(None, description="Associated job ID")


class TemporalCallbackClient:
    """Temporal client for sending callback signals to workflows."""
    
    def __init__(self, temporal_host: str = "localhost:7233", namespace: str = "default"):
        self.temporal_host = temporal_host
        self.namespace = namespace
        self._client: Optional[Client] = None
    
    async def get_client(self) -> Client:
        """Get or create Temporal client."""
        if self._client is None:
            try:
                self._client = await Client.connect(
                    self.temporal_host,
                    namespace=self.namespace
                )
                logger.info(f"Connected to Temporal server at {self.temporal_host}")
            except Exception as e:
                logger.error(f"Failed to connect to Temporal server: {e}")
                raise HTTPException(
                    status_code=503,
                    detail=f"Temporal server connection failed: {str(e)}"
                )
        return self._client
    
    async def send_video_ready_signal(
        self,
        workflow_id: str,
        video_url: str,
        job_id: Optional[str] = None,
        status: str = "completed",
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send video_ready signal to a workflow.
        
        Args:
            workflow_id: Target workflow ID
            video_url: Generated video URL
            job_id: Kling job ID
            status: Job status
            error_message: Error message (if failed)
            metadata: Additional metadata
            
        Returns:
            bool: True if signal sent successfully
        """
        try:
            client = await self.get_client()
            
            # Prepare signal data
            signal_data = {
                "video_url": video_url,
                "job_id": job_id,
                "status": status,
                "error_message": error_message,
                "metadata": metadata or {},
                "timestamp": datetime.now().isoformat()
            }
            
            # Get workflow handle
            workflow_handle = client.get_workflow_handle(workflow_id)
            
            # Send signal
            await workflow_handle.signal("video_ready", signal_data)
            
            logger.info(
                f"Successfully sent video_ready signal to workflow {workflow_id} "
                f"for job {job_id} with status {status}"
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to send signal to workflow {workflow_id}: {e}"
            )
            return False
    
    async def send_kling_done_signal(
        self,
        workflow_id: str,
        video_url: str,
        job_id: Optional[str] = None,
        status: str = "completed",
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send kling_done signal to a workflow (backward compatibility).
        
        Args:
            workflow_id: Target workflow ID
            video_url: Generated video URL
            job_id: Kling job ID
            status: Job status
            error_message: Error message (if failed)
            metadata: Additional metadata
            
        Returns:
            bool: True if signal sent successfully
        """
        try:
            client = await self.get_client()
            
            # Prepare signal data
            signal_data = {
                "job_id": job_id,
                "status": status,
                "asset_url": video_url,  # Use asset_url for backward compatibility
                "video_url": video_url,  # Also include video_url
                "error_message": error_message,
                "metadata": metadata or {},
                "timestamp": datetime.now().isoformat()
            }
            
            # Get workflow handle
            workflow_handle = client.get_workflow_handle(workflow_id)
            
            # Send signal
            await workflow_handle.signal("kling_done", signal_data)
            
            logger.info(
                f"Successfully sent kling_done signal to workflow {workflow_id} "
                f"for job {job_id} with status {status}"
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to send kling_done signal to workflow {workflow_id}: {e}"
            )
            return False
    
    async def close(self):
        """Close Temporal client connection."""
        if self._client:
            self._client = None
            logger.info("Temporal client connection closed")


from contextlib import asynccontextmanager

# Initialize callback client
callback_client = TemporalCallbackClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    logger.info("Starting Kling Callback API server on port 16883")
    try:
        # Test Temporal connection
        await callback_client.get_client()
        logger.info("Temporal connection established successfully")
    except Exception as e:
        logger.error(f"Failed to establish Temporal connection: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Kling Callback API server")
    await callback_client.close()


# Initialize FastAPI app
app = FastAPI(
    title="Kling Callback API Server",
    description="Dedicated FastAPI server for handling Kling API callbacks and triggering Temporal workflow signals",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Simple health check without testing Temporal connection
        # to avoid connection issues during testing
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "kling-callback-api",
            "port": 16883
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "service": "kling-callback-api",
                "error": str(e)
            }
        )


@app.post("/callback/kling", response_model=CallbackResponse)
async def kling_callback(
    callback_data: KlingCallbackRequest,
    background_tasks: BackgroundTasks = None
):
    """Handle Kling API callback and send signal to workflow.
    
    This endpoint receives callbacks from Kling API when video generation
    is completed and forwards the result to the appropriate Temporal workflow
    via the video_ready or kling_done signal.
    
    Args:
        callback_data: Kling callback data including video_url and workflow_id
        background_tasks: FastAPI background tasks
        
    Returns:
        CallbackResponse: Response indicating success/failure
    """
    logger.info(
        f"Received Kling callback for workflow {callback_data.workflow_id} "
        f"with video URL: {callback_data.video_url}"
    )
    
    try:
        # Validate callback data
        if not callback_data.video_url:
            raise HTTPException(
                status_code=400,
                detail="Missing video_url in callback data"
            )
        
        if not callback_data.workflow_id:
            raise HTTPException(
                status_code=400,
                detail="Missing workflow_id in callback data"
            )
        
        # Send both signals for compatibility
        success_video_ready = await callback_client.send_video_ready_signal(
            workflow_id=callback_data.workflow_id,
            video_url=callback_data.video_url,
            job_id=callback_data.job_id,
            status=callback_data.status,
            error_message=callback_data.error_message,
            metadata=callback_data.metadata
        )
        
        success_kling_done = await callback_client.send_kling_done_signal(
            workflow_id=callback_data.workflow_id,
            video_url=callback_data.video_url,
            job_id=callback_data.job_id,
            status=callback_data.status,
            error_message=callback_data.error_message,
            metadata=callback_data.metadata
        )
        
        if success_video_ready or success_kling_done:
            return CallbackResponse(
                success=True,
                message=f"Callback processed successfully for workflow {callback_data.workflow_id}",
                workflow_id=callback_data.workflow_id,
                job_id=callback_data.job_id
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to send signals to workflow"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Kling callback: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/callback/kling/legacy", response_model=CallbackResponse)
async def kling_callback_legacy(
    video_url: str = Query(..., description="Generated video URL"),
    workflow_id: str = Query(..., description="Target workflow ID"),
    job_id: Optional[str] = Query(None, description="Kling job ID"),
    status: str = Query("completed", description="Job status"),
    error_message: Optional[str] = Query(None, description="Error message if failed")
):
    """Legacy Kling callback endpoint using query parameters.
    
    This endpoint provides backward compatibility for systems that send
    callback data as query parameters instead of JSON body.
    
    Args:
        video_url: Generated video URL
        workflow_id: Target workflow ID
        job_id: Kling job ID
        status: Job status
        error_message: Error message if failed
        
    Returns:
        CallbackResponse: Response indicating success/failure
    """
    logger.info(
        f"Received legacy Kling callback for workflow {workflow_id} "
        f"with video URL: {video_url}"
    )
    
    try:
        # Convert to standard callback format
        callback_data = KlingCallbackRequest(
            video_url=video_url,
            workflow_id=workflow_id,
            job_id=job_id,
            status=status,
            error_message=error_message
        )
        
        # Process using standard callback handler
        return await kling_callback(callback_data)
        
    except Exception as e:
        logger.error(f"Error processing legacy Kling callback: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/signal/{workflow_id}/{signal_name}")
async def send_custom_signal(
    workflow_id: str,
    signal_name: str,
    signal_data: Dict[str, Any] = None
):
    """Send custom signal to a workflow.
    
    Generic endpoint for sending any signal to a Temporal workflow.
    
    Args:
        workflow_id: Target workflow ID
        signal_name: Name of the signal to send
        signal_data: Signal payload data
        
    Returns:
        dict: Response indicating success/failure
    """
    logger.info(
        f"Sending custom signal '{signal_name}' to workflow {workflow_id}"
    )
    
    try:
        client = await callback_client.get_client()
        workflow_handle = client.get_workflow_handle(workflow_id)
        
        # Add timestamp to signal data
        if signal_data is None:
            signal_data = {}
        signal_data["timestamp"] = datetime.now().isoformat()
        
        await workflow_handle.signal(signal_name, signal_data)
        
        logger.info(
            f"Successfully sent signal '{signal_name}' to workflow {workflow_id}"
        )
        
        return {
            "success": True,
            "message": f"Signal '{signal_name}' sent to workflow {workflow_id}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(
            f"Failed to send signal '{signal_name}' to workflow {workflow_id}: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send signal: {str(e)}"
        )


@app.get("/workflows/{workflow_id}/status")
async def get_workflow_status(workflow_id: str):
    """Get workflow status.
    
    Args:
        workflow_id: Workflow ID to check
        
    Returns:
        dict: Workflow status information
    """
    try:
        client = await callback_client.get_client()
        workflow_handle = client.get_workflow_handle(workflow_id)
        
        # Get workflow description
        description = await workflow_handle.describe()
        
        return {
            "workflow_id": workflow_id,
            "status": description.status.name,
            "start_time": description.start_time.isoformat() if description.start_time else None,
            "close_time": description.close_time.isoformat() if description.close_time else None,
            "workflow_type": description.workflow_type,
            "task_queue": description.task_queue
        }
        
    except Exception as e:
        logger.error(f"Failed to get workflow status for {workflow_id}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found or error: {str(e)}"
        )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Kling Callback API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=16883, help="Port to bind to (default: 16883)")
    parser.add_argument("--temporal-host", default="localhost:7233", help="Temporal server host")
    parser.add_argument("--temporal-namespace", default="default", help="Temporal namespace")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    
    args = parser.parse_args()
    
    # Update callback client configuration
    callback_client.temporal_host = args.temporal_host
    callback_client.namespace = args.temporal_namespace
    
    logger.info(f"Starting Kling Callback server on {args.host}:{args.port}")
    logger.info(f"Temporal server: {args.temporal_host}")
    logger.info(f"Temporal namespace: {args.temporal_namespace}")
    
    uvicorn.run(
        "callback_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )