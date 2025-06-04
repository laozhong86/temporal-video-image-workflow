#!/usr/bin/env python3
"""
Comprehensive Test Runner for Temporal Video Generation System

This script runs all available tests in a structured manner and generates
a comprehensive test report with results, metrics, and recommendations.
"""

import asyncio
import subprocess
import sys
import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Test execution result."""
    name: str
    category: str
    status: str  # 'passed', 'failed', 'skipped', 'error'
    duration: float
    output: str
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class TestSuite:
    """Test suite configuration."""
    name: str
    category: str
    script_path: str
    description: str
    dependencies: List[str] = None
    timeout: int = 300  # 5 minutes default
    requires_services: List[str] = None


class ComprehensiveTestRunner:
    """Comprehensive test runner for the Temporal system."""
    
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root or os.getcwd())
        self.results: List[TestResult] = []
        self.start_time = datetime.now()
        self.services_status = {}
        
        # Define test suites
        self.test_suites = [
            # Basic functionality tests
            TestSuite(
                name="Simple Workflow Test",
                category="Basic Functionality",
                script_path="test_simple_workflow.py",
                description="Tests basic workflow execution",
                requires_services=["temporal"]
            ),
            TestSuite(
                name="Video Workflow Structure Test",
                category="Basic Functionality",
                script_path="test_gen_video_workflow.py",
                description="Tests video generation workflow structure",
                requires_services=[]
            ),
            TestSuite(
                name="Simple Callback Server Test",
                category="Basic Functionality",
                script_path="simple_test.py",
                description="Basic callback server functionality",
                requires_services=["callback_server"]
            ),
            
            # Component tests
            TestSuite(
                name="Callback Server Test",
                category="Component Tests",
                script_path="test_callback_server.py",
                description="Comprehensive callback server testing",
                requires_services=["temporal", "callback_server"],
                timeout=600
            ),
            TestSuite(
                name="Worker Service Test",
                category="Component Tests",
                script_path="test_worker_service.py",
                description="Worker service functionality testing",
                requires_services=["temporal"]
            ),
            TestSuite(
                name="Metrics System Test",
                category="Component Tests",
                script_path="test_metrics_system.py",
                description="Metrics collection system testing",
                requires_services=[]
            ),
            TestSuite(
                name="Progress Query Test",
                category="Component Tests",
                script_path="tests/test_progress_query.py",
                description="Progress query interface testing",
                requires_services=["temporal"],
                timeout=180
            ),
            
            # Verification tests
            TestSuite(
                name="Image Generation Verification",
                category="Verification",
                script_path="final_verify.py",
                description="Verifies image generation implementation",
                requires_services=[]
            ),
            TestSuite(
                name="Image Generation Function Verification",
                category="Verification",
                script_path="verify_gen_image.py",
                description="Verifies image generation function",
                requires_services=[]
            ),
            
            # Server tests
            TestSuite(
                name="Server Startup Test",
                category="Server Tests",
                script_path="test_server.py",
                description="Tests server startup and basic endpoints",
                requires_services=[],
                timeout=120
            )
        ]
    
    async def check_service_status(self, service: str) -> bool:
        """Check if a required service is running."""
        try:
            if service == "temporal":
                # Check Temporal server
                proc = await asyncio.create_subprocess_exec(
                    "curl", "-s", "http://localhost:8233/api/v1/namespaces",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                return proc.returncode == 0
                
            elif service == "callback_server":
                # Check callback server
                proc = await asyncio.create_subprocess_exec(
                    "curl", "-s", "http://localhost:16883/health",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                return proc.returncode == 0
                
            elif service == "api_server":
                # Check API server
                proc = await asyncio.create_subprocess_exec(
                    "curl", "-s", "http://localhost:8000/health",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                return proc.returncode == 0
                
        except Exception as e:
            logger.warning(f"Failed to check {service} status: {e}")
            return False
        
        return False
    
    async def check_all_services(self):
        """Check status of all required services."""
        services = ["temporal", "callback_server", "api_server"]
        
        print("\n🔍 检查服务状态...")
        for service in services:
            status = await self.check_service_status(service)
            self.services_status[service] = status
            status_icon = "✅" if status else "❌"
            print(f"  {status_icon} {service}: {'运行中' if status else '未运行'}")
    
    async def run_test_suite(self, suite: TestSuite) -> TestResult:
        """Run a single test suite."""
        print(f"\n🧪 运行测试: {suite.name}")
        print(f"   描述: {suite.description}")
        
        # Check service dependencies
        if suite.requires_services:
            missing_services = []
            for service in suite.requires_services:
                if not self.services_status.get(service, False):
                    missing_services.append(service)
            
            if missing_services:
                error_msg = f"缺少必需的服务: {', '.join(missing_services)}"
                print(f"   ⏭️  跳过: {error_msg}")
                return TestResult(
                    name=suite.name,
                    category=suite.category,
                    status="skipped",
                    duration=0.0,
                    output="",
                    error=error_msg
                )
        
        start_time = time.time()
        script_path = self.project_root / suite.script_path
        
        if not script_path.exists():
            error_msg = f"测试脚本不存在: {script_path}"
            print(f"   ❌ 错误: {error_msg}")
            return TestResult(
                name=suite.name,
                category=suite.category,
                status="error",
                duration=0.0,
                output="",
                error=error_msg
            )
        
        try:
            # Run the test script
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(self.project_root)
            )
            
            try:
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(), 
                    timeout=suite.timeout
                )
                output = stdout.decode('utf-8', errors='replace')
                
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                error_msg = f"测试超时 ({suite.timeout}秒)"
                print(f"   ⏰ 超时: {error_msg}")
                return TestResult(
                    name=suite.name,
                    category=suite.category,
                    status="failed",
                    duration=time.time() - start_time,
                    output="",
                    error=error_msg
                )
            
            duration = time.time() - start_time
            
            # Determine test status based on return code
            if proc.returncode == 0:
                status = "passed"
                print(f"   ✅ 通过 ({duration:.2f}秒)")
            else:
                status = "failed"
                print(f"   ❌ 失败 ({duration:.2f}秒)")
            
            return TestResult(
                name=suite.name,
                category=suite.category,
                status=status,
                duration=duration,
                output=output,
                error=None if status == "passed" else f"退出码: {proc.returncode}"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"执行异常: {str(e)}"
            print(f"   💥 异常: {error_msg}")
            return TestResult(
                name=suite.name,
                category=suite.category,
                status="error",
                duration=duration,
                output="",
                error=error_msg
            )
    
    async def run_all_tests(self):
        """Run all test suites."""
        print("\n" + "="*60)
        print("🚀 开始综合测试执行")
        print("="*60)
        
        # Check service status first
        await self.check_all_services()
        
        # Group tests by category
        categories = {}
        for suite in self.test_suites:
            if suite.category not in categories:
                categories[suite.category] = []
            categories[suite.category].append(suite)
        
        # Run tests by category
        for category, suites in categories.items():
            print(f"\n📂 测试分类: {category}")
            print("-" * 40)
            
            for suite in suites:
                result = await self.run_test_suite(suite)
                self.results.append(result)
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate a summary report of all test results."""
        total_tests = len(self.results)
        passed = len([r for r in self.results if r.status == "passed"])
        failed = len([r for r in self.results if r.status == "failed"])
        skipped = len([r for r in self.results if r.status == "skipped"])
        errors = len([r for r in self.results if r.status == "error"])
        
        total_duration = sum(r.duration for r in self.results)
        
        # Group by category
        by_category = {}
        for result in self.results:
            if result.category not in by_category:
                by_category[result.category] = []
            by_category[result.category].append(result)
        
        category_summary = {}
        for category, results in by_category.items():
            category_passed = len([r for r in results if r.status == "passed"])
            category_total = len(results)
            category_summary[category] = {
                "total": category_total,
                "passed": category_passed,
                "failed": len([r for r in results if r.status == "failed"]),
                "skipped": len([r for r in results if r.status == "skipped"]),
                "errors": len([r for r in results if r.status == "error"]),
                "pass_rate": (category_passed / category_total * 100) if category_total > 0 else 0
            }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "execution_time": (datetime.now() - self.start_time).total_seconds(),
            "summary": {
                "total_tests": total_tests,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "errors": errors,
                "pass_rate": (passed / total_tests * 100) if total_tests > 0 else 0,
                "total_duration": total_duration
            },
            "by_category": category_summary,
            "services_status": self.services_status,
            "detailed_results": [asdict(r) for r in self.results]
        }
    
    def print_summary_report(self):
        """Print a formatted summary report."""
        report = self.generate_summary_report()
        summary = report["summary"]
        
        print("\n" + "="*60)
        print("📊 测试执行总结")
        print("="*60)
        
        print(f"\n⏱️  执行时间: {report['execution_time']:.2f} 秒")
        print(f"📈 总体通过率: {summary['pass_rate']:.1f}%")
        
        print(f"\n📋 测试统计:")
        print(f"   总测试数: {summary['total_tests']}")
        print(f"   ✅ 通过: {summary['passed']}")
        print(f"   ❌ 失败: {summary['failed']}")
        print(f"   ⏭️  跳过: {summary['skipped']}")
        print(f"   💥 错误: {summary['errors']}")
        
        print(f"\n🔧 服务状态:")
        for service, status in report["services_status"].items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {service}")
        
        print(f"\n📂 分类统计:")
        for category, stats in report["by_category"].items():
            print(f"   {category}: {stats['passed']}/{stats['total']} ({stats['pass_rate']:.1f}%)")
        
        # Show failed tests
        failed_tests = [r for r in self.results if r.status in ["failed", "error"]]
        if failed_tests:
            print(f"\n❌ 失败的测试:")
            for test in failed_tests:
                print(f"   • {test.name}: {test.error or 'Unknown error'}")
        
        # Show skipped tests
        skipped_tests = [r for r in self.results if r.status == "skipped"]
        if skipped_tests:
            print(f"\n⏭️  跳过的测试:")
            for test in skipped_tests:
                print(f"   • {test.name}: {test.error or 'Unknown reason'}")
    
    def save_detailed_report(self, filename: str = None):
        """Save detailed test report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"comprehensive_test_report_{timestamp}.json"
        
        report_path = self.project_root / "test_reports" / filename
        report_path.parent.mkdir(exist_ok=True)
        
        report = self.generate_summary_report()
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 详细报告已保存: {report_path}")
        return report_path


async def main():
    """Main test execution function."""
    runner = ComprehensiveTestRunner()
    
    try:
        await runner.run_all_tests()
        runner.print_summary_report()
        runner.save_detailed_report()
        
        # Exit with appropriate code
        failed_count = len([r for r in runner.results if r.status in ["failed", "error"]])
        sys.exit(1 if failed_count > 0 else 0)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n💥 测试执行异常: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())