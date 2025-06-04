#!/usr/bin/env python3
"""
演示自定义搜索属性 CustomProgress 和 CustomTag 的使用
"""

import asyncio
import time
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from workflows import ImageGenerationWorkflow
from models.image_request import ImageRequest


async def demo_custom_attributes():
    """演示自定义搜索属性的使用"""
    print("🚀 开始演示自定义搜索属性...")
    
    # 连接到 Temporal 服务
    client = await Client.connect(
        'localhost:7233',
        data_converter=pydantic_data_converter
    )
    
    # 创建一个测试工作流
    workflow_id = f'demo-custom-attrs-{int(time.time())}'
    
    print(f"📝 启动工作流: {workflow_id}")
    
    try:
        # 创建请求对象
        request = ImageRequest(
            request_id=workflow_id,
            prompt="A beautiful sunset over mountains",
            width=512,
            height=512
        )
        
        # 启动工作流
        handle = await client.start_workflow(
            ImageGenerationWorkflow.run,
            request,
            id=workflow_id,
            task_queue='image-generation'
        )
        
        print(f"✅ 工作流已启动，ID: {workflow_id}")
        print(f"🔗 在 Temporal UI 中查看: http://localhost:8080/namespaces/default/workflows/{workflow_id}")
        
        # 等待一段时间让工作流开始执行
        await asyncio.sleep(2)
        
        # 查询工作流状态
        workflow_info = await handle.describe()
        print(f"📊 工作流状态: {workflow_info.status}")
        
        # 演示搜索查询
        print("\n🔍 演示搜索查询:")
        print("1. 搜索所有包含进度信息的工作流:")
        print("   CustomProgress != ''")
        print("\n2. 搜索特定进度状态的工作流:")
        print("   CustomProgress LIKE 'PROCESSING:%'")
        print("\n3. 搜索带有特定标签的工作流:")
        print("   CustomTag = 'image-generation'")
        print("\n4. 组合查询:")
        print("   CustomProgress LIKE '%:50%' AND CustomTag = 'processing'")
        
        print("\n💡 提示: 在 Temporal UI 的 Workflows 页面使用这些查询来过滤工作流")
        
        return workflow_id
        
    except Exception as e:
        print(f"❌ 演示过程中出现错误: {e}")
        return None


if __name__ == "__main__":
    asyncio.run(demo_custom_attributes())