#!/usr/bin/env python3
"""
Simple test for callback server
"""

import httpx
import asyncio
import json
from datetime import datetime

async def test_callback_server():
    """Test callback server endpoints."""
    
    # Disable proxy for localhost connections
    async with httpx.AsyncClient(proxies={}) as client:
        try:
            # Test health endpoint
            print("Testing health endpoint...")
            response = await client.get("http://localhost:16883/health")
            print(f"Health check status: {response.status_code}")
            if response.status_code == 200:
                print(f"Health response: {response.json()}")
            
            # Test callback endpoint with mock data
            print("\nTesting callback endpoint...")
            callback_data = {
                "video_url": "https://example.com/test-video.mp4",
                "workflow_id": "test-workflow-123",
                "job_id": "test-job-456",
                "status": "completed",
                "metadata": {
                    "test": True,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            response = await client.post(
                "http://localhost:16883/callback/kling",
                json=callback_data
            )
            print(f"Callback status: {response.status_code}")
            if response.status_code == 200:
                print(f"Callback response: {response.json()}")
            else:
                print(f"Callback error: {response.text}")
            
            # Test legacy callback endpoint
            print("\nTesting legacy callback endpoint...")
            params = {
                "video_url": "https://example.com/test-video-legacy.mp4",
                "workflow_id": "test-workflow-legacy-789",
                "job_id": "test-job-legacy-101",
                "status": "completed"
            }
            
            response = await client.post(
                "http://localhost:16883/callback/kling/legacy",
                params=params
            )
            print(f"Legacy callback status: {response.status_code}")
            if response.status_code == 200:
                print(f"Legacy callback response: {response.json()}")
            else:
                print(f"Legacy callback error: {response.text}")
            
            print("\n✅ All tests completed successfully!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    print("Simple Callback Server Test")
    print("===========================\n")
    
    asyncio.run(test_callback_server())