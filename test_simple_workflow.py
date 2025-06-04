#!/usr/bin/env python3

import asyncio
from temporalio.client import Client
from minimal_worker import SimpleWorkflow

async def test_workflow():
    """测试简单工作流"""
    try:
        # 连接到Temporal服务器
        client = await Client.connect("localhost:7233")
        print("Connected to Temporal server")
        
        # 执行工作流
        result = await client.execute_workflow(
            SimpleWorkflow.run,
            "test data",
            id="test-workflow-1",
            task_queue="simple-queue"
        )
        
        print(f"Workflow result: {result}")
        
    except Exception as e:
        print(f"Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_workflow())