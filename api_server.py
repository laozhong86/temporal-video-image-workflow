#!/usr/bin/env python3
"""
FastAPI Server for Temporal Workflow Signal Handling

This module provides a FastAPI server that handles external callbacks
and sends signals to Temporal workflows for asynchronous processing.

Features:
- Kling API callback handling
- Temporal workflow signal transmission
- Request validation and error handling
- Comprehensive logging
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Request, Query, BackgroundTasks
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
    job_id: str = Field(..., description="Kling job ID")
    status: str = Field(..., description="Job status (completed, failed, etc.)")
    asset_url: Optional[str] = Field(None, description="Generated video URL")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class CallbackResponse(BaseModel):
    """Standard callback response model."""
    success: bool = Field(..., description="Whether callback was processed successfully")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    workflow_id: Optional[str] = Field(None, description="Associated workflow ID")


class TemporalSignalSender:
    """Helper class for sending signals to Temporal workflows."""
    
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
    
    async def send_kling_done_signal(
        self,
        workflow_id: str,
        job_id: str,
        status: str,
        asset_url: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send kling_done signal to a workflow.
        
        Args:
            workflow_id: Target workflow ID
            job_id: Kling job ID
            status: Job status
            asset_url: Generated video URL (if successful)
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
                "asset_url": asset_url,
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
                f"Failed to send signal to workflow {workflow_id}: {e}"
            )
            return False
    
    async def close(self):
        """Close Temporal client connection."""
        if self._client:
            # Temporal Python client doesn't have a close method
        # It cleans itself up when no longer referenced
        pass
            self._client = None
            logger.info("Temporal client connection closed")


# Initialize FastAPI app
app = FastAPI(
    title="Temporal Workflow Signal Handler",
    description="FastAPI server for handling external callbacks and sending Temporal workflow signals",
    version="1.0.0"
)

# Initialize signal sender
signal_sender = TemporalSignalSender()


@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup."""
    logger.info("Starting Temporal Signal Handler API server")
    try:
        # Test Temporal connection
        await signal_sender.get_client()
        logger.info("Temporal connection established successfully")
    except Exception as e:
        logger.error(f"Failed to establish Temporal connection: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown."""
    logger.info("Shutting down Temporal Signal Handler API server")
    await signal_sender.close()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        client = await signal_sender.get_client()
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "temporal_connected": client is not None
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
        )


@app.post("/callback/kling", response_model=CallbackResponse)
async def kling_callback(
    callback_data: KlingCallbackRequest,
    workflow_id: str = Query(..., description="Target workflow ID"),
    background_tasks: BackgroundTasks = None
):
    """Handle Kling API callback and send signal to workflow.
    
    This endpoint receives callbacks from Kling API when video generation
    is completed and forwards the result to the appropriate Temporal workflow
    via the kling_done signal.
    
    Args:
        callback_data: Kling callback data
        workflow_id: Target workflow ID to signal
        background_tasks: FastAPI background tasks
        
    Returns:
        CallbackResponse: Response indicating success/failure
    """
    logger.info(
        f"Received Kling callback for job {callback_data.job_id} "
        f"targeting workflow {workflow_id}"
    )
    
    try:
        # Validate callback data
        if not callback_data.job_id:
            raise HTTPException(
                status_code=400,
                detail="Missing job_id in callback data"
            )
        
        if not workflow_id:
            raise HTTPException(
                status_code=400,
                detail="Missing workflow_id parameter"
            )
        
        # Send signal to workflow
        success = await signal_sender.send_kling_done_signal(
            workflow_id=workflow_id,
            job_id=callback_data.job_id,
            status=callback_data.status,
            asset_url=callback_data.asset_url,
            error_message=callback_data.error_message,
            metadata=callback_data.metadata
        )
        
        if success:
            return CallbackResponse(
                success=True,
                message=f"Signal sent successfully to workflow {workflow_id}",
                workflow_id=workflow_id
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to send signal to workflow"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Kling callback: {e}")
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
        client = await signal_sender.get_client()
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
        client = await signal_sender.get_client()
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


@app.get("/workflows/{workflow_id}/progress")
async def get_workflow_progress(workflow_id: str):
    """Get workflow progress information.
    
    Args:
        workflow_id: Workflow ID to check progress for
        
    Returns:
        dict: Workflow progress information including percentage, status, and details
    """
    try:
        client = await signal_sender.get_client()
        workflow_handle = client.get_workflow_handle(workflow_id)
        
        # Get workflow description first to check if it's running
        description = await workflow_handle.describe()
        
        # Query progress from workflow
        try:
            progress_result = await workflow_handle.query("get_progress")
            
            return {
                "workflow_id": workflow_id,
                "workflow_status": description.status.name,
                "progress": progress_result,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as query_error:
            # If query fails, return basic status info
            logger.warning(f"Failed to query progress for {workflow_id}: {query_error}")
            return {
                "workflow_id": workflow_id,
                "workflow_status": description.status.name,
                "progress": {
                    "percent": 0 if description.status.name == "RUNNING" else 100,
                    "status": "unknown",
                    "message": "Progress information not available"
                },
                "timestamp": datetime.now().isoformat(),
                "error": "Could not retrieve detailed progress information"
            }
        
    except Exception as e:
        logger.error(f"Failed to get workflow progress for {workflow_id}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found or error: {str(e)}"
        )


@app.get("/workflows/{workflow_id}/detailed-status")
async def get_workflow_detailed_status(workflow_id: str):
    """Get detailed workflow status including progress and full state.
    
    Args:
        workflow_id: Workflow ID to check
        
    Returns:
        dict: Detailed workflow status and progress information
    """
    try:
        client = await signal_sender.get_client()
        workflow_handle = client.get_workflow_handle(workflow_id)
        
        # Get workflow description
        description = await workflow_handle.describe()
        
        # Query both progress and status from workflow
        progress_result = None
        status_result = None
        
        try:
            progress_result = await workflow_handle.query("get_progress")
        except Exception as e:
            logger.warning(f"Failed to query progress for {workflow_id}: {e}")
            
        try:
            status_result = await workflow_handle.query("get_status")
        except Exception as e:
            logger.warning(f"Failed to query status for {workflow_id}: {e}")
        
        return {
            "workflow_id": workflow_id,
            "workflow_status": description.status.name,
            "start_time": description.start_time.isoformat() if description.start_time else None,
            "close_time": description.close_time.isoformat() if description.close_time else None,
            "workflow_type": description.workflow_type,
            "task_queue": description.task_queue,
            "progress": progress_result,
            "detailed_status": status_result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get detailed workflow status for {workflow_id}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found or error: {str(e)}"
        )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Temporal Signal Handler API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--temporal-host", default="localhost:7233", help="Temporal server host")
    parser.add_argument("--temporal-namespace", default="default", help="Temporal namespace")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    
    args = parser.parse_args()
    
    # Update signal sender configuration
    signal_sender.temporal_host = args.temporal_host
    signal_sender.namespace = args.temporal_namespace
    
    logger.info(f"Starting server on {args.host}:{args.port}")
    logger.info(f"Temporal server: {args.temporal_host}")
    logger.info(f"Temporal namespace: {args.temporal_namespace}")
    
    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )