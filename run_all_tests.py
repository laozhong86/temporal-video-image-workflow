#!/usr/bin/env python3
"""
Comprehensive Test Runner for Temporal Video Generation System

This script orchestrates the execution of all test suites and generates
comprehensive reports with metrics, analysis, and recommendations.

Usage:
    python run_all_tests.py [options]
    
Options:
    --config: Path to test configuration file (default: test_config.yaml)
    --suite: Specific test suite to run (unit, integration, performance, security, e2e, all)
    --parallel: Run tests in parallel (default: True)
    --report: Generate reports (default: True)
    --verbose: Verbose output (default: False)
    --dry-run: Show what would be executed without running tests
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import psutil


@dataclass
class TestResult:
    """Test result data structure"""
    suite: str
    test_name: str
    status: str  # passed, failed, skipped, error
    duration: float
    error_message: Optional[str] = None
    output: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


@dataclass
class TestSuiteResult:
    """Test suite result data structure"""
    suite_name: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    coverage: Optional[float] = None
    results: List[TestResult] = None


@dataclass
class SystemMetrics:
    """System metrics during test execution"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    network_io: Dict[str, int]


class TestRunner:
    """Main test runner class"""
    
    def __init__(self, config_path: str = "test_config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.results: List[TestSuiteResult] = []
        self.system_metrics: List[SystemMetrics] = []
        self.start_time = None
        self.end_time = None
        
        # Setup logging
        self._setup_logging()
        
        # Create output directories
        self._create_output_dirs()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load test configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Warning: Config file {self.config_path} not found. Using defaults.")
            return self._get_default_config()
        except yaml.YAMLError as e:
            print(f"Error parsing config file: {e}")
            sys.exit(1)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if config file is not found"""
        return {
            'global': {
                'test_timeout': 300,
                'retry_attempts': 3,
                'parallel_execution': True,
                'generate_reports': True,
                'log_level': 'INFO'
            },
            'unit_tests': {'enabled': True},
            'integration_tests': {'enabled': True},
            'performance_tests': {'enabled': True},
            'security_tests': {'enabled': True},
            'e2e_tests': {'enabled': True}
        }
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = self.config.get('global', {}).get('log_level', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('test_execution.log')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _create_output_dirs(self):
        """Create output directories for test results"""
        output_dir = Path(self.config.get('environment', {}).get('output_dir', './test_results'))
        output_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (output_dir / 'reports').mkdir(exist_ok=True)
        (output_dir / 'logs').mkdir(exist_ok=True)
        (output_dir / 'metrics').mkdir(exist_ok=True)
        (output_dir / 'artifacts').mkdir(exist_ok=True)
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                disk_usage_percent=disk.percent,
                network_io={
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                }
            )
        except Exception as e:
            self.logger.warning(f"Failed to collect system metrics: {e}")
            return None
    
    async def _monitor_system_metrics(self, interval: int = 5):
        """Monitor system metrics during test execution"""
        while self.start_time and not self.end_time:
            metrics = self._collect_system_metrics()
            if metrics:
                self.system_metrics.append(metrics)
            await asyncio.sleep(interval)
    
    def _run_test_command(self, command: List[str], timeout: int = 300) -> Tuple[int, str, str]:
        """Run a test command and return exit code, stdout, stderr"""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd()
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Test timed out after {timeout} seconds"
        except Exception as e:
            return -1, "", f"Error running test: {str(e)}"
    
    def _run_unit_tests(self) -> TestSuiteResult:
        """Run unit tests"""
        self.logger.info("Running unit tests...")
        start_time = time.time()
        
        # Run pytest with coverage
        command = [
            'python', '-m', 'pytest',
            'test_unit_comprehensive.py',
            '-v',
            '--tb=short',
            '--cov=.',
            '--cov-report=json',
            '--json-report',
            '--json-report-file=test_results/unit_test_report.json'
        ]
        
        exit_code, stdout, stderr = self._run_test_command(command)
        duration = time.time() - start_time
        
        # Parse results
        try:
            with open('test_results/unit_test_report.json', 'r') as f:
                report = json.load(f)
            
            # Parse coverage
            coverage = None
            try:
                with open('coverage.json', 'r') as f:
                    cov_data = json.load(f)
                    coverage = cov_data.get('totals', {}).get('percent_covered', 0)
            except FileNotFoundError:
                pass
            
            return TestSuiteResult(
                suite_name="unit",
                total_tests=report['summary']['total'],
                passed=report['summary']['passed'],
                failed=report['summary']['failed'],
                skipped=report['summary']['skipped'],
                errors=report['summary']['error'],
                duration=duration,
                coverage=coverage
            )
        except Exception as e:
            self.logger.error(f"Failed to parse unit test results: {e}")
            return TestSuiteResult(
                suite_name="unit",
                total_tests=0,
                passed=0,
                failed=1,
                skipped=0,
                errors=1,
                duration=duration
            )
    
    def _run_integration_tests(self) -> TestSuiteResult:
        """Run integration tests"""
        self.logger.info("Running integration tests...")
        start_time = time.time()
        
        command = [
            'python', '-m', 'pytest',
            'test_integration_comprehensive.py',
            '-v',
            '--tb=short',
            '--json-report',
            '--json-report-file=test_results/integration_test_report.json'
        ]
        
        exit_code, stdout, stderr = self._run_test_command(command, timeout=600)
        duration = time.time() - start_time
        
        # Parse results (similar to unit tests)
        try:
            with open('test_results/integration_test_report.json', 'r') as f:
                report = json.load(f)
            
            return TestSuiteResult(
                suite_name="integration",
                total_tests=report['summary']['total'],
                passed=report['summary']['passed'],
                failed=report['summary']['failed'],
                skipped=report['summary']['skipped'],
                errors=report['summary']['error'],
                duration=duration
            )
        except Exception as e:
            self.logger.error(f"Failed to parse integration test results: {e}")
            return TestSuiteResult(
                suite_name="integration",
                total_tests=0,
                passed=0,
                failed=1,
                skipped=0,
                errors=1,
                duration=duration
            )
    
    def _run_performance_tests(self) -> TestSuiteResult:
        """Run performance tests"""
        self.logger.info("Running performance tests...")
        start_time = time.time()
        
        command = [
            'python', 'test_performance_stress.py',
            '--mode=performance',
            '--output=test_results/performance_results.json'
        ]
        
        exit_code, stdout, stderr = self._run_test_command(command, timeout=900)
        duration = time.time() - start_time
        
        # Parse performance results
        passed = 1 if exit_code == 0 else 0
        failed = 0 if exit_code == 0 else 1
        
        return TestSuiteResult(
            suite_name="performance",
            total_tests=1,
            passed=passed,
            failed=failed,
            skipped=0,
            errors=0,
            duration=duration
        )
    
    def _run_security_tests(self) -> TestSuiteResult:
        """Run security tests"""
        self.logger.info("Running security tests...")
        start_time = time.time()
        
        command = [
            'python', '-m', 'pytest',
            'test_security_comprehensive.py',
            '-v',
            '--tb=short',
            '--json-report',
            '--json-report-file=test_results/security_test_report.json'
        ]
        
        exit_code, stdout, stderr = self._run_test_command(command)
        duration = time.time() - start_time
        
        # Parse results
        try:
            with open('test_results/security_test_report.json', 'r') as f:
                report = json.load(f)
            
            return TestSuiteResult(
                suite_name="security",
                total_tests=report['summary']['total'],
                passed=report['summary']['passed'],
                failed=report['summary']['failed'],
                skipped=report['summary']['skipped'],
                errors=report['summary']['error'],
                duration=duration
            )
        except Exception as e:
            self.logger.error(f"Failed to parse security test results: {e}")
            return TestSuiteResult(
                suite_name="security",
                total_tests=0,
                passed=0,
                failed=1,
                skipped=0,
                errors=1,
                duration=duration
            )
    
    def _run_e2e_tests(self) -> TestSuiteResult:
        """Run end-to-end tests"""
        self.logger.info("Running end-to-end tests...")
        start_time = time.time()
        
        # Run existing test files
        test_files = [
            'test_gen_video_workflow.py',
            'test_simple_workflow.py',
            'final_verify.py'
        ]
        
        total_tests = len(test_files)
        passed = 0
        failed = 0
        
        for test_file in test_files:
            if os.path.exists(test_file):
                command = ['python', test_file]
                exit_code, stdout, stderr = self._run_test_command(command, timeout=600)
                if exit_code == 0:
                    passed += 1
                else:
                    failed += 1
            else:
                self.logger.warning(f"Test file {test_file} not found")
                failed += 1
        
        duration = time.time() - start_time
        
        return TestSuiteResult(
            suite_name="e2e",
            total_tests=total_tests,
            passed=passed,
            failed=failed,
            skipped=0,
            errors=0,
            duration=duration
        )
    
    def _generate_summary_report(self) -> Dict[str, Any]:
        """Generate comprehensive test summary report"""
        total_duration = (self.end_time - self.start_time).total_seconds()
        
        # Calculate overall statistics
        total_tests = sum(result.total_tests for result in self.results)
        total_passed = sum(result.passed for result in self.results)
        total_failed = sum(result.failed for result in self.results)
        total_skipped = sum(result.skipped for result in self.results)
        total_errors = sum(result.errors for result in self.results)
        
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        # System metrics summary
        metrics_summary = {}
        if self.system_metrics:
            metrics_summary = {
                'avg_cpu_percent': sum(m.cpu_percent for m in self.system_metrics) / len(self.system_metrics),
                'max_cpu_percent': max(m.cpu_percent for m in self.system_metrics),
                'avg_memory_percent': sum(m.memory_percent for m in self.system_metrics) / len(self.system_metrics),
                'max_memory_percent': max(m.memory_percent for m in self.system_metrics),
                'avg_memory_used_mb': sum(m.memory_used_mb for m in self.system_metrics) / len(self.system_metrics),
                'max_memory_used_mb': max(m.memory_used_mb for m in self.system_metrics)
            }
        
        return {
            'execution_info': {
                'start_time': self.start_time.isoformat(),
                'end_time': self.end_time.isoformat(),
                'total_duration_seconds': total_duration,
                'config_file': self.config_path
            },
            'overall_summary': {
                'total_tests': total_tests,
                'passed': total_passed,
                'failed': total_failed,
                'skipped': total_skipped,
                'errors': total_errors,
                'success_rate_percent': round(success_rate, 2)
            },
            'suite_results': [asdict(result) for result in self.results],
            'system_metrics': metrics_summary,
            'recommendations': self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check overall success rate
        total_tests = sum(result.total_tests for result in self.results)
        total_passed = sum(result.passed for result in self.results)
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        if success_rate < 95:
            recommendations.append("Overall test success rate is below 95%. Review failed tests and improve code quality.")
        
        # Check individual suites
        for result in self.results:
            suite_success_rate = (result.passed / result.total_tests * 100) if result.total_tests > 0 else 0
            
            if suite_success_rate < 90:
                recommendations.append(f"{result.suite_name} test suite has low success rate ({suite_success_rate:.1f}%). Focus on improving this area.")
            
            if result.duration > 300:  # 5 minutes
                recommendations.append(f"{result.suite_name} test suite takes too long ({result.duration:.1f}s). Consider optimizing test execution.")
        
        # Check coverage
        unit_result = next((r for r in self.results if r.suite_name == 'unit'), None)
        if unit_result and unit_result.coverage and unit_result.coverage < 80:
            recommendations.append(f"Code coverage is below 80% ({unit_result.coverage:.1f}%). Add more unit tests.")
        
        # Check system metrics
        if self.system_metrics:
            max_cpu = max(m.cpu_percent for m in self.system_metrics)
            max_memory = max(m.memory_percent for m in self.system_metrics)
            
            if max_cpu > 90:
                recommendations.append(f"High CPU usage detected ({max_cpu:.1f}%). Consider optimizing performance-critical code.")
            
            if max_memory > 90:
                recommendations.append(f"High memory usage detected ({max_memory:.1f}%). Check for memory leaks or optimize memory usage.")
        
        if not recommendations:
            recommendations.append("All tests are performing well! Consider adding more comprehensive test scenarios.")
        
        return recommendations
    
    def _save_reports(self, summary: Dict[str, Any]):
        """Save test reports in multiple formats"""
        output_dir = Path('test_results/reports')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # JSON report
        json_file = output_dir / f'test_report_{timestamp}.json'
        with open(json_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        # Markdown report
        md_file = output_dir / f'test_report_{timestamp}.md'
        self._generate_markdown_report(summary, md_file)
        
        # HTML report (basic)
        html_file = output_dir / f'test_report_{timestamp}.html'
        self._generate_html_report(summary, html_file)
        
        self.logger.info(f"Reports saved to {output_dir}")
    
    def _generate_markdown_report(self, summary: Dict[str, Any], output_file: Path):
        """Generate markdown test report"""
        with open(output_file, 'w') as f:
            f.write("# Temporal Video Generation System - Test Report\n\n")
            
            # Execution info
            exec_info = summary['execution_info']
            f.write(f"**Execution Time:** {exec_info['start_time']} - {exec_info['end_time']}\n")
            f.write(f"**Total Duration:** {exec_info['total_duration_seconds']:.2f} seconds\n\n")
            
            # Overall summary
            overall = summary['overall_summary']
            f.write("## Overall Summary\n\n")
            f.write(f"- **Total Tests:** {overall['total_tests']}\n")
            f.write(f"- **Passed:** {overall['passed']} ✅\n")
            f.write(f"- **Failed:** {overall['failed']} ❌\n")
            f.write(f"- **Skipped:** {overall['skipped']} ⏭️\n")
            f.write(f"- **Errors:** {overall['errors']} 🚨\n")
            f.write(f"- **Success Rate:** {overall['success_rate_percent']}%\n\n")
            
            # Suite results
            f.write("## Test Suite Results\n\n")
            for suite in summary['suite_results']:
                f.write(f"### {suite['suite_name'].title()} Tests\n\n")
                f.write(f"- **Duration:** {suite['duration']:.2f}s\n")
                f.write(f"- **Tests:** {suite['total_tests']}\n")
                f.write(f"- **Passed:** {suite['passed']}\n")
                f.write(f"- **Failed:** {suite['failed']}\n")
                if suite.get('coverage'):
                    f.write(f"- **Coverage:** {suite['coverage']:.1f}%\n")
                f.write("\n")
            
            # Recommendations
            f.write("## Recommendations\n\n")
            for rec in summary['recommendations']:
                f.write(f"- {rec}\n")
    
    def _generate_html_report(self, summary: Dict[str, Any], output_file: Path):
        """Generate basic HTML test report"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Test Report - Temporal Video Generation System</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .summary {{ background: #f5f5f5; padding: 20px; border-radius: 5px; }}
        .suite {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .passed {{ color: green; }}
        .failed {{ color: red; }}
        .skipped {{ color: orange; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Temporal Video Generation System - Test Report</h1>
    
    <div class="summary">
        <h2>Overall Summary</h2>
        <p><strong>Success Rate:</strong> {summary['overall_summary']['success_rate_percent']}%</p>
        <p><strong>Total Tests:</strong> {summary['overall_summary']['total_tests']}</p>
        <p><strong>Duration:</strong> {summary['execution_info']['total_duration_seconds']:.2f} seconds</p>
    </div>
    
    <h2>Test Suite Results</h2>
    <table>
        <tr>
            <th>Suite</th>
            <th>Total</th>
            <th>Passed</th>
            <th>Failed</th>
            <th>Skipped</th>
            <th>Duration (s)</th>
            <th>Coverage</th>
        </tr>
"""
        
        for suite in summary['suite_results']:
            coverage = f"{suite.get('coverage', 0):.1f}%" if suite.get('coverage') else "N/A"
            html_content += f"""
        <tr>
            <td>{suite['suite_name'].title()}</td>
            <td>{suite['total_tests']}</td>
            <td class="passed">{suite['passed']}</td>
            <td class="failed">{suite['failed']}</td>
            <td class="skipped">{suite['skipped']}</td>
            <td>{suite['duration']:.2f}</td>
            <td>{coverage}</td>
        </tr>
"""
        
        html_content += """
    </table>
    
    <h2>Recommendations</h2>
    <ul>
"""
        
        for rec in summary['recommendations']:
            html_content += f"        <li>{rec}</li>\n"
        
        html_content += """
    </ul>
</body>
</html>
"""
        
        with open(output_file, 'w') as f:
            f.write(html_content)
    
    async def run_all_tests(self, suites: List[str] = None, parallel: bool = True) -> Dict[str, Any]:
        """Run all specified test suites"""
        if suites is None:
            suites = ['unit', 'integration', 'performance', 'security', 'e2e']
        
        self.start_time = datetime.now()
        self.logger.info(f"Starting test execution at {self.start_time}")
        
        # Start system monitoring
        monitor_task = asyncio.create_task(self._monitor_system_metrics())
        
        try:
            if parallel and len(suites) > 1:
                # Run tests in parallel
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = []
                    
                    for suite in suites:
                        if suite == 'unit' and self.config.get('unit_tests', {}).get('enabled', True):
                            futures.append(executor.submit(self._run_unit_tests))
                        elif suite == 'integration' and self.config.get('integration_tests', {}).get('enabled', True):
                            futures.append(executor.submit(self._run_integration_tests))
                        elif suite == 'performance' and self.config.get('performance_tests', {}).get('enabled', True):
                            futures.append(executor.submit(self._run_performance_tests))
                        elif suite == 'security' and self.config.get('security_tests', {}).get('enabled', True):
                            futures.append(executor.submit(self._run_security_tests))
                        elif suite == 'e2e' and self.config.get('e2e_tests', {}).get('enabled', True):
                            futures.append(executor.submit(self._run_e2e_tests))
                    
                    for future in as_completed(futures):
                        try:
                            result = future.result()
                            self.results.append(result)
                            self.logger.info(f"Completed {result.suite_name} tests: {result.passed}/{result.total_tests} passed")
                        except Exception as e:
                            self.logger.error(f"Test suite failed with exception: {e}")
            else:
                # Run tests sequentially
                for suite in suites:
                    try:
                        if suite == 'unit' and self.config.get('unit_tests', {}).get('enabled', True):
                            result = self._run_unit_tests()
                        elif suite == 'integration' and self.config.get('integration_tests', {}).get('enabled', True):
                            result = self._run_integration_tests()
                        elif suite == 'performance' and self.config.get('performance_tests', {}).get('enabled', True):
                            result = self._run_performance_tests()
                        elif suite == 'security' and self.config.get('security_tests', {}).get('enabled', True):
                            result = self._run_security_tests()
                        elif suite == 'e2e' and self.config.get('e2e_tests', {}).get('enabled', True):
                            result = self._run_e2e_tests()
                        else:
                            continue
                        
                        self.results.append(result)
                        self.logger.info(f"Completed {result.suite_name} tests: {result.passed}/{result.total_tests} passed")
                    except Exception as e:
                        self.logger.error(f"Test suite {suite} failed with exception: {e}")
        
        finally:
            self.end_time = datetime.now()
            monitor_task.cancel()
        
        # Generate and save reports
        summary = self._generate_summary_report()
        
        if self.config.get('global', {}).get('generate_reports', True):
            self._save_reports(summary)
        
        self.logger.info(f"Test execution completed at {self.end_time}")
        return summary


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Comprehensive Test Runner for Temporal Video Generation System')
    parser.add_argument('--config', default='test_config.yaml', help='Path to test configuration file')
    parser.add_argument('--suite', choices=['unit', 'integration', 'performance', 'security', 'e2e', 'all'], 
                       default='all', help='Specific test suite to run')
    parser.add_argument('--parallel', action='store_true', default=True, help='Run tests in parallel')
    parser.add_argument('--no-parallel', dest='parallel', action='store_false', help='Run tests sequentially')
    parser.add_argument('--no-report', dest='report', action='store_false', default=True, help='Skip report generation')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be executed without running tests')
    
    args = parser.parse_args()
    
    # Determine which suites to run
    if args.suite == 'all':
        suites = ['unit', 'integration', 'performance', 'security', 'e2e']
    else:
        suites = [args.suite]
    
    if args.dry_run:
        print(f"Would run test suites: {', '.join(suites)}")
        print(f"Parallel execution: {args.parallel}")
        print(f"Generate reports: {args.report}")
        print(f"Config file: {args.config}")
        return
    
    # Create and run test runner
    runner = TestRunner(args.config)
    
    try:
        summary = asyncio.run(runner.run_all_tests(suites, args.parallel))
        
        # Print summary
        print("\n" + "="*60)
        print("TEST EXECUTION SUMMARY")
        print("="*60)
        print(f"Total Tests: {summary['overall_summary']['total_tests']}")
        print(f"Passed: {summary['overall_summary']['passed']}")
        print(f"Failed: {summary['overall_summary']['failed']}")
        print(f"Success Rate: {summary['overall_summary']['success_rate_percent']}%")
        print(f"Duration: {summary['execution_info']['total_duration_seconds']:.2f}s")
        
        if summary['overall_summary']['failed'] > 0:
            print("\n⚠️  Some tests failed. Check the detailed reports for more information.")
            sys.exit(1)
        else:
            print("\n✅ All tests passed successfully!")
            
    except KeyboardInterrupt:
        print("\n❌ Test execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()