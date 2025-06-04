#!/usr/bin/env python3
"""
测试GenVideoWorkflow工作流的基本功能
"""

import asyncio
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('.')

from workflows import GenVideoWorkflow
from models.core_models import JobInput, Step


async def test_gen_video_workflow():
    """测试GenVideoWorkflow的基本功能"""
    print("=== GenVideoWorkflow 基本功能测试 ===")
    
    try:
        # 创建工作流实例
        workflow = GenVideoWorkflow()
        print("✅ GenVideoWorkflow实例创建成功")
        
        # 创建测试输入
        job_input = JobInput(
            prompt="一只可爱的小猫在花园里玩耍",
            style="realistic",
            job_type=Step.VIDEO,
            width=512,
            height=512,
            duration=5.0,
            user_id="test_user_123",
            metadata={"test": True, "created_at": datetime.now().isoformat()}
        )
        print("✅ JobInput测试数据创建成功")
        print(f"   - 提示词: {job_input.prompt}")
        print(f"   - 任务类型: {job_input.job_type}")
        print(f"   - 尺寸: {job_input.width}x{job_input.height}")
        print(f"   - 时长: {job_input.duration}秒")
        
        # 验证工作流类结构
        print("\n=== 工作流结构验证 ===")
        
        # 检查必要的方法
        required_methods = ['run', '_poll_for_completion', 'cancel_generation', 'get_status', 'update_progress']
        for method_name in required_methods:
            if hasattr(workflow, method_name):
                print(f"✅ 方法 {method_name} 存在")
            else:
                print(f"❌ 方法 {method_name} 缺失")
        
        # 检查初始状态
        print("\n=== 初始状态检查 ===")
        print(f"✅ 工作流ID: {workflow.workflow_id}")
        print(f"✅ 当前进度: {workflow.current_progress.step} - {workflow.current_progress.status}")
        print(f"✅ 进度百分比: {workflow.current_progress.percent}%")
        print(f"✅ 开始时间: {workflow.started_at}")
        
        # 验证JobInput转换
        print("\n=== JobInput转换测试 ===")
        payload = job_input.to_temporal_payload()
        print(f"✅ Temporal payload转换成功: {len(payload)} 字段")
        
        json_str = job_input.to_json()
        print(f"✅ JSON转换成功: {len(json_str)} 字符")
        
        print("\n=== 测试完成 ===")
        print("✅ GenVideoWorkflow基本功能验证通过")
        print("\n注意: 这只是结构测试，实际工作流执行需要Temporal服务器运行")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_gen_video_workflow())
    sys.exit(0 if success else 1)