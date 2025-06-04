#!/usr/bin/env python3
"""
简单的Worker启动脚本，只处理ImageGenerationWorkflow
"""

import asyncio
import logging
from temporalio.worker import Worker
from temporalio.client import Client
from workflows.image_workflow import ImageGenerationWorkflow
from activities.image_activities import (
    gen_image,
    submit_image_request,
    check_image_status,
    download_image_result,
    send_image_notification
)
from activities.common_activities import (
    validate_request,
    log_activity,
    handle_error,
    cleanup_resources
)
from models.image_request import ImageRequest, ImageResponse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """启动简单的worker"""
    try:
        # 连接到Temporal服务器
        client = await Client.connect('localhost:7233')
        logger.info("Connected to Temporal server")
        
        # 创建worker
        worker = Worker(
            client,
            task_queue='image-generation-queue',
            workflows=[ImageGenerationWorkflow],
            activities=[
                gen_image,
                submit_image_request,
                check_image_status,
                download_image_result,
                send_image_notification,
                validate_request,
                log_activity,
                handle_error,
                cleanup_resources
            ]
        )
        
        logger.info("Worker started for ImageGenerationWorkflow")
        logger.info("Listening on task queue: image-generation-queue")
        
        # 运行worker
        await worker.run()
        
    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())