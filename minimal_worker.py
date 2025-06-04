#!/usr/bin/env python3

import asyncio
import logging
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker
from typing import Dict, Any

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 简单的活动定义
@activity.defn
async def simple_activity(data: str) -> str:
    """简单的测试活动"""
    activity.logger.info(f"Processing: {data}")
    return f"Processed: {data}"

# 简单的工作流定义
@workflow.defn
class SimpleWorkflow:
    """简单的测试工作流"""
    
    @workflow.run
    async def run(self, input_data: str) -> str:
        """运行简单工作流"""
        workflow.logger.info(f"Starting simple workflow with: {input_data}")
        
        result = await workflow.execute_activity(
            simple_activity,
            input_data,
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return result

async def main():
    """启动worker"""
    try:
        # 连接到Temporal服务器
        client = await Client.connect("localhost:7233")
        logger.info("Connected to Temporal server")
        
        # 创建worker
        worker = Worker(
            client,
            task_queue='simple-queue',
            workflows=[SimpleWorkflow],
            activities=[simple_activity]
        )
        
        logger.info("Starting worker...")
        await worker.run()
        
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        raise

if __name__ == "__main__":
    from datetime import timedelta
    asyncio.run(main())