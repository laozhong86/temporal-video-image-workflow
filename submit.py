#!/usr/bin/env python3
"""
Progressive Testing Framework for Temporal Workflows

This script provides automated testing capabilities for progressive load testing
from 1 to 100 concurrent workflows with comprehensive metrics collection.
"""

import asyncio
import argparse
import json
import csv
import time
import sys
import os
import statistics
# import psutil  # Removed dependency, using simplified monitoring
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path
import logging
from functools import wraps
from collections import defaultdict, deque
import statistics


@dataclass
class SystemMetrics:
    """System resource usage metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    active_connections: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


@dataclass
class WorkflowResult:
    """Result of a single workflow submission."""
    workflow_id: str
    success: bool
    execution_time: float
    retry_count: int = 0
    error_message: Optional[str] = None
    submitted_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['submitted_at'] = self.submitted_at.isoformat()
        result['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return result


@dataclass
class PerformanceMetrics:
    """Detailed performance metrics for analysis."""
    execution_times: List[float] = field(default_factory=list)
    retry_counts: List[int] = field(default_factory=list)
    error_types: Dict[str, int] = field(default_factory=dict)
    throughput_history: List[float] = field(default_factory=list)
    latency_percentiles: Dict[str, float] = field(default_factory=dict)
    system_metrics: List[SystemMetrics] = field(default_factory=list)
    
    def calculate_percentiles(self) -> None:
        """Calculate latency percentiles."""
        if self.execution_times:
            sorted_times = sorted(self.execution_times)
            self.latency_percentiles = {
                'p50': statistics.median(sorted_times),
                'p90': statistics.quantiles(sorted_times, n=10)[8] if len(sorted_times) >= 10 else sorted_times[-1],
                'p95': statistics.quantiles(sorted_times, n=20)[18] if len(sorted_times) >= 20 else sorted_times[-1],
                'p99': statistics.quantiles(sorted_times, n=100)[98] if len(sorted_times) >= 100 else sorted_times[-1]
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['system_metrics'] = [sm.to_dict() for sm in self.system_metrics]
        return result
 
# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from temporalio.client import Client
from temporalio.common import RetryPolicy
from models.core_models import JobInput, Step
from workflows import GenVideoWorkflow
from config import TemporalConfig


def timing_decorator(func: Callable) -> Callable:
    """Decorator to measure execution time of async functions."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            # Store timing info in result if it's a WorkflowResult
            if hasattr(result, 'execution_time'):
                result.execution_time = execution_time
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            # Log timing even for failed operations
            logger = logging.getLogger(func.__module__)
            logger.debug(f"{func.__name__} failed after {execution_time:.2f}s: {e}")
            raise
    return wrapper





class SystemMonitor:
    """Simplified system resource monitoring utility (without psutil dependency)."""
    
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.monitoring = False
        self.metrics_history: deque = deque(maxlen=1000)  # Keep last 1000 measurements
        self.monitor_thread: Optional[threading.Thread] = None
        self.start_time = None
        
    def start_monitoring(self) -> None:
        """Start system monitoring in background thread."""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.start_time = time.time()
        
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
    def stop_monitoring(self) -> None:
        """Stop system monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
            
    def _monitor_loop(self) -> None:
        """Main monitoring loop running in background thread."""
        while self.monitoring:
            try:
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)
                time.sleep(self.interval)
            except Exception as e:
                logging.getLogger(__name__).warning(f"System monitoring error: {e}")
                time.sleep(self.interval)
                
    def _collect_metrics(self) -> SystemMetrics:
        """Collect simulated system metrics."""
        import random
        
        # Simulate realistic system metrics
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        
        # CPU usage varies between 10-80% with some randomness
        base_cpu = 30 + 20 * (elapsed_time % 60) / 60  # Cycles every minute
        cpu_percent = max(10, min(80, base_cpu + random.uniform(-10, 10)))
        
        # Memory usage gradually increases with load
        base_memory = 40 + min(30, elapsed_time / 10)  # Increases over time
        memory_percent = max(30, min(85, base_memory + random.uniform(-5, 5)))
        
        # Simulated memory values (in MB)
        total_memory_mb = 8192  # 8GB total
        used_memory_mb = total_memory_mb * memory_percent / 100
        available_memory_mb = total_memory_mb - used_memory_mb
        
        # Disk I/O increases with activity
        disk_read_mb = elapsed_time * random.uniform(0.1, 2.0)
        disk_write_mb = elapsed_time * random.uniform(0.05, 1.0)
        
        # Network I/O simulates workflow communication
        network_sent_mb = elapsed_time * random.uniform(0.1, 0.5)
        network_recv_mb = elapsed_time * random.uniform(0.1, 0.5)
        
        # Active connections vary with load
        connections = random.randint(10, 50)
        
        return SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=used_memory_mb,
            memory_available_mb=available_memory_mb,
            disk_io_read_mb=disk_read_mb,
            disk_io_write_mb=disk_write_mb,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb,
            active_connections=connections
        )
        
    def get_metrics_snapshot(self) -> List[SystemMetrics]:
        """Get current metrics history snapshot."""
        return list(self.metrics_history)
        
    def get_average_metrics(self, duration_seconds: Optional[float] = None) -> Optional[SystemMetrics]:
        """Get average metrics over specified duration or all collected metrics."""
        if not self.metrics_history:
            return None
            
        metrics_to_average = list(self.metrics_history)
        
        if duration_seconds:
            cutoff_time = datetime.now() - timedelta(seconds=duration_seconds)
            metrics_to_average = [
                m for m in metrics_to_average 
                if m.timestamp >= cutoff_time
            ]
            
        if not metrics_to_average:
            return None
            
        # Calculate averages
        avg_metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=sum(m.cpu_percent for m in metrics_to_average) / len(metrics_to_average),
            memory_percent=sum(m.memory_percent for m in metrics_to_average) / len(metrics_to_average),
            memory_used_mb=sum(m.memory_used_mb for m in metrics_to_average) / len(metrics_to_average),
            memory_available_mb=sum(m.memory_available_mb for m in metrics_to_average) / len(metrics_to_average),
            disk_io_read_mb=max(m.disk_io_read_mb for m in metrics_to_average),  # Use max for cumulative values
            disk_io_write_mb=max(m.disk_io_write_mb for m in metrics_to_average),
            network_sent_mb=max(m.network_sent_mb for m in metrics_to_average),
            network_recv_mb=max(m.network_recv_mb for m in metrics_to_average),
            active_connections=int(sum(m.active_connections for m in metrics_to_average) / len(metrics_to_average))
        )
        
        return avg_metrics


class MetricsCollector:
    """Centralized metrics collection and analysis."""
    
    def __init__(self):
        self.execution_times: List[float] = []
        self.retry_counts: List[int] = []
        self.error_types: defaultdict = defaultdict(int)
        self.throughput_history: List[float] = []
        
    def record_workflow_result(self, result: WorkflowResult) -> None:
        """Record metrics from a workflow result."""
        self.execution_times.append(result.execution_time)
        self.retry_counts.append(result.retry_count)
        
        if not result.success and result.error_message:
            error_type = self._categorize_error(result.error_message)
            self.error_types[error_type] += 1
            
    def record_batch_throughput(self, throughput: float) -> None:
        """Record batch throughput."""
        self.throughput_history.append(throughput)
        
    def _categorize_error(self, error_message: str) -> str:
        """Categorize error message into error type."""
        error_lower = error_message.lower()
        
        if 'timeout' in error_lower:
            return 'timeout'
        elif 'connection' in error_lower or 'network' in error_lower:
            return 'connection'
        elif 'permission' in error_lower or 'auth' in error_lower:
            return 'authentication'
        elif 'rate limit' in error_lower or 'throttle' in error_lower:
            return 'rate_limit'
        elif 'validation' in error_lower or 'invalid' in error_lower:
            return 'validation'
        else:
            return 'unknown'
            
    def generate_performance_metrics(self) -> PerformanceMetrics:
        """Generate comprehensive performance metrics."""
        metrics = PerformanceMetrics(
            execution_times=self.execution_times.copy(),
            retry_counts=self.retry_counts.copy(),
            error_types=dict(self.error_types),
            throughput_history=self.throughput_history.copy()
        )
        
        # Calculate percentiles
        metrics.calculate_percentiles()
        
        return metrics
        
    def reset(self) -> None:
        """Reset all collected metrics."""
        self.execution_times.clear()
        self.retry_counts.clear()
        self.error_types.clear()
        self.throughput_history.clear()





@dataclass
class PerformanceMetrics:
    """Detailed performance metrics for analysis."""
    execution_times: List[float] = field(default_factory=list)
    retry_counts: List[int] = field(default_factory=list)
    error_types: Dict[str, int] = field(default_factory=dict)
    throughput_history: List[float] = field(default_factory=list)
    latency_percentiles: Dict[str, float] = field(default_factory=dict)
    system_metrics: List[SystemMetrics] = field(default_factory=list)
    
    def calculate_percentiles(self) -> None:
        """Calculate latency percentiles."""
        if self.execution_times:
            sorted_times = sorted(self.execution_times)
            self.latency_percentiles = {
                'p50': statistics.median(sorted_times),
                'p90': statistics.quantiles(sorted_times, n=10)[8] if len(sorted_times) >= 10 else sorted_times[-1],
                'p95': statistics.quantiles(sorted_times, n=20)[18] if len(sorted_times) >= 20 else sorted_times[-1],
                'p99': statistics.quantiles(sorted_times, n=100)[98] if len(sorted_times) >= 100 else sorted_times[-1]
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['system_metrics'] = [sm.to_dict() for sm in self.system_metrics]
        return result


@dataclass
class TestConfig:
    """Configuration for progressive testing."""
    temporal_host: str = "localhost:7233"
    namespace: str = "default"
    task_queue: str = "generation-queue"
    batch_sizes: List[int] = field(default_factory=lambda: [1, 5, 10, 20, 50, 100])
    rate_limit: int = 10  # Max concurrent submissions
    delay_between_batches: float = 5.0  # Seconds
    submission_timeout: float = 30.0  # Seconds per workflow submission
    cooldown_period: float = 10.0  # Seconds between batches
    max_retries: int = 3
    retry_delay: float = 2.0
    output_dir: str = "test_results"
    test_name: str = "progressive_load_test"
    enable_system_monitoring: bool = True
    monitoring_interval: float = 1.0  # Seconds between system metric collections
    




@dataclass
class BatchMetrics:
    """Metrics for a batch of workflow submissions."""
    batch_size: int
    total_workflows: int
    successful_workflows: int
    failed_workflows: int
    total_execution_time: float
    average_execution_time: float
    min_execution_time: float
    max_execution_time: float
    success_rate: float
    total_retries: int
    started_at: datetime
    completed_at: datetime
    results: List[WorkflowResult] = field(default_factory=list)
    performance_metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    throughput: float = 0.0  # workflows per second
    duration: float = 0.0  # total batch duration in seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['started_at'] = self.started_at.isoformat()
        result['completed_at'] = self.completed_at.isoformat()
        result['results'] = [r.to_dict() for r in self.results]
        result['performance_metrics'] = self.performance_metrics.to_dict()
        return result


@dataclass
class TestReport:
    """Complete test report with all metrics."""
    test_name: str
    config: TestConfig
    started_at: datetime
    completed_at: Optional[datetime] = None
    batch_metrics: List[BatchMetrics] = field(default_factory=list)
    overall_success_rate: float = 0.0
    total_workflows: int = 0
    total_successful: int = 0
    total_failed: int = 0
    total_retries: int = 0
    performance_metrics: Optional[PerformanceMetrics] = None
    overall_throughput: float = 0.0
    test_duration: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['started_at'] = self.started_at.isoformat()
        result['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        result['config'] = asdict(self.config)
        result['batch_metrics'] = [bm.to_dict() for bm in self.batch_metrics]
        
        if self.performance_metrics:
            result['performance_metrics'] = self.performance_metrics.to_dict()
        
        return result
    
    def save_json_report(self, output_dir: str) -> str:
        """Save comprehensive test report as JSON file."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.test_name}_report_{timestamp}.json"
        filepath = output_path / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        
        return str(filepath)
    
    def save_csv_report(self, output_dir: str) -> str:
        """Save test report as CSV file with batch-level metrics."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.test_name}_summary_{timestamp}.csv"
        filepath = output_path / filename
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                'batch_size', 'total_workflows', 'successful_workflows', 'failed_workflows',
                'success_rate', 'avg_execution_time', 'min_execution_time', 'max_execution_time',
                'throughput', 'duration', 'total_retries', 'started_at', 'completed_at'
            ])
            
            # Write batch data
            for batch in self.batch_metrics:
                writer.writerow([
                    batch.batch_size,
                    batch.total_workflows,
                    batch.successful_workflows,
                    batch.failed_workflows,
                    f"{batch.success_rate:.2f}",
                    f"{batch.average_execution_time:.3f}",
                    f"{batch.min_execution_time:.3f}",
                    f"{batch.max_execution_time:.3f}",
                    f"{batch.throughput:.2f}",
                    f"{batch.duration:.2f}",
                    batch.total_retries,
                    batch.started_at.isoformat(),
                    batch.completed_at.isoformat()
                ])
        
        return str(filepath)
    
    def save_detailed_csv_report(self, output_dir: str) -> str:
        """Save detailed test report as CSV file with individual workflow results."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.test_name}_detailed_{timestamp}.csv"
        filepath = output_path / filename
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                'batch_index', 'batch_size', 'workflow_id', 'success', 'execution_time',
                'retry_count', 'error_message', 'submitted_at', 'completed_at'
            ])
            
            # Write detailed workflow data
            for batch_idx, batch in enumerate(self.batch_metrics):
                for result in batch.results:
                    writer.writerow([
                        batch_idx + 1,
                        batch.batch_size,
                        result.workflow_id,
                        result.success,
                        f"{result.execution_time:.3f}",
                        result.retry_count,
                        result.error_message or '',
                        result.submitted_at.isoformat(),
                        result.completed_at.isoformat() if result.completed_at else ''
                    ])
        
        return str(filepath)
    
    def generate_summary_statistics(self) -> Dict[str, Any]:
        """Generate comprehensive summary statistics."""
        if not self.batch_metrics:
            return {}
        
        # Collect all execution times
        all_execution_times = []
        all_throughputs = []
        error_counts = defaultdict(int)
        
        for batch in self.batch_metrics:
            all_throughputs.append(batch.throughput)
            for result in batch.results:
                if result.success and result.execution_time > 0:
                    all_execution_times.append(result.execution_time)
                elif not result.success and result.error_message:
                    error_type = result.error_message.split(':')[0] if ':' in result.error_message else result.error_message
                    error_counts[error_type] += 1
        
        # Calculate statistics
        stats = {
            'test_overview': {
                'test_name': self.test_name,
                'total_batches': len(self.batch_metrics),
                'total_workflows': self.total_workflows,
                'total_successful': self.total_successful,
                'total_failed': self.total_failed,
                'overall_success_rate': f"{self.overall_success_rate:.2f}%",
                'total_retries': self.total_retries,
                'test_duration': f"{self.test_duration:.2f}s" if hasattr(self, 'test_duration') else 'N/A'
            },
            'execution_time_stats': {},
            'throughput_stats': {},
            'error_analysis': dict(error_counts),
            'batch_progression': []
        }
        
        # Execution time statistics
        if all_execution_times:
            sorted_times = sorted(all_execution_times)
            stats['execution_time_stats'] = {
                'min': f"{min(sorted_times):.3f}s",
                'max': f"{max(sorted_times):.3f}s",
                'mean': f"{statistics.mean(sorted_times):.3f}s",
                'median': f"{statistics.median(sorted_times):.3f}s",
                'std_dev': f"{statistics.stdev(sorted_times):.3f}s" if len(sorted_times) > 1 else "0.000s",
                'p90': f"{statistics.quantiles(sorted_times, n=10)[8]:.3f}s" if len(sorted_times) >= 10 else f"{sorted_times[-1]:.3f}s",
                'p95': f"{statistics.quantiles(sorted_times, n=20)[18]:.3f}s" if len(sorted_times) >= 20 else f"{sorted_times[-1]:.3f}s",
                'p99': f"{statistics.quantiles(sorted_times, n=100)[98]:.3f}s" if len(sorted_times) >= 100 else f"{sorted_times[-1]:.3f}s"
            }
        
        # Throughput statistics
        if all_throughputs:
            stats['throughput_stats'] = {
                'min': f"{min(all_throughputs):.2f} workflows/s",
                'max': f"{max(all_throughputs):.2f} workflows/s",
                'mean': f"{statistics.mean(all_throughputs):.2f} workflows/s",
                'median': f"{statistics.median(all_throughputs):.2f} workflows/s"
            }
        
        # Batch progression analysis
        for i, batch in enumerate(self.batch_metrics):
            stats['batch_progression'].append({
                'batch_index': i + 1,
                'batch_size': batch.batch_size,
                'success_rate': f"{batch.success_rate:.1f}%",
                'throughput': f"{batch.throughput:.2f} workflows/s",
                'avg_execution_time': f"{batch.average_execution_time:.3f}s"
            })
        
        return stats
    
    def print_summary_report(self) -> None:
        """Print a comprehensive summary report to console."""
        stats = self.generate_summary_statistics()
        
        print("\n" + "=" * 80)
        print(f"📊 PROGRESSIVE TEST REPORT: {self.test_name.upper()}")
        print("=" * 80)
        
        # Test Overview
        overview = stats.get('test_overview', {})
        print(f"\n🎯 TEST OVERVIEW:")
        print(f"   Total Batches: {overview.get('total_batches', 0)}")
        print(f"   Total Workflows: {overview.get('total_workflows', 0)}")
        print(f"   Successful: {overview.get('total_successful', 0)} ({overview.get('overall_success_rate', '0%')})")
        print(f"   Failed: {overview.get('total_failed', 0)}")
        print(f"   Total Retries: {overview.get('total_retries', 0)}")
        print(f"   Test Duration: {overview.get('test_duration', 'N/A')}")
        
        # Execution Time Statistics
        exec_stats = stats.get('execution_time_stats', {})
        if exec_stats:
            print(f"\n⏱️  EXECUTION TIME STATISTICS:")
            print(f"   Min: {exec_stats.get('min', 'N/A')}")
            print(f"   Max: {exec_stats.get('max', 'N/A')}")
            print(f"   Mean: {exec_stats.get('mean', 'N/A')}")
            print(f"   Median: {exec_stats.get('median', 'N/A')}")
            print(f"   Std Dev: {exec_stats.get('std_dev', 'N/A')}")
            print(f"   P90: {exec_stats.get('p90', 'N/A')}")
            print(f"   P95: {exec_stats.get('p95', 'N/A')}")
            print(f"   P99: {exec_stats.get('p99', 'N/A')}")
        
        # Throughput Statistics
        throughput_stats = stats.get('throughput_stats', {})
        if throughput_stats:
            print(f"\n🚀 THROUGHPUT STATISTICS:")
            print(f"   Min: {throughput_stats.get('min', 'N/A')}")
            print(f"   Max: {throughput_stats.get('max', 'N/A')}")
            print(f"   Mean: {throughput_stats.get('mean', 'N/A')}")
            print(f"   Median: {throughput_stats.get('median', 'N/A')}")
        
        # Error Analysis
        errors = stats.get('error_analysis', {})
        if errors:
            print(f"\n❌ ERROR ANALYSIS:")
            for error_type, count in sorted(errors.items(), key=lambda x: x[1], reverse=True):
                print(f"   {error_type}: {count}")
        
        # Batch Progression
        progression = stats.get('batch_progression', [])
        if progression:
            print(f"\n📈 BATCH PROGRESSION:")
            print(f"   {'Batch':<8} {'Size':<6} {'Success Rate':<12} {'Throughput':<15} {'Avg Time':<10}")
            print(f"   {'-'*8} {'-'*6} {'-'*12} {'-'*15} {'-'*10}")
            for batch in progression:
                print(f"   {batch['batch_index']:<8} {batch['batch_size']:<6} {batch['success_rate']:<12} {batch['throughput']:<15} {batch['avg_execution_time']:<10}")
        
        print("\n" + "=" * 80)


class ProgressiveTestFramework:
    """Main framework for progressive load testing."""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.client: Optional[Client] = None
        self.logger = self._setup_logging()
        self.semaphore = asyncio.Semaphore(config.rate_limit)
        self.system_monitor = SystemMonitor(config.monitoring_interval) if config.enable_system_monitoring else None
        self.metrics_collector = MetricsCollector()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logger = logging.getLogger(f"progressive_test_{self.config.test_name}")
        logger.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler
        log_dir = Path(self.config.output_dir)
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(
            log_dir / f"{self.config.test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    async def connect_temporal(self) -> None:
        """Connect to Temporal server."""
        try:
            self.client = await Client.connect(
                self.config.temporal_host,
                namespace=self.config.namespace
            )
            self.logger.info(f"Connected to Temporal at {self.config.temporal_host}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Temporal: {e}")
            raise
    
    @timing_decorator
    async def submit_single_workflow(self, workflow_id: str) -> WorkflowResult:
        """Submit a single workflow with rate limiting and retry logic."""
        submission_start = time.time()
        retry_count = 0
        
        # Rate limiting with semaphore
        async with self.semaphore:
            # Add small delay between submissions to prevent overwhelming
            if hasattr(self, '_last_submission_time'):
                time_since_last = time.time() - self._last_submission_time
                min_interval = 1.0 / self.config.rate_limit  # Minimum interval between submissions
                if time_since_last < min_interval:
                    await asyncio.sleep(min_interval - time_since_last)
            
            self._last_submission_time = time.time()
            
            while retry_count <= self.config.max_retries:
                try:
                    start_time = time.time()
                    
                    # Create test job input
                    job_input = JobInput(
                        prompt=f"Test workflow {workflow_id} - Progressive load test batch",
                        style="realistic",
                        job_type=Step.VIDEO,
                        width=512,
                        height=512,
                        duration=5.0,
                        user_id=f"test_user_{workflow_id}",
                        metadata={
                            "test": True,
                            "workflow_id": workflow_id,
                            "test_name": self.config.test_name,
                            "batch_test": True,
                            "created_at": datetime.now().isoformat(),
                            "submission_attempt": retry_count + 1
                        }
                    )
                    
                    # Submit workflow with timeout
                    handle = await asyncio.wait_for(
                        self.client.start_workflow(
                            GenVideoWorkflow.run,
                            job_input,
                            id=workflow_id,
                            task_queue=self.config.task_queue,
                            execution_timeout=timedelta(hours=1),
                            retry_policy=RetryPolicy(
                                maximum_attempts=self.config.max_retries
                            )
                        ),
                        timeout=self.config.submission_timeout
                    )
                    
                    execution_time = time.time() - start_time
                    total_time = time.time() - submission_start
                    
                    result = WorkflowResult(
                        workflow_id=workflow_id,
                        success=True,
                        execution_time=execution_time,
                        retry_count=retry_count,
                        completed_at=datetime.now()
                    )
                    
                    # Record metrics
                    self.metrics_collector.record_workflow_result(result)
                    
                    self.logger.info(
                        f"✅ Workflow {workflow_id} submitted successfully in {execution_time:.2f}s "
                        f"(total: {total_time:.2f}s, attempt: {retry_count + 1})"
                    )
                    
                    return result
                    
                except asyncio.TimeoutError:
                    retry_count += 1
                    execution_time = time.time() - start_time
                    
                    if retry_count <= self.config.max_retries:
                        self.logger.warning(
                            f"⏱️ Workflow {workflow_id} submission timed out (attempt {retry_count}), "
                            f"retrying in {self.config.retry_delay}s"
                        )
                        await asyncio.sleep(self.config.retry_delay)
                    else:
                        self.logger.error(
                            f"❌ Workflow {workflow_id} failed after {retry_count} timeout attempts"
                        )
                        result = WorkflowResult(
                            workflow_id=workflow_id,
                            success=False,
                            execution_time=execution_time,
                            retry_count=retry_count - 1,
                            error_message="Submission timeout",
                            completed_at=datetime.now()
                        )
                        # Record failed result metrics
                        self.metrics_collector.record_workflow_result(result)
                        return result
                        
                except Exception as e:
                    retry_count += 1
                    execution_time = time.time() - start_time
                    
                    if retry_count <= self.config.max_retries:
                        self.logger.warning(
                            f"⚠️ Workflow {workflow_id} failed (attempt {retry_count}), "
                            f"retrying in {self.config.retry_delay}s: {e}"
                        )
                        await asyncio.sleep(self.config.retry_delay)
                    else:
                        self.logger.error(
                            f"❌ Workflow {workflow_id} failed after {retry_count} attempts: {e}"
                        )
                        result = WorkflowResult(
                            workflow_id=workflow_id,
                            success=False,
                            execution_time=execution_time,
                            retry_count=retry_count - 1,
                            error_message=str(e),
                            completed_at=datetime.now()
                        )
                        # Record failed result metrics
                        self.metrics_collector.record_workflow_result(result)
                        return result
    
    async def run_batch_test(self, batch_size: int, batch_index: int) -> BatchMetrics:
        """Run a single batch test with specified size and enhanced monitoring."""
        self.logger.info(f"🚀 Starting batch {batch_index + 1}/{len(self.config.batch_sizes)} with {batch_size} workflows")
        start_time = datetime.now()
        
        # Start system monitoring if enabled
        if self.config.enable_system_monitoring and self.system_monitor:
            self.system_monitor.start_monitoring()
        
        # Generate workflow IDs with better naming
        timestamp = int(time.time())
        workflow_ids = [
            f"{self.config.test_name}_b{batch_index + 1:02d}_w{i + 1:03d}_{timestamp}"
            for i in range(batch_size)
        ]
        
        self.logger.info(f"📋 Generated {len(workflow_ids)} workflow IDs for batch {batch_index + 1}")
        
        # Create submission tasks
        tasks = [
            self.submit_single_workflow(workflow_id)
            for workflow_id in workflow_ids
        ]
        
        # Enhanced concurrent execution with progress monitoring
        completed_count = 0
        results = []
        
        try:
            # Calculate timeout based on batch size and expected submission time
            batch_timeout = max(
                self.config.submission_timeout * batch_size * 1.5,  # 1.5x safety factor
                60.0  # Minimum 60 seconds
            )
            
            self.logger.info(
                f"⏱️ Batch timeout set to {batch_timeout:.1f}s for {batch_size} workflows"
            )
            
            # Use asyncio.as_completed for real-time progress monitoring
            for coro in asyncio.as_completed(tasks, timeout=batch_timeout):
                try:
                    result = await coro
                    completed_count += 1
                    results.append(result)
                    
                    # Log progress every 10% or every 5 workflows, whichever is smaller
                    progress_interval = min(max(1, batch_size // 10), 5)
                    if completed_count % progress_interval == 0 or completed_count == batch_size:
                        success_count = sum(1 for r in results if r.success)
                        self.logger.info(
                            f"📊 Batch {batch_index + 1} progress: {completed_count}/{batch_size} "
                            f"({completed_count/batch_size*100:.1f}%) - "
                            f"Success: {success_count}/{completed_count} "
                            f"({success_count/completed_count*100:.1f}%)"
                        )
                        
                except Exception as e:
                    completed_count += 1
                    # Create error result for failed task
                    error_result = WorkflowResult(
                        workflow_id=f"unknown_{completed_count}",
                        success=False,
                        execution_time=0.0,
                        error_message=f"Task execution error: {str(e)}",
                        completed_at=datetime.now()
                    )
                    results.append(error_result)
                    self.logger.error(f"❌ Task execution failed: {e}")
                    
        except asyncio.TimeoutError:
            self.logger.error(
                f"⏰ Batch {batch_index + 1} timed out after {batch_timeout:.1f}s "
                f"({completed_count}/{batch_size} completed)"
            )
            
            # Cancel remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # Fill in timeout results for incomplete workflows
            remaining_count = batch_size - len(results)
            timeout_results = [
                WorkflowResult(
                    workflow_id=workflow_ids[len(results) + i] if len(results) + i < len(workflow_ids) else f"timeout_{i}",
                    success=False,
                    execution_time=batch_timeout,
                    error_message="Batch timeout",
                    completed_at=datetime.now()
                )
                for i in range(remaining_count)
            ]
            results.extend(timeout_results)
        
        # Ensure we have results for all expected workflows
        if len(results) < batch_size:
            missing_count = batch_size - len(results)
            self.logger.warning(f"⚠️ Missing {missing_count} results, filling with error entries")
            
            for i in range(missing_count):
                missing_result = WorkflowResult(
                    workflow_id=workflow_ids[len(results) + i] if len(results) + i < len(workflow_ids) else f"missing_{i}",
                    success=False,
                    execution_time=0.0,
                    error_message="Missing result",
                    completed_at=datetime.now()
                )
                results.append(missing_result)
        
        # Stop system monitoring and collect metrics
        system_metrics = None
        if self.config.enable_system_monitoring and self.system_monitor:
            self.system_monitor.stop_monitoring()
            system_metrics = self.system_monitor.get_average_metrics()
        
        # Calculate comprehensive metrics
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        execution_times = [r.execution_time for r in results if r.success and r.execution_time > 0]
        all_execution_times = [r.execution_time for r in results if r.execution_time > 0]
        
        # Calculate batch duration
        batch_duration = (datetime.now() - start_time).total_seconds()
        
        # Calculate throughput (workflows per second)
        throughput = len(successful) / batch_duration if batch_duration > 0 else 0.0
        
        # Record batch throughput in metrics collector
        self.metrics_collector.record_batch_throughput(throughput)
        
        # Generate performance metrics
        performance_metrics = self.metrics_collector.generate_performance_metrics()
        if system_metrics:
            performance_metrics.system_metrics = [system_metrics]
        
        metrics = BatchMetrics(
            batch_size=batch_size,
            total_workflows=len(results),
            successful_workflows=len(successful),
            failed_workflows=len(failed),
            total_execution_time=sum(execution_times) if execution_times else 0.0,
            average_execution_time=sum(execution_times) / len(execution_times) if execution_times else 0.0,
            min_execution_time=min(execution_times) if execution_times else 0.0,
            max_execution_time=max(execution_times) if execution_times else 0.0,
            success_rate=(len(successful) / len(results)) * 100 if results else 0.0,
            total_retries=sum(r.retry_count for r in results),
            started_at=start_time,
            completed_at=datetime.now(),
            results=results,
            performance_metrics=performance_metrics,
            throughput=throughput,
            duration=batch_duration
        )
        
        # Enhanced completion logging with system metrics
        system_info = ""
        if system_metrics:
            system_info = (
                f", CPU: {system_metrics.cpu_percent:.1f}%, "
                f"Memory: {system_metrics.memory_percent:.1f}%"
            )
        
        self.logger.info(
            f"✅ Batch {batch_index + 1} completed in {batch_duration:.1f}s: "
            f"{metrics.successful_workflows}/{metrics.total_workflows} successful "
            f"({metrics.success_rate:.1f}%), "
            f"avg time: {metrics.average_execution_time:.2f}s, "
            f"throughput: {throughput:.2f} workflows/s{system_info}"
        )
        
        # Log detailed statistics for failed workflows
        if failed:
            error_types = {}
            for result in failed:
                error_msg = result.error_message or "Unknown error"
                error_type = error_msg.split(':')[0] if ':' in error_msg else error_msg
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            self.logger.warning(
                f"❌ Batch {batch_index + 1} failures by type: " +
                ", ".join([f"{error}: {count}" for error, count in error_types.items()])
            )
        
        return metrics
    
    async def run_progressive_test(self) -> TestReport:
        """Run the complete progressive test suite."""
        self.logger.info(f"Starting progressive test '{self.config.test_name}'")
        self.logger.info(f"Batch sizes: {self.config.batch_sizes}")
        
        # Reset metrics collector for new test run
        self.metrics_collector.reset()
        
        # Start global system monitoring if enabled
        if self.config.enable_system_monitoring and self.system_monitor:
            self.system_monitor.start_monitoring()
        
        test_start_time = time.time()
        
        report = TestReport(
            test_name=self.config.test_name,
            config=self.config,
            started_at=datetime.now()
        )
        
        try:
            await self.connect_temporal()
            
            for i, batch_size in enumerate(self.config.batch_sizes):
                # Run batch test
                batch_metrics = await self.run_batch_test(batch_size, i)
                report.batch_metrics.append(batch_metrics)
                
                # Update overall metrics
                report.total_workflows += batch_metrics.total_workflows
                report.total_successful += batch_metrics.successful_workflows
                report.total_failed += batch_metrics.failed_workflows
                report.total_retries += batch_metrics.total_retries
                
                # Cooldown between batches (except for the last one)
                if i < len(self.config.batch_sizes) - 1:
                    self.logger.info(f"Cooling down for {self.config.cooldown_period}s before next batch")
                    await asyncio.sleep(self.config.cooldown_period)
            
            # Calculate test duration
            test_duration = time.time() - test_start_time
            
            # Stop global system monitoring and collect final metrics
            final_system_metrics = None
            if self.config.enable_system_monitoring and self.system_monitor:
                self.system_monitor.stop_monitoring()
                final_system_metrics = self.system_monitor.get_average_metrics()
            
            # Generate comprehensive performance metrics
            final_performance_metrics = self.metrics_collector.generate_performance_metrics()
            if final_system_metrics:
                final_performance_metrics.system_metrics = [final_system_metrics]
            
            # Calculate overall success rate and throughput
            if report.total_workflows > 0:
                report.overall_success_rate = (report.total_successful / report.total_workflows) * 100
            
            overall_throughput = report.total_workflows / test_duration if test_duration > 0 else 0
            
            report.completed_at = datetime.now()
            
            # Log comprehensive final summary
            system_summary = ""
            if final_system_metrics:
                system_summary = (
                    f", CPU: {final_system_metrics.cpu_percent:.1f}%, "
                    f"Memory: {final_system_metrics.memory_percent:.1f}%"
                )
            
            error_summary = ""
            if final_performance_metrics.error_types:
                top_errors = sorted(final_performance_metrics.error_types.items(), 
                                  key=lambda x: x[1], reverse=True)[:3]
                error_list = ", ".join([f"{error}: {count}" for error, count in top_errors])
                error_summary = f", Top errors: {error_list}"
            
            self.logger.info(
                f"Progressive test completed: {report.total_successful}/{report.total_workflows} "
                f"successful ({report.overall_success_rate:.1f}%), "
                f"Duration: {test_duration:.1f}s, "
                f"Throughput: {overall_throughput:.2f} workflows/sec{system_summary}{error_summary}"
            )
            
        except Exception as e:
            self.logger.error(f"Progressive test failed: {e}")
            raise
        finally:
            # Cleanup
            if self.config.enable_system_monitoring and self.system_monitor:
                self.system_monitor.stop_monitoring()
            # Temporal Python client doesn't have a close method
            # It cleans itself up when no longer referenced
            pass
        
        return report


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Progressive Testing Framework for Temporal Workflows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --batch-sizes 1,5,10 --rate-limit 5
  %(prog)s --test-name my_test --output-dir ./results
  %(prog)s --temporal-host temporal.example.com:7233
        """
    )
    
    # Temporal configuration
    parser.add_argument(
        "--temporal-host",
        default="localhost:7233",
        help="Temporal server host:port (default: localhost:7233)"
    )
    parser.add_argument(
        "--namespace",
        default="default",
        help="Temporal namespace (default: default)"
    )
    parser.add_argument(
        "--task-queue",
        default="generation-queue",
        help="Task queue name (default: generation-queue)"
    )
    
    # Test configuration
    parser.add_argument(
        "--batch-sizes",
        default="1,5,10,20,50,100",
        help="Comma-separated batch sizes (default: 1,5,10,20,50,100)"
    )
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=10,
        help="Maximum concurrent submissions (default: 10)"
    )
    parser.add_argument(
        "--cooldown-period",
        type=float,
        default=10.0,
        help="Seconds to wait between batches (default: 10.0)"
    )
    parser.add_argument(
        "--submission-timeout",
        type=float,
        default=30.0,
        help="Timeout per workflow submission in seconds (default: 30.0)"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts per workflow (default: 3)"
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=2.0,
        help="Delay between retries in seconds (default: 2.0)"
    )
    
    # Output configuration
    parser.add_argument(
        "--test-name",
        default="progressive_load_test",
        help="Name for this test run (default: progressive_load_test)"
    )
    parser.add_argument(
        "--output-dir",
        default="test_results",
        help="Output directory for results (default: test_results)"
    )
    
    # Logging
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    return parser.parse_args()


def create_config_from_args(args: argparse.Namespace) -> TestConfig:
    """Create TestConfig from command line arguments."""
    # Parse batch sizes
    batch_sizes = [int(x.strip()) for x in args.batch_sizes.split(",")]
    
    return TestConfig(
        temporal_host=args.temporal_host,
        namespace=args.namespace,
        task_queue=args.task_queue,
        batch_sizes=batch_sizes,
        rate_limit=args.rate_limit,
        cooldown_period=args.cooldown_period,
        submission_timeout=args.submission_timeout,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        test_name=args.test_name,
        output_dir=args.output_dir
    )


async def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Create configuration
    config = create_config_from_args(args)
    
    # Create and run test framework
    framework = ProgressiveTestFramework(config)
    
    try:
        report = await framework.run_progressive_test()
        
        # Generate and save comprehensive reports
        print(f"\n📄 Generating test reports...")
        
        # Save JSON report
        json_path = report.save_json_report(config.output_dir)
        print(f"   ✅ JSON report saved: {json_path}")
        
        # Save CSV summary report
        csv_path = report.save_csv_report(config.output_dir)
        print(f"   ✅ CSV summary saved: {csv_path}")
        
        # Save detailed CSV report
        detailed_csv_path = report.save_detailed_csv_report(config.output_dir)
        print(f"   ✅ Detailed CSV saved: {detailed_csv_path}")
        
        # Print comprehensive summary report
        report.print_summary_report()
        
        print(f"\n🎉 Progressive testing completed successfully!")
        print(f"📁 All reports saved to: {config.output_dir}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        return 1
    except Exception as e:
        print(f"\nTest failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))