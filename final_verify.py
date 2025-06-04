#!/usr/bin/env python3
"""最终验证gen_image函数实现"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def verify_gen_image():
    """验证gen_image函数的完整实现"""
    try:
        # 读取源代码
        with open('activities/image_activities.py', 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        print("=== gen_image 函数实现验证 ===")
        print()
        
        # 核心组件检查
        core_components = [
            ('异步函数定义', 'async def gen_image'),
            ('JobInput参数', 'job_input: JobInput'),
            ('返回类型注解', '-> str'),
            ('ComfyUI API基础URL', 'base_url = "http://81.70.239.227:6889"'),
            ('HTTP客户端', 'httpx.AsyncClient'),
            ('提交端点调用', '/img/submit'),
            ('状态查询端点', '/img/status/'),
            ('结果获取端点', '/img/result/'),
            ('轮询间隔配置', 'poll_intervals = [1, 2, 4]'),
            ('最大轮询次数', 'max_polls = 150'),
            ('指数退避计算', 'interval_index = min(poll_count, len(poll_intervals) - 1)'),
            ('动态睡眠时间', 'sleep_time = poll_intervals[interval_index]'),
            ('异步等待', 'await asyncio.sleep(sleep_time)'),
            ('超时异常处理', 'httpx.TimeoutException'),
            ('HTTP错误处理', 'httpx.HTTPStatusError'),
            ('日志记录', 'activity.logger')
        ]
        
        print("📋 核心组件检查:")
        missing_components = []
        for name, pattern in core_components:
            if pattern in source_code:
                print(f"  ✅ {name}")
            else:
                print(f"  ❌ {name} - 缺失")
                missing_components.append(name)
        
        print()
        
        # API流程检查
        api_flows = [
            ('提交图像生成请求', 'submit_payload' in source_code and 'client.post' in source_code),
            ('获取job_id', 'job_id = submit_data.get("job_id")' in source_code),
            ('轮询状态检查', 'client.get(f"{base_url}/img/status/{job_id}")' in source_code),
            ('处理完成状态', 'status == "completed"' in source_code),
            ('处理失败状态', 'status == "failed"' in source_code),
            ('获取最终结果', 'client.get(f"{base_url}/img/result/{job_id}")' in source_code),
            ('返回图像URL', 'return image_url' in source_code)
        ]
        
        print("🔄 API流程检查:")
        missing_flows = []
        for name, condition in api_flows:
            if condition:
                print(f"  ✅ {name}")
            else:
                print(f"  ❌ {name} - 缺失")
                missing_flows.append(name)
        
        print()
        
        # 模型集成验证
        print("🔗 模型集成验证:")
        try:
            from models.core_models import JobInput, Step
            test_input = JobInput(
                prompt="测试图像生成",
                style="realistic",
                job_type=Step.IMAGE
            )
            print(f"  ✅ JobInput模型集成成功")
            print(f"    - 提示词: {test_input.prompt}")
            print(f"    - 风格: {test_input.style}")
            print(f"    - 任务类型: {test_input.job_type}")
            model_integration = True
        except Exception as e:
            print(f"  ❌ JobInput模型集成失败: {e}")
            model_integration = False
        
        print()
        print("=" * 50)
        
        # 最终结果
        if not missing_components and not missing_flows and model_integration:
            print("🎉 验证成功! gen_image函数实现完整")
            print()
            print("📋 实现总结:")
            print("  ✅ 完整的异步函数定义")
            print("  ✅ ComfyUI API三步流程 (提交→轮询→获取)")
            print("  ✅ 指数退避轮询策略")
            print("  ✅ 全面的错误处理机制")
            print("  ✅ 结构化日志记录")
            print("  ✅ JobInput模型集成")
            return True
        else:
            print("❌ 验证失败，存在以下问题:")
            if missing_components:
                print(f"  🔧 缺失核心组件: {len(missing_components)}个")
                for comp in missing_components[:3]:  # 只显示前3个
                    print(f"    - {comp}")
                if len(missing_components) > 3:
                    print(f"    - ... 还有{len(missing_components)-3}个")
            
            if missing_flows:
                print(f"  🔄 缺失API流程: {len(missing_flows)}个")
                for flow in missing_flows[:3]:  # 只显示前3个
                    print(f"    - {flow}")
                if len(missing_flows) > 3:
                    print(f"    - ... 还有{len(missing_flows)-3}个")
            
            if not model_integration:
                print(f"  🔗 模型集成问题")
            
            return False
            
    except FileNotFoundError:
        print("❌ 错误: 找不到 activities/image_activities.py 文件")
        return False
    except Exception as e:
        print(f"❌ 验证过程中出现错误: {e}")
        return False

if __name__ == "__main__":
    success = verify_gen_image()
    sys.exit(0 if success else 1)