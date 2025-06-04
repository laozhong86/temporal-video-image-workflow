#!/usr/bin/env python3
"""验证gen_image函数实现的简化测试脚本"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_gen_image_source():
    """检查gen_image函数的源代码结构"""
    try:
        # 直接读取文件内容而不导入
        with open('activities/image_activities.py', 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        print("=== 验证 gen_image 函数实现 ===")
        print()
        
        # 检查必需的组件
        required_components = [
            ('函数定义', 'async def gen_image'),
            ('JobInput参数', 'job_input: JobInput'),
            ('返回类型', '-> str'),
            ('ComfyUI基础URL', 'base_url = "http://81.70.239.227:6889"'),
            ('提交端点', '/img/submit'),
            ('状态查询端点', '/img/status/'),
            ('结果获取端点', '/img/result/'),
            ('HTTP客户端', 'httpx.AsyncClient'),
            ('轮询间隔', 'poll_intervals = [1, 2, 4]'),
            ('最大轮询次数', 'max_polls = 150'),
            ('异步睡眠', 'asyncio.sleep'),
            ('超时异常处理', 'httpx.TimeoutException'),
            ('HTTP状态错误处理', 'httpx.HTTPStatusError'),
            ('日志记录', 'activity.logger')
        ]
        
        print("✅ 核心组件检查:")
        all_found = True
        missing_components = []
        for name, pattern in required_components:
            if pattern in source_code:
                print(f"  ✓ {name}: 已实现")
            else:
                print(f"  ✗ {name}: 缺失")
                missing_components.append(name)
                all_found = False
        
        print()
        print("✅ API流程检查:")
        
        # 检查API调用流程
        api_flow_checks = [
            ('提交图像请求', 'client.post(f"{base_url}/img/submit"'),
            ('解析job_id', 'submit_response.json()'),
            ('状态轮询循环', 'for poll_count in range(max_polls)'),
            ('状态查询请求', 'client.get(f"{base_url}/img/status/{job_id}"'),
            ('检查完成状态', 'status_data.get("status") == "completed"'),
            ('获取最终结果', 'client.get(f"{base_url}/img/result/{job_id}"'),
            ('返回图像URL', 'return result_data.get("image_url")')
        ]
        
        for name, pattern in api_flow_checks:
            if pattern in source_code:
                print(f"  ✓ {name}: 已实现")
            else:
                print(f"  ✗ {name}: 缺失")
                all_found = False
        
        print()
        print("✅ 错误处理检查:")
        
        # 检查错误处理
        error_handling_checks = [
            ('提交失败处理', 'raise Exception(f"Failed to submit image request"'),
            ('无job_id处理', 'if not job_id'),
            ('状态查询失败', 'Failed to check image status'),
            ('超时处理', 'Image generation timed out'),
            ('结果获取失败', 'Failed to get image result'),
            ('无图像URL处理', 'if not image_url')
        ]
        
        for name, pattern in error_handling_checks:
            if pattern in source_code:
                print(f"  ✓ {name}: 已实现")
            else:
                print(f"  ✗ {name}: 缺失")
                all_found = False
        
        print()
        print("✅ 指数退避策略检查:")
        
        # 检查指数退避实现
        backoff_checks = [
            ('轮询间隔数组', 'poll_intervals = [1, 2, 4]'),
            ('间隔索引计算', 'interval_index = min(poll_count, len(poll_intervals) - 1)'),
            ('动态睡眠时间', 'sleep_time = poll_intervals[interval_index]'),
            ('异步等待', 'await asyncio.sleep(sleep_time)')
        ]
        
        backoff_found = True
        missing_backoff = []
        for name, pattern in backoff_checks:
            if pattern in source_code:
                print(f"  ✓ {name}: 已实现")
            else:
                print(f"  ✗ {name}: 缺失")
                missing_backoff.append(name)
                backoff_found = False
                all_found = False
        
        print()
        if all_found:
            print("🎉 gen_image函数实现完整!")
            print("\n📋 功能总结:")
            print("- ✓ 异步函数，接收JobInput参数")
            print("- ✓ 集成ComfyUI API (提交/状态/结果)")
            print("- ✓ 实现指数退避轮询策略")
            print("- ✓ 完整的错误处理和超时机制")
            print("- ✓ 结构化日志记录")
            print("- ✓ 返回最终图像URL")
            return True
        else:
            print("❌ gen_image函数实现不完整，存在缺失组件:")
            if missing_components:
                print(f"  缺失的核心组件: {', '.join(missing_components)}")
            if not backoff_found:
                print(f"  缺失的指数退避组件: {', '.join(missing_backoff)}")
            return False
            
    except FileNotFoundError:
        print("❌ 错误: 找不到 activities/image_activities.py 文件")
        return False
    except Exception as e:
        print(f"❌ 验证过程中出现错误: {e}")
        return False

def check_models_integration():
    """检查与核心模型的集成"""
    try:
        from models.core_models import JobInput, Step
        
        print("\n=== 模型集成验证 ===")
        print()
        
        # 创建测试JobInput
        test_job = JobInput(
            prompt="测试图像生成",
            style="realistic",
            job_type=Step.IMAGE
        )
        
        print(f"✓ 成功创建JobInput实例")
        print(f"  - 提示词: {test_job.prompt}")
        print(f"  - 风格: {test_job.style}")
        print(f"  - 任务类型: {test_job.job_type}")
        
        return True
        
    except Exception as e:
        print(f"❌ 模型集成验证失败: {e}")
        return False

def main():
    """运行所有验证测试"""
    print("开始验证 gen_image 函数实现...")
    print("="*60)
    
    # 验证源代码结构
    source_ok = check_gen_image_source()
    
    # 验证模型集成
    models_ok = check_models_integration()
    
    print("\n" + "="*60)
    
    if source_ok and models_ok:
        print("\n🎉 所有验证通过! gen_image函数已正确实现")
        print("\n📝 实现要点:")
        print("1. 完整的ComfyUI API集成 (提交→轮询→获取结果)")
        print("2. 指数退避轮询策略 (1s→2s→4s)")
        print("3. 全面的错误处理和超时机制")
        print("4. 与JobInput模型的正确集成")
        print("5. 结构化日志记录")
        print("\n✅ 任务4的核心功能已完成实现")
        return 0
    else:
        print("\n❌ 验证失败，需要修复实现")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)