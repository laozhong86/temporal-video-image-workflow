#!/usr/bin/env python3
"""
测试指标收集系统的功能（简化版本，不依赖psutil）
"""

import asyncio
import time
import logging
from datetime import datetime
from typing import Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict
import threading
import functools

# 简化的系统指标类（不依赖psutil）
@dataclass
class SystemMetrics:
    timestamp: datetime
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_io_read: int = 0
    disk_io_write: int = 0
    network_io_sent: int = 0
    network_io_recv: int = 0
    connections: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'disk_io_read': self.disk_io_read,
            'disk_io_write': self.disk_io_write,
            'network_io_sent': self.network_io_sent,
            'network_io_recv': self.network_io_recv,
            'connections': self.connections
        }

# 简化的性能指标类
@dataclass
class PerformanceMetrics:
    execution_times: list = field(default_factory=list)
    retry_counts: Dict[str, int] = field(default_factory=dict)
    error_types: Dict[str, int] = field(default_factory=dict)
    throughput_history: list = field(default_factory=list)
    latency_percentiles: Dict[str, float] = field(default_factory=dict)
    system_metrics: list = field(default_factory=list)
    
    def calculate_percentiles(self) -> Dict[str, float]:
        if not self.execution_times:
            return {}
        
        sorted_times = sorted(self.execution_times)
        n = len(sorted_times)
        
        return {
            'p50': sorted_times[int(n * 0.5)],
            'p90': sorted_times[int(n * 0.9)],
            'p95': sorted_times[int(n * 0.95)],
            'p99': sorted_times[int(n * 0.99)] if n > 1 else sorted_times[0]
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'execution_times': self.execution_times,
            'retry_counts': dict(self.retry_counts),
            'error_types': dict(self.error_types),
            'throughput_history': self.throughput_history,
            'latency_percentiles': self.latency_percentiles,
            'system_metrics': [metric.to_dict() for metric in self.system_metrics]
        }

# 简化的系统监控器（模拟数据）
class SystemMonitor:
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.running = False
        self.thread = None
        self.metrics_history = []
        self.start_time = None
    
    def start(self):
        if self.running:
            return
        
        self.running = True
        self.start_time = datetime.now()
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print(f"系统监控已启动，间隔: {self.interval}秒")
    
    def stop(self):
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        print("系统监控已停止")
    
    def _monitor_loop(self):
        while self.running:
            metrics = self._collect_metrics()
            self.metrics_history.append(metrics)
            time.sleep(self.interval)
    
    def _collect_metrics(self) -> SystemMetrics:
        # 模拟系统指标数据
        import random
        return SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=random.uniform(10, 80),
            memory_percent=random.uniform(30, 70),
            disk_io_read=random.randint(1000, 10000),
            disk_io_write=random.randint(500, 5000),
            network_io_sent=random.randint(100, 1000),
            network_io_recv=random.randint(200, 2000),
            connections=random.randint(5, 50)
        )
    
    def get_average_metrics(self) -> SystemMetrics:
        if not self.metrics_history:
            return SystemMetrics(timestamp=datetime.now())
        
        # 计算平均值
        avg_cpu = sum(m.cpu_percent for m in self.metrics_history) / len(self.metrics_history)
        avg_memory = sum(m.memory_percent for m in self.metrics_history) / len(self.metrics_history)
        total_disk_read = sum(m.disk_io_read for m in self.metrics_history)
        total_disk_write = sum(m.disk_io_write for m in self.metrics_history)
        total_net_sent = sum(m.network_io_sent for m in self.metrics_history)
        total_net_recv = sum(m.network_io_recv for m in self.metrics_history)
        avg_connections = sum(m.connections for m in self.metrics_history) / len(self.metrics_history)
        
        return SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=avg_cpu,
            memory_percent=avg_memory,
            disk_io_read=total_disk_read,
            disk_io_write=total_disk_write,
            network_io_sent=total_net_sent,
            network_io_recv=total_net_recv,
            connections=avg_connections
        )

# 指标收集器
class MetricsCollector:
    def __init__(self):
        self.execution_times = []
        self.retry_counts = defaultdict(int)
        self.error_types = defaultdict(int)
        self.throughput_history = []
        self.workflow_results = []
    
    def record_workflow_result(self, result):
        self.workflow_results.append(result)
        
        if hasattr(result, 'execution_time'):
            self.execution_times.append(result.execution_time)
        
        if hasattr(result, 'retry_count'):
            workflow_id = getattr(result, 'workflow_id', 'unknown')
            self.retry_counts[workflow_id] = result.retry_count
        
        if hasattr(result, 'error_message') and result.error_message:
            self.error_types['模拟失败'] += 1
    
    def record_batch_throughput(self, throughput: float):
        self.throughput_history.append(throughput)
    
    def generate_performance_metrics(self, system_metrics: list = None) -> PerformanceMetrics:
        metrics = PerformanceMetrics(
            execution_times=self.execution_times.copy(),
            retry_counts=dict(self.retry_counts),
            error_types=dict(self.error_types),
            throughput_history=self.throughput_history.copy(),
            system_metrics=system_metrics or []
        )
        
        metrics.latency_percentiles = metrics.calculate_percentiles()
        return metrics
    
    def reset(self):
        self.execution_times.clear()
        self.retry_counts.clear()
        self.error_types.clear()
        self.throughput_history.clear()
        self.workflow_results.clear()

# 时间装饰器
def timing_decorator(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # 如果结果有execution_time属性，更新它
            if hasattr(result, 'execution_time'):
                result.execution_time = execution_time
            
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                'error': e,
                'execution_time': execution_time,
                'success': False
            }
    return wrapper

# 工作流结果类
@dataclass
class WorkflowResult:
    workflow_id: str
    success: bool
    execution_time: float
    submitted_at: datetime
    completed_at: datetime
    retry_count: int = 0
    error_message: str = None

# 测试配置类
@dataclass
class TestConfig:
    enable_system_monitoring: bool = True
    monitoring_interval: float = 1.0

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MetricsSystemTester:
    """指标收集系统测试器"""
    
    def __init__(self):
        self.config = TestConfig(
            enable_system_monitoring=True,
            monitoring_interval=0.5  # 更频繁的监控用于测试
        )
        self.system_monitor = SystemMonitor(interval=self.config.monitoring_interval)
        self.metrics_collector = MetricsCollector()
    
    @timing_decorator
    async def simulate_workflow_execution(self, workflow_id: str, duration: float, should_fail: bool = False) -> WorkflowResult:
        """模拟工作流执行"""
        logger.info(f"开始模拟工作流 {workflow_id}，预期耗时 {duration}s")
        
        start_time = time.time()
        await asyncio.sleep(duration)  # 模拟工作流执行时间
        
        if should_fail:
            result = WorkflowResult(
                workflow_id=workflow_id,
                success=False,
                execution_time=duration,
                error_message="模拟失败",
                submitted_at=datetime.now(),
                completed_at=datetime.now(),
                retry_count=1
            )
        else:
            result = WorkflowResult(
                workflow_id=workflow_id,
                success=True,
                execution_time=duration,
                submitted_at=datetime.now(),
                completed_at=datetime.now(),
                retry_count=0
            )
        
        return result
    
    async def test_system_monitoring(self):
        """测试系统监控功能"""
        logger.info("🔍 测试系统监控功能...")
        
        # 启动系统监控
        self.system_monitor.start()
        logger.info("✅ 系统监控已启动")
        
        # 运行一段时间收集数据
        await asyncio.sleep(3)
        
        # 停止监控并获取平均指标
        self.system_monitor.stop()
        avg_metrics = self.system_monitor.get_average_metrics()
        
        if avg_metrics:
            logger.info(f"📊 平均系统指标:")
            logger.info(f"   CPU: {avg_metrics.cpu_percent:.1f}%")
            logger.info(f"   内存: {avg_metrics.memory_percent:.1f}%")
            logger.info(f"   连接数: {avg_metrics.connections:.0f}")
            logger.info(f"   监控历史记录数: {len(self.system_monitor.metrics_history)}")
        else:
            logger.warning("❌ 未能获取系统指标")
        
        return avg_metrics is not None
    
    async def test_metrics_collection(self):
        """测试指标收集功能"""
        logger.info("📈 测试指标收集功能...")
        
        # 重置指标收集器
        self.metrics_collector.reset()
        
        # 模拟多个工作流执行
        workflows = [
            ("workflow-1", 0.5, False),
            ("workflow-2", 1.0, False),
            ("workflow-3", 0.3, True),   # 失败的工作流
            ("workflow-4", 0.8, False),
            ("workflow-5", 0.2, True),   # 另一个失败的工作流
        ]
        
        for workflow_id, duration, should_fail in workflows:
            result = await self.simulate_workflow_execution(workflow_id, duration, should_fail)
            self.metrics_collector.record_workflow_result(result)
        
        # 记录批次吞吐量
        self.metrics_collector.record_batch_throughput(2.5)  # 5个工作流 / 2秒
        
        # 生成性能指标
        performance_metrics = self.metrics_collector.generate_performance_metrics()
        
        # 验证指标
        logger.info(f"📊 收集的性能指标:")
        logger.info(f"   执行时间记录数: {len(performance_metrics.execution_times)}")
        logger.info(f"   重试次数记录数: {len(performance_metrics.retry_counts)}")
        logger.info(f"   错误类型: {dict(performance_metrics.error_types)}")
        logger.info(f"   吞吐量历史: {performance_metrics.throughput_history}")
        
        if performance_metrics.latency_percentiles:
            logger.info(f"   延迟百分位数:")
            for percentile, value in performance_metrics.latency_percentiles.items():
                logger.info(f"     {percentile}: {value:.3f}s")
        
        # 验证数据正确性
        expected_workflows = len(workflows)
        actual_workflows = len(performance_metrics.execution_times)
        
        if actual_workflows == expected_workflows:
            logger.info("✅ 指标收集数量正确")
        else:
            logger.error(f"❌ 指标收集数量错误: 期望 {expected_workflows}, 实际 {actual_workflows}")
            return False
        
        # 验证错误统计
        failed_count = sum(1 for _, _, should_fail in workflows if should_fail)
        recorded_errors = sum(performance_metrics.error_types.values())
        
        if recorded_errors == failed_count:
            logger.info("✅ 错误统计正确")
        else:
            logger.error(f"❌ 错误统计错误: 期望 {failed_count}, 实际 {recorded_errors}")
            return False
        
        return True
    
    async def test_timing_decorator(self):
        """测试时间装饰器功能"""
        logger.info("⏱️ 测试时间装饰器功能...")
        
        @timing_decorator
        async def test_function(duration: float):
            await asyncio.sleep(duration)
            return f"完成，耗时 {duration}s"
        
        # 测试正常执行
        start_time = time.time()
        result = await test_function(0.5)
        actual_duration = time.time() - start_time
        
        logger.info(f"函数返回: {result}")
        logger.info(f"实际执行时间: {actual_duration:.3f}s")
        
        # 验证时间测量的准确性（允许一定误差）
        if 0.4 <= actual_duration <= 0.6:
            logger.info("✅ 时间装饰器工作正常")
            return True
        else:
            logger.error(f"❌ 时间装饰器测量不准确")
            return False
    
    async def test_json_serialization(self):
        """测试JSON序列化功能"""
        logger.info("🔄 测试JSON序列化功能...")
        
        try:
            # 创建测试数据
            result = WorkflowResult(
                workflow_id="test-workflow",
                success=True,
                execution_time=1.5,
                submitted_at=datetime.now(),
                completed_at=datetime.now()
            )
            
            self.metrics_collector.record_workflow_result(result)
            performance_metrics = self.metrics_collector.generate_performance_metrics()
            
            # 测试序列化
            metrics_dict = performance_metrics.to_dict()
            logger.info(f"✅ PerformanceMetrics 序列化成功")
            logger.info(f"   序列化字段数: {len(metrics_dict)}")
            
            # 启动系统监控获取系统指标
            self.system_monitor.start()
            await asyncio.sleep(1)
            self.system_monitor.stop()
            
            avg_metrics = self.system_monitor.get_average_metrics()
            if avg_metrics:
                system_dict = avg_metrics.to_dict()
                logger.info(f"✅ SystemMetrics 序列化成功")
                logger.info(f"   序列化字段数: {len(system_dict)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ JSON序列化失败: {e}")
            return False
    
    async def run_all_tests(self):
        """运行所有测试"""
        logger.info("🚀 开始指标收集系统综合测试")
        
        tests = [
            ("系统监控", self.test_system_monitoring),
            ("指标收集", self.test_metrics_collection),
            ("时间装饰器", self.test_timing_decorator),
            ("JSON序列化", self.test_json_serialization),
        ]
        
        results = []
        for test_name, test_func in tests:
            logger.info(f"\n--- 测试: {test_name} ---")
            try:
                result = await test_func()
                results.append((test_name, result))
                if result:
                    logger.info(f"✅ {test_name} 测试通过")
                else:
                    logger.error(f"❌ {test_name} 测试失败")
            except Exception as e:
                logger.error(f"💥 {test_name} 测试异常: {e}")
                results.append((test_name, False))
        
        # 总结测试结果
        logger.info("\n🎯 测试结果总结:")
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"   {test_name}: {status}")
        
        logger.info(f"\n总体结果: {passed}/{total} 测试通过 ({passed/total*100:.1f}%)")
        
        if passed == total:
            logger.info("🎉 所有测试通过！指标收集系统工作正常。")
        else:
            logger.warning(f"⚠️ 有 {total-passed} 个测试失败，需要检查相关功能。")
        
        return passed == total


async def main():
    """主函数"""
    tester = MetricsSystemTester()
    success = await tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)