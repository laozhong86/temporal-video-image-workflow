"""Batch processing workflow for handling multiple generation requests."""

import asyncio
from datetime import timedelta
from typing import Dict, Any, List, Union

from temporalio import workflow
from temporalio.common import RetryPolicy

from models.video_request import VideoRequest, VideoResponse, GenerationStatus
from models.image_request import ImageRequest, ImageResponse
from activities.common_activities import (
    validate_request,
    log_activity,
    handle_error,
    cleanup_resources
)


@workflow.defn
class BatchProcessingWorkflow:
    """Workflow for handling batch processing of multiple generation requests."""
    
    def __init__(self):
        self.batch_id: str = ""
        self.total_requests: int = 0
        self.completed_requests: int = 0
        self.failed_requests: int = 0
        self.child_workflows: List[str] = []
        self.results: List[Dict[str, Any]] = []
    
    @workflow.run
    async def run(self, batch_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main batch processing workflow execution.
        
        Args:
            batch_data: Batch processing request containing multiple requests
            
        Returns:
            Dict containing batch processing results
        """
        self.batch_id = batch_data.get("batch_id", f"batch_{workflow.uuid4()}")
        requests = batch_data.get("requests", [])
        self.total_requests = len(requests)
        
        workflow.logger.info(f"Starting batch processing workflow: {self.batch_id} with {self.total_requests} requests")
        
        try:
            # Log batch start
            await workflow.execute_activity(
                log_activity,
                args=["batch_workflow_start", {
                    "batch_id": self.batch_id,
                    "total_requests": self.total_requests
                }],
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            # Process requests based on strategy
            processing_strategy = batch_data.get("processing_strategy", "parallel")
            max_concurrent = batch_data.get("max_concurrent", 5)
            
            if processing_strategy == "sequential":
                results = await self._process_sequential(requests)
            elif processing_strategy == "parallel":
                results = await self._process_parallel(requests, max_concurrent)
            else:
                raise ValueError(f"Unknown processing strategy: {processing_strategy}")
            
            # Compile final results
            batch_result = {
                "batch_id": self.batch_id,
                "total_requests": self.total_requests,
                "completed_requests": self.completed_requests,
                "failed_requests": self.failed_requests,
                "success_rate": self.completed_requests / self.total_requests if self.total_requests > 0 else 0,
                "results": results,
                "processing_strategy": processing_strategy
            }
            
            # Log batch completion
            await workflow.execute_activity(
                log_activity,
                args=["batch_workflow_complete", batch_result],
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            return batch_result
            
        except Exception as e:
            # Handle batch processing errors
            error_info = await workflow.execute_activity(
                handle_error,
                args=[e, {"workflow": "batch_processing", "batch_id": self.batch_id}],
                start_to_close_timeout=timedelta(seconds=30)
            )
            
            return {
                "batch_id": self.batch_id,
                "total_requests": self.total_requests,
                "completed_requests": self.completed_requests,
                "failed_requests": self.failed_requests,
                "error": error_info["error_message"],
                "results": self.results
            }
    
    async def _process_sequential(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process requests sequentially one by one.
        
        Args:
            requests: List of generation requests
            
        Returns:
            List of processing results
        """
        results = []
        
        for i, request_data in enumerate(requests):
            workflow.logger.info(f"Processing request {i+1}/{len(requests)} in batch {self.batch_id}")
            
            try:
                result = await self._process_single_request(request_data, i)
                results.append(result)
                
                if result.get("status") == "completed":
                    self.completed_requests += 1
                else:
                    self.failed_requests += 1
                    
            except Exception as e:
                self.failed_requests += 1
                results.append({
                    "request_index": i,
                    "request_id": request_data.get("request_id", f"unknown_{i}"),
                    "status": "failed",
                    "error": str(e)
                })
        
        return results
    
    async def _process_parallel(self, requests: List[Dict[str, Any]], max_concurrent: int) -> List[Dict[str, Any]]:
        """Process requests in parallel with concurrency limit.
        
        Args:
            requests: List of generation requests
            max_concurrent: Maximum number of concurrent requests
            
        Returns:
            List of processing results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(request_data: Dict[str, Any], index: int) -> Dict[str, Any]:
            async with semaphore:
                try:
                    result = await self._process_single_request(request_data, index)
                    
                    if result.get("status") == "completed":
                        self.completed_requests += 1
                    else:
                        self.failed_requests += 1
                    
                    return result
                    
                except Exception as e:
                    self.failed_requests += 1
                    return {
                        "request_index": index,
                        "request_id": request_data.get("request_id", f"unknown_{index}"),
                        "status": "failed",
                        "error": str(e)
                    }
        
        # Create tasks for all requests
        tasks = [
            process_with_semaphore(request_data, i)
            for i, request_data in enumerate(requests)
        ]
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions that weren't caught
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.failed_requests += 1
                processed_results.append({
                    "request_index": i,
                    "request_id": requests[i].get("request_id", f"unknown_{i}"),
                    "status": "failed",
                    "error": str(result)
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _process_single_request(self, request_data: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Process a single generation request.
        
        Args:
            request_data: Individual request data
            index: Request index in batch
            
        Returns:
            Processing result for the request
        """
        request_type = request_data.get("type", "unknown")
        request_id = request_data.get("request_id", f"batch_{self.batch_id}_req_{index}")
        
        # Determine workflow type
        if request_type == "video":
            workflow_type = "VideoGenerationWorkflow"
        elif request_type == "image":
            workflow_type = "ImageGenerationWorkflow"
        else:
            raise ValueError(f"Unknown request type: {request_type}")
        
        # Start child workflow
        child_workflow_id = f"{self.batch_id}_child_{index}"
        self.child_workflows.append(child_workflow_id)
        
        try:
            # Execute child workflow
            if request_type == "video":
                from workflows.video_workflow import VideoGenerationWorkflow
                result = await workflow.execute_child_workflow(
                    VideoGenerationWorkflow.run,
                    args=[request_data],
                    id=child_workflow_id,
                    task_queue="generation-queue",
                    execution_timeout=timedelta(hours=2)
                )
            else:  # image
                from workflows.image_workflow import ImageGenerationWorkflow
                result = await workflow.execute_child_workflow(
                    ImageGenerationWorkflow.run,
                    args=[request_data],
                    id=child_workflow_id,
                    task_queue="generation-queue",
                    execution_timeout=timedelta(hours=1)
                )
            
            # Convert result to dict for serialization
            if hasattr(result, '__dict__'):
                result_dict = result.__dict__.copy()
            else:
                result_dict = result
            
            return {
                "request_index": index,
                "request_id": request_id,
                "request_type": request_type,
                "status": "completed" if result_dict.get("status") == GenerationStatus.COMPLETED else "failed",
                "child_workflow_id": child_workflow_id,
                "result": result_dict
            }
            
        except Exception as e:
            workflow.logger.error(f"Child workflow failed for request {request_id}: {str(e)}")
            raise
    
    @workflow.signal
    async def cancel_batch(self):
        """Signal to cancel the entire batch processing."""
        workflow.logger.info(f"Cancellation requested for batch: {self.batch_id}")
        # In a real implementation, you would:
        # 1. Cancel all running child workflows
        # 2. Clean up resources
        # 3. Update batch status
    
    @workflow.query
    def get_progress(self) -> Dict[str, Any]:
        """Query current batch processing progress.
        
        Returns:
            Dict containing current progress information
        """
        return {
            "batch_id": self.batch_id,
            "total_requests": self.total_requests,
            "completed_requests": self.completed_requests,
            "failed_requests": self.failed_requests,
            "progress_percentage": (self.completed_requests + self.failed_requests) / self.total_requests * 100 if self.total_requests > 0 else 0,
            "active_child_workflows": len(self.child_workflows)
        }
    
    @workflow.signal
    async def pause_batch(self):
        """Signal to pause batch processing."""
        workflow.logger.info(f"Pause requested for batch: {self.batch_id}")
        # Implementation would depend on the specific requirements
    
    @workflow.signal
    async def resume_batch(self):
        """Signal to resume paused batch processing."""
        workflow.logger.info(f"Resume requested for batch: {self.batch_id}")
        # Implementation would depend on the specific requirements