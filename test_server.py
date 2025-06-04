#!/usr/bin/env python3
"""
Test script for callback server
"""

import asyncio
import subprocess
import time
import signal
import os
import sys
import httpx


async def test_server():
    """Test the callback server."""
    # Start server in background
    print("Starting callback server...")
    server_process = subprocess.Popen(
        [sys.executable, "callback_server.py", "--host", "127.0.0.1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        preexec_fn=os.setsid  # Create new process group
    )
    
    # Wait for server to start
    print("Waiting for server to start...")
    await asyncio.sleep(3)
    
    try:
        # Test health endpoint
        print("Testing /health endpoint...")
        async with httpx.AsyncClient(proxies={}) as client:
            response = await client.get("http://127.0.0.1:16883/health", timeout=5.0)
            print(f"Health check status: {response.status_code}")
            if response.status_code == 200:
                print(f"Response: {response.json()}")
                print("✅ Health check successful!")
            else:
                print(f"❌ Health check failed: {response.status_code}")
                
        # Test callback endpoint
        print("\nTesting /callback/kling endpoint...")
        test_payload = {
            "job_id": "test_job_123",
            "status": "completed",
            "video_url": "https://example.com/video.mp4",
            "workflow_id": "test_workflow_456"
        }
        
        async with httpx.AsyncClient(proxies={}) as client:
            response = await client.post(
                "http://127.0.0.1:16883/callback/kling",
                json=test_payload,
                timeout=5.0
            )
            print(f"Callback status: {response.status_code}")
            if response.status_code == 200:
                print(f"Response: {response.json()}")
                print("✅ Callback test successful!")
            else:
                print(f"❌ Callback test failed: {response.status_code}")
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
    
    finally:
        # Stop server
        print("\nStopping server...")
        try:
            # Kill the entire process group
            os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
            server_process.wait(timeout=5)
        except:
            # Force kill if needed
            try:
                os.killpg(os.getpgid(server_process.pid), signal.SIGKILL)
            except:
                pass
        print("Server stopped.")


if __name__ == "__main__":
    asyncio.run(test_server())