#!/usr/bin/env python3
"""
Test Script for Kling Callback API Server

This script tests the callback server functionality by:
1. Starting a test workflow
2. Sending mock callback requests
3. Verifying signal delivery
4. Testing error handling
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

import httpx
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
CALLBACK_SERVER_URL = "http://localhost:16883"
TEMPORAL_HOST = "localhost:7233"
TASK_QUEUE = "test-callback-queue"


@activity
async def test_activity() -> str:
    """Simple test activity."""
    logger.info("Executing test activity")
    return "Test activity completed"


@workflow.defn
class TestCallbackWorkflow:
    """Test workflow for callback testing."""
    
    def __init__(self):
        self.video_ready_received = False
        self.kling_done_received = False
        self.video_url = None
        self.callback_data = None
    
    @workflow.run
    async def run(self) -> Dict[str, Any]:
        """Main workflow execution."""
        logger.info("Starting test callback workflow")
        
        # Execute a test activity
        result = await workflow.execute_activity(
            test_activity,
            start_to_close_timeout=30
        )
        
        # Wait for callback signals
        logger.info("Waiting for callback signals...")
        
        # Wait for either video_ready or kling_done signal (or timeout)
        try:
            await workflow.wait_condition(
                lambda: self.video_ready_received or self.kling_done_received,
                timeout=60  # 60 seconds timeout
            )
            
            return {
                "status": "completed",
                "activity_result": result,
                "video_ready_received": self.video_ready_received,
                "kling_done_received": self.kling_done_received,
                "video_url": self.video_url,
                "callback_data": self.callback_data,
                "timestamp": datetime.now().isoformat()
            }
            
        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "activity_result": result,
                "video_ready_received": self.video_ready_received,
                "kling_done_received": self.kling_done_received,
                "message": "Timeout waiting for callback signals",
                "timestamp": datetime.now().isoformat()
            }
    
    @workflow.signal
    async def video_ready(self, data: Dict[str, Any]):
        """Handle video_ready signal."""
        logger.info(f"Received video_ready signal: {data}")
        self.video_ready_received = True
        self.video_url = data.get("video_url")
        self.callback_data = data
    
    @workflow.signal
    async def kling_done(self, data: Dict[str, Any]):
        """Handle kling_done signal."""
        logger.info(f"Received kling_done signal: {data}")
        self.kling_done_received = True
        self.video_url = data.get("asset_url") or data.get("video_url")
        self.callback_data = data
    
    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """Get current workflow status."""
        return {
            "video_ready_received": self.video_ready_received,
            "kling_done_received": self.kling_done_received,
            "video_url": self.video_url,
            "callback_data": self.callback_data
        }


class CallbackServerTester:
    """Test harness for callback server."""
    
    def __init__(self):
        self.client = None
        self.worker = None
        self.http_client = httpx.AsyncClient()
    
    async def setup(self):
        """Setup Temporal client and worker."""
        logger.info("Setting up test environment...")
        
        # Connect to Temporal
        self.client = await Client.connect(TEMPORAL_HOST)
        
        # Create worker
        self.worker = Worker(
            self.client,
            task_queue=TASK_QUEUE,
            workflows=[TestCallbackWorkflow],
            activities=[test_activity]
        )
    
    async def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up test environment...")
        
        if self.http_client:
            await self.http_client.aclose()
        
        if self.worker:
            # Worker cleanup is handled automatically
            pass
    
    async def test_callback_server_health(self) -> bool:
        """Test callback server health endpoint."""
        logger.info("Testing callback server health...")
        
        try:
            response = await self.http_client.get(f"{CALLBACK_SERVER_URL}/health")
            
            if response.status_code == 200:
                health_data = response.json()
                logger.info(f"Callback server health: {health_data}")
                return health_data.get("status") == "healthy"
            else:
                logger.error(f"Health check failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to callback server: {e}")
            return False
    
    async def test_callback_endpoint(self, workflow_id: str) -> bool:
        """Test callback endpoint with mock data."""
        logger.info(f"Testing callback endpoint for workflow {workflow_id}...")
        
        # Test data
        callback_data = {
            "video_url": "https://example.com/test-video.mp4",
            "workflow_id": workflow_id,
            "job_id": "test-job-123",
            "status": "completed",
            "metadata": {
                "test": True,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        try:
            response = await self.http_client.post(
                f"{CALLBACK_SERVER_URL}/callback/kling",
                json=callback_data
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Callback response: {result}")
                return result.get("success", False)
            else:
                logger.error(f"Callback failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send callback: {e}")
            return False
    
    async def test_legacy_callback_endpoint(self, workflow_id: str) -> bool:
        """Test legacy callback endpoint with query parameters."""
        logger.info(f"Testing legacy callback endpoint for workflow {workflow_id}...")
        
        # Test parameters
        params = {
            "video_url": "https://example.com/test-video-legacy.mp4",
            "workflow_id": workflow_id,
            "job_id": "test-job-legacy-456",
            "status": "completed"
        }
        
        try:
            response = await self.http_client.post(
                f"{CALLBACK_SERVER_URL}/callback/kling/legacy",
                params=params
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Legacy callback response: {result}")
                return result.get("success", False)
            else:
                logger.error(f"Legacy callback failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send legacy callback: {e}")
            return False
    
    async def test_error_handling(self) -> bool:
        """Test error handling with invalid data."""
        logger.info("Testing error handling...")
        
        # Test with missing required fields
        invalid_data = {
            "job_id": "test-job-error",
            "status": "completed"
            # Missing video_url and workflow_id
        }
        
        try:
            response = await self.http_client.post(
                f"{CALLBACK_SERVER_URL}/callback/kling",
                json=invalid_data
            )
            
            # Should return 400 or 422 for validation error
            if response.status_code in [400, 422]:
                logger.info(f"Error handling working correctly: {response.status_code}")
                return True
            else:
                logger.error(f"Expected error response, got: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to test error handling: {e}")
            return False
    
    async def run_workflow_test(self) -> bool:
        """Run complete workflow test."""
        logger.info("Starting workflow test...")
        
        # Start worker in background
        worker_task = asyncio.create_task(self.worker.run())
        
        try:
            # Start test workflow
            workflow_id = f"test-callback-workflow-{int(datetime.now().timestamp())}"
            
            workflow_handle = await self.client.start_workflow(
                TestCallbackWorkflow.run,
                id=workflow_id,
                task_queue=TASK_QUEUE
            )
            
            logger.info(f"Started test workflow: {workflow_id}")
            
            # Wait a moment for workflow to start
            await asyncio.sleep(2)
            
            # Send callback
            callback_success = await self.test_callback_endpoint(workflow_id)
            
            if not callback_success:
                logger.error("Callback sending failed")
                return False
            
            # Wait for workflow to complete
            result = await workflow_handle.result()
            
            logger.info(f"Workflow result: {result}")
            
            # Check if signals were received
            success = (
                result.get("status") == "completed" and
                (result.get("video_ready_received") or result.get("kling_done_received"))
            )
            
            if success:
                logger.info("✅ Workflow test passed!")
            else:
                logger.error("❌ Workflow test failed!")
            
            return success
            
        finally:
            # Stop worker
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
    
    async def run_all_tests(self) -> bool:
        """Run all tests."""
        logger.info("🚀 Starting callback server tests...")
        
        tests = [
            ("Health Check", self.test_callback_server_health()),
            ("Error Handling", self.test_error_handling()),
            ("Workflow Integration", self.run_workflow_test())
        ]
        
        results = []
        
        for test_name, test_coro in tests:
            logger.info(f"\n📋 Running test: {test_name}")
            try:
                result = await test_coro
                results.append((test_name, result))
                status = "✅ PASSED" if result else "❌ FAILED"
                logger.info(f"Test {test_name}: {status}")
            except Exception as e:
                logger.error(f"Test {test_name} failed with exception: {e}")
                results.append((test_name, False))
        
        # Summary
        logger.info("\n📊 Test Summary:")
        all_passed = True
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"  {test_name}: {status}")
            if not result:
                all_passed = False
        
        if all_passed:
            logger.info("\n🎉 All tests passed!")
        else:
            logger.info("\n💥 Some tests failed!")
        
        return all_passed


async def main():
    """Main test function."""
    tester = CallbackServerTester()
    
    try:
        await tester.setup()
        success = await tester.run_all_tests()
        return 0 if success else 1
    
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        return 1
    
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    import sys
    
    print("Kling Callback Server Test Suite")
    print("================================")
    print(f"Callback Server: {CALLBACK_SERVER_URL}")
    print(f"Temporal Server: {TEMPORAL_HOST}")
    print("")
    print("Make sure the callback server is running on port 16883")
    print("Run: python3 callback_server.py --port 16883")
    print("")
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)