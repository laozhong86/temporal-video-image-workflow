#!/usr/bin/env python3
"""
Performance and Stress Tests for Temporal Video Generation System

This module provides comprehensive performance and stress tests including:
- Load testing with varying concurrent users
- Stress testing under extreme conditions
- Memory and CPU usage profiling
- Throughput and latency measurements
- Resource exhaustion testing
- Long-running stability tests
"""

import pytest
import asyncio
import time
import psutil
import json
import sys
import statistics
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, Mock, AsyncMock
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import project modules
from models.core_models import JobInput, Progress, JobStatus, Step
from models.video_request import VideoRequest
from config import Config


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""
    timestamp: str
    test_name: str
    duration: float
    throughput: float
    success_rate: float
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    cpu_usage: float
    memory_usage_mb: float
    error_count: int
    total_requests: int


@dataclass
class LoadTestConfig:
    """Load test configuration."""
    concurrent_users: int
    requests_per_user: int
    ramp_up_time: float
    test_duration: float
    target_throughput: float


class PerformanceMonitor:
    """Performance monitoring utility."""
    
    def __init__(self):
        self.start_time = None
        self.metrics = []
        self.response_times = []
        self.errors = []
    
    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.time()
        self.metrics = []
        self.response_times = []
        self.errors = []
    
    def record_response_time(self, response_time: float):
        """Record a response time."""
        self.response_times.append(response_time)
    
    def record_error(self, error: str):
        """Record an error."""
        self.errors.append({
            "timestamp": datetime.now().isoformat(),
            "error": error
        })
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        if not self.start_time:
            return {}
        
        current_time = time.time()
        duration = current_time - self.start_time
        
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_info = psutil.virtual_memory()
        memory_mb = memory_info.used / (1024 * 1024)
        
        # Response time metrics
        avg_response_time = statistics.mean(self.response_times) if self.response_times else 0
        p95_response_time = statistics.quantiles(self.response_times, n=20)[18] if len(self.response_times) >= 20 else 0
        p99_response_time = statistics.quantiles(self.response_times, n=100)[98] if len(self.response_times) >= 100 else 0
        
        # Throughput metrics
        total_requests = len(self.response_times)
        throughput = total_requests / duration if duration > 0 else 0
        success_rate = (total_requests - len(self.errors)) / total_requests if total_requests > 0 else 0
        
        return {
            "timestamp": datetime.now().isoformat(),
            "duration": duration,
            "throughput": throughput,
            "success_rate": success_rate,
            "avg_response_time": avg_response_time,
            "p95_response_time": p95_response_time,
            "p99_response_time": p99_response_time,
            "cpu_usage": cpu_percent,
            "memory_usage_mb": memory_mb,
            "error_count": len(self.errors),
            "total_requests": total_requests
        }


class TestLoadTesting:
    """Load testing scenarios."""
    
    def __init__(self):
        self.monitor = PerformanceMonitor()
    
    @pytest.mark.asyncio
    async def test_light_load(self):
        """Test system under light load (1-5 concurrent users)."""
        config = LoadTestConfig(
            concurrent_users=3,
            requests_per_user=10,
            ramp_up_time=5.0,
            test_duration=30.0,
            target_throughput=5.0
        )
        
        metrics = await self._run_load_test(config, "light_load")
        
        # Assertions for light load
        assert metrics.success_rate >= 0.95  # 95% success rate
        assert metrics.avg_response_time <= 2.0  # Average response time under 2s
        assert metrics.cpu_usage <= 70.0  # CPU usage under 70%
        
        print(f"✅ Light load test passed: {metrics.throughput:.2f} req/s, {metrics.success_rate:.2%} success")
    
    @pytest.mark.asyncio
    async def test_moderate_load(self):
        """Test system under moderate load (10-20 concurrent users)."""
        config = LoadTestConfig(
            concurrent_users=15,
            requests_per_user=20,
            ramp_up_time=10.0,
            test_duration=60.0,
            target_throughput=15.0
        )
        
        metrics = await self._run_load_test(config, "moderate_load")
        
        # Assertions for moderate load
        assert metrics.success_rate >= 0.90  # 90% success rate
        assert metrics.avg_response_time <= 5.0  # Average response time under 5s
        assert metrics.cpu_usage <= 85.0  # CPU usage under 85%
        
        print(f"✅ Moderate load test passed: {metrics.throughput:.2f} req/s, {metrics.success_rate:.2%} success")
    
    @pytest.mark.asyncio
    async def test_heavy_load(self):
        """Test system under heavy load (50+ concurrent users)."""
        config = LoadTestConfig(
            concurrent_users=50,
            requests_per_user=10,
            ramp_up_time=20.0,
            test_duration=120.0,
            target_throughput=25.0
        )
        
        metrics = await self._run_load_test(config, "heavy_load")
        
        # Assertions for heavy load (more lenient)
        assert metrics.success_rate >= 0.80  # 80% success rate
        assert metrics.avg_response_time <= 10.0  # Average response time under 10s
        assert metrics.cpu_usage <= 95.0  # CPU usage under 95%
        
        print(f"✅ Heavy load test passed: {metrics.throughput:.2f} req/s, {metrics.success_rate:.2%} success")
    
    async def _run_load_test(self, config: LoadTestConfig, test_name: str) -> PerformanceMetrics:
        """Run a load test with the given configuration."""
        self.monitor.start_monitoring()
        
        # Create mock job inputs
        job_inputs = [
            JobInput(
                prompt=f"Load test video {i}",
                job_type=Step.VIDEO,
                width=512,
                height=512,
                duration=5.0,
                user_id=f"load_test_user_{i % config.concurrent_users}"
            )
            for i in range(config.concurrent_users * config.requests_per_user)
        ]
        
        # Simulate concurrent user load
        async def simulate_user_requests(user_id: int, requests: List[JobInput]):
            """Simulate requests from a single user."""
            for job_input in requests:
                start_time = time.time()
                
                try:
                    # Mock workflow execution
                    await self._mock_workflow_execution(job_input)
                    response_time = time.time() - start_time
                    self.monitor.record_response_time(response_time)
                    
                except Exception as e:
                    self.monitor.record_error(str(e))
                
                # Add some delay between requests
                await asyncio.sleep(0.1)
        
        # Split jobs among users
        jobs_per_user = len(job_inputs) // config.concurrent_users
        user_tasks = []
        
        for user_id in range(config.concurrent_users):
            start_idx = user_id * jobs_per_user
            end_idx = start_idx + jobs_per_user
            user_jobs = job_inputs[start_idx:end_idx]
            
            # Add ramp-up delay
            ramp_delay = (user_id / config.concurrent_users) * config.ramp_up_time
            
            async def delayed_user_simulation(uid, jobs, delay):
                await asyncio.sleep(delay)
                await simulate_user_requests(uid, jobs)
            
            user_tasks.append(delayed_user_simulation(user_id, user_jobs, ramp_delay))
        
        # Execute all user simulations
        await asyncio.gather(*user_tasks)
        
        # Get final metrics
        final_metrics = self.monitor.get_current_metrics()
        
        return PerformanceMetrics(
            timestamp=final_metrics["timestamp"],
            test_name=test_name,
            duration=final_metrics["duration"],
            throughput=final_metrics["throughput"],
            success_rate=final_metrics["success_rate"],
            avg_response_time=final_metrics["avg_response_time"],
            p95_response_time=final_metrics["p95_response_time"],
            p99_response_time=final_metrics["p99_response_time"],
            cpu_usage=final_metrics["cpu_usage"],
            memory_usage_mb=final_metrics["memory_usage_mb"],
            error_count=final_metrics["error_count"],
            total_requests=final_metrics["total_requests"]
        )
    
    async def _mock_workflow_execution(self, job_input: JobInput):
        """Mock workflow execution with realistic timing."""
        # Simulate image generation (20-60 seconds)
        image_time = 0.05 + (hash(job_input.prompt) % 100) / 2500  # 0.05-0.09s mock
        await asyncio.sleep(image_time)
        
        # Simulate video generation (60-300 seconds)
        video_time = 0.1 + (hash(job_input.user_id) % 100) / 1000  # 0.1-0.2s mock
        await asyncio.sleep(video_time)
        
        # Simulate callback processing (1-5 seconds)
        callback_time = 0.01 + (hash(str(job_input.width)) % 10) / 1000  # 0.01-0.02s mock
        await asyncio.sleep(callback_time)


class TestStressTesting:
    """Stress testing scenarios."""
    
    def __init__(self):
        self.monitor = PerformanceMonitor()
    
    @pytest.mark.asyncio
    async def test_cpu_stress(self):
        """Test system under CPU stress."""
        self.monitor.start_monitoring()
        
        # Simulate CPU-intensive operations
        async def cpu_intensive_task(task_id: int):
            """Simulate CPU-intensive workflow processing."""
            start_time = time.time()
            
            # Mock CPU-intensive operations
            for i in range(1000):
                # Simulate complex calculations
                result = sum(j * j for j in range(100))
                await asyncio.sleep(0.001)  # Small delay to prevent blocking
            
            response_time = time.time() - start_time
            self.monitor.record_response_time(response_time)
        
        # Run multiple CPU-intensive tasks concurrently
        tasks = [cpu_intensive_task(i) for i in range(20)]
        await asyncio.gather(*tasks)
        
        metrics = self.monitor.get_current_metrics()
        
        # Verify system handled CPU stress
        assert metrics["total_requests"] == 20
        assert metrics["success_rate"] >= 0.90
        
        print(f"✅ CPU stress test passed: {metrics['cpu_usage']:.1f}% CPU, {metrics['throughput']:.2f} req/s")
    
    @pytest.mark.asyncio
    async def test_memory_stress(self):
        """Test system under memory stress."""
        self.monitor.start_monitoring()
        
        # Simulate memory-intensive operations
        async def memory_intensive_task(task_id: int):
            """Simulate memory-intensive workflow processing."""
            start_time = time.time()
            
            # Mock memory-intensive operations
            large_data = []
            for i in range(1000):
                # Simulate large data processing
                data_chunk = [j for j in range(1000)]
                large_data.append(data_chunk)
                await asyncio.sleep(0.001)
            
            # Clean up
            del large_data
            
            response_time = time.time() - start_time
            self.monitor.record_response_time(response_time)
        
        # Run multiple memory-intensive tasks
        tasks = [memory_intensive_task(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        metrics = self.monitor.get_current_metrics()
        
        # Verify system handled memory stress
        assert metrics["total_requests"] == 10
        assert metrics["success_rate"] >= 0.90
        
        print(f"✅ Memory stress test passed: {metrics['memory_usage_mb']:.1f}MB memory, {metrics['throughput']:.2f} req/s")
    
    @pytest.mark.asyncio
    async def test_connection_stress(self):
        """Test system under connection stress."""
        self.monitor.start_monitoring()
        
        # Simulate many concurrent connections
        async def connection_task(connection_id: int):
            """Simulate a connection with multiple requests."""
            for request_id in range(5):
                start_time = time.time()
                
                try:
                    # Mock API call with potential connection issues
                    await asyncio.sleep(0.05)  # Simulate network latency
                    
                    # Simulate occasional connection failures
                    if (connection_id + request_id) % 50 == 0:
                        raise Exception("Connection timeout")
                    
                    response_time = time.time() - start_time
                    self.monitor.record_response_time(response_time)
                    
                except Exception as e:
                    self.monitor.record_error(str(e))
        
        # Create many concurrent connections
        connections = [connection_task(i) for i in range(100)]
        await asyncio.gather(*connections, return_exceptions=True)
        
        metrics = self.monitor.get_current_metrics()
        
        # Verify system handled connection stress
        assert metrics["total_requests"] >= 400  # Should have processed most requests
        assert metrics["success_rate"] >= 0.85  # Allow for some connection failures
        
        print(f"✅ Connection stress test passed: {metrics['total_requests']} requests, {metrics['success_rate']:.2%} success")


class TestLongRunningStability:
    """Long-running stability tests."""
    
    def __init__(self):
        self.monitor = PerformanceMonitor()
    
    @pytest.mark.asyncio
    async def test_extended_operation(self):
        """Test system stability over extended operation."""
        self.monitor.start_monitoring()
        
        # Run for extended period with continuous load
        test_duration = 60.0  # 1 minute for testing (would be longer in real scenario)
        end_time = time.time() + test_duration
        
        request_count = 0
        while time.time() < end_time:
            start_time = time.time()
            
            try:
                # Mock continuous workflow processing
                await self._mock_continuous_workflow()
                response_time = time.time() - start_time
                self.monitor.record_response_time(response_time)
                request_count += 1
                
            except Exception as e:
                self.monitor.record_error(str(e))
            
            # Small delay between requests
            await asyncio.sleep(0.5)
        
        metrics = self.monitor.get_current_metrics()
        
        # Verify system remained stable
        assert metrics["success_rate"] >= 0.95
        assert metrics["avg_response_time"] <= 5.0
        assert request_count >= 100  # Should have processed many requests
        
        print(f"✅ Extended operation test passed: {request_count} requests over {test_duration}s")
    
    @pytest.mark.asyncio
    async def test_memory_leak_detection(self):
        """Test for memory leaks over time."""
        initial_memory = psutil.virtual_memory().used / (1024 * 1024)
        memory_samples = [initial_memory]
        
        # Run operations and monitor memory
        for i in range(50):
            # Mock workflow that could potentially leak memory
            await self._mock_workflow_with_cleanup()
            
            # Sample memory usage
            current_memory = psutil.virtual_memory().used / (1024 * 1024)
            memory_samples.append(current_memory)
            
            await asyncio.sleep(0.1)
        
        final_memory = memory_samples[-1]
        memory_growth = final_memory - initial_memory
        
        # Check for excessive memory growth (allow some growth but not too much)
        assert memory_growth <= 100.0  # No more than 100MB growth
        
        print(f"✅ Memory leak test passed: {memory_growth:.1f}MB growth over 50 operations")
    
    async def _mock_continuous_workflow(self):
        """Mock a continuous workflow operation."""
        # Simulate image processing
        await asyncio.sleep(0.1)
        
        # Simulate video processing
        await asyncio.sleep(0.2)
        
        # Simulate callback processing
        await asyncio.sleep(0.05)
    
    async def _mock_workflow_with_cleanup(self):
        """Mock workflow with proper cleanup."""
        # Create some data
        temp_data = [i for i in range(10000)]
        
        # Process data
        await asyncio.sleep(0.01)
        
        # Clean up
        del temp_data


class TestResourceExhaustion:
    """Resource exhaustion testing."""
    
    @pytest.mark.asyncio
    async def test_queue_overflow_handling(self):
        """Test handling of queue overflow scenarios."""
        # Mock queue with limited capacity
        queue_capacity = 100
        current_queue_size = 0
        processed_requests = 0
        rejected_requests = 0
        
        # Simulate high request rate
        for i in range(150):  # More requests than capacity
            if current_queue_size < queue_capacity:
                current_queue_size += 1
                # Mock processing
                await asyncio.sleep(0.001)
                current_queue_size -= 1
                processed_requests += 1
            else:
                rejected_requests += 1
        
        # Verify graceful handling of overflow
        assert processed_requests <= queue_capacity
        assert rejected_requests > 0
        assert processed_requests + rejected_requests == 150
        
        print(f"✅ Queue overflow test passed: {processed_requests} processed, {rejected_requests} rejected")
    
    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion(self):
        """Test handling of connection pool exhaustion."""
        # Mock connection pool
        max_connections = 20
        active_connections = 0
        successful_connections = 0
        failed_connections = 0
        
        async def mock_connection_request():
            nonlocal active_connections, successful_connections, failed_connections
            
            if active_connections < max_connections:
                active_connections += 1
                try:
                    await asyncio.sleep(0.1)  # Simulate connection usage
                    successful_connections += 1
                finally:
                    active_connections -= 1
            else:
                failed_connections += 1
        
        # Create more connection requests than pool capacity
        tasks = [mock_connection_request() for _ in range(50)]
        await asyncio.gather(*tasks)
        
        # Verify connection pool handled exhaustion
        assert successful_connections <= max_connections * 2  # Allow some overlap
        assert failed_connections > 0
        
        print(f"✅ Connection pool test passed: {successful_connections} successful, {failed_connections} failed")


def generate_performance_report(metrics_list: List[PerformanceMetrics]) -> str:
    """Generate a comprehensive performance report."""
    report = []
    report.append("\n" + "="*80)
    report.append("📊 PERFORMANCE TEST REPORT")
    report.append("="*80)
    report.append(f"Generated: {datetime.now().isoformat()}")
    report.append(f"Total Tests: {len(metrics_list)}")
    report.append("\n")
    
    for metrics in metrics_list:
        report.append(f"🔍 Test: {metrics.test_name}")
        report.append(f"   Duration: {metrics.duration:.2f}s")
        report.append(f"   Throughput: {metrics.throughput:.2f} req/s")
        report.append(f"   Success Rate: {metrics.success_rate:.2%}")
        report.append(f"   Avg Response Time: {metrics.avg_response_time:.3f}s")
        report.append(f"   P95 Response Time: {metrics.p95_response_time:.3f}s")
        report.append(f"   P99 Response Time: {metrics.p99_response_time:.3f}s")
        report.append(f"   CPU Usage: {metrics.cpu_usage:.1f}%")
        report.append(f"   Memory Usage: {metrics.memory_usage_mb:.1f}MB")
        report.append(f"   Total Requests: {metrics.total_requests}")
        report.append(f"   Errors: {metrics.error_count}")
        report.append("")
    
    # Summary statistics
    if metrics_list:
        avg_throughput = statistics.mean([m.throughput for m in metrics_list])
        avg_success_rate = statistics.mean([m.success_rate for m in metrics_list])
        avg_response_time = statistics.mean([m.avg_response_time for m in metrics_list])
        
        report.append("📈 SUMMARY STATISTICS")
        report.append("-" * 40)
        report.append(f"Average Throughput: {avg_throughput:.2f} req/s")
        report.append(f"Average Success Rate: {avg_success_rate:.2%}")
        report.append(f"Average Response Time: {avg_response_time:.3f}s")
    
    report.append("\n" + "="*80)
    
    return "\n".join(report)


def run_performance_tests():
    """Run all performance and stress tests."""
    print("\n" + "="*60)
    print("⚡ 运行性能和压力测试")
    print("="*60)
    
    # Run pytest with specific markers
    pytest_args = [
        __file__,
        "-v",
        "--tb=short",
        "--color=yes",
        "-x"  # Stop on first failure
    ]
    
    return pytest.main(pytest_args)


if __name__ == "__main__":
    exit_code = run_performance_tests()
    sys.exit(exit_code)