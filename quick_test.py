#!/usr/bin/env python3
"""
Quick Test Script for Temporal Video Generation System

This script performs a quick health check and basic functionality test
to ensure the system is working correctly before running comprehensive tests.

Usage:
    python quick_test.py [--verbose] [--no-proxy]
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class QuickTester:
    """Quick test runner for basic system validation"""
    
    def __init__(self, verbose: bool = False, no_proxy: bool = False):
        self.verbose = verbose
        self.no_proxy = no_proxy
        self.results = []
        
        # Setup logging
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def _log_test_result(self, test_name: str, success: bool, message: str = "", duration: float = 0):
        """Log and store test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        log_msg = f"{status} {test_name}"
        if message:
            log_msg += f" - {message}"
        if duration > 0:
            log_msg += f" ({duration:.2f}s)"
        
        if success:
            self.logger.info(log_msg)
        else:
            self.logger.error(log_msg)
        
        self.results.append({
            'test': test_name,
            'success': success,
            'message': message,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        })
    
    def test_python_environment(self) -> bool:
        """Test Python environment and required packages"""
        start_time = time.time()
        
        try:
            # Check Python version
            if sys.version_info < (3, 8):
                self._log_test_result(
                    "Python Environment", 
                    False, 
                    f"Python 3.8+ required, found {sys.version_info.major}.{sys.version_info.minor}",
                    time.time() - start_time
                )
                return False
            
            # Check required packages
            required_packages = [
                'temporalio',
                'fastapi',
                'httpx',
                'pydantic',
                'uvicorn',
                'psutil',
                'yaml'
            ]
            
            missing_packages = []
            for package in required_packages:
                try:
                    __import__(package)
                except ImportError:
                    missing_packages.append(package)
            
            if missing_packages:
                self._log_test_result(
                    "Python Environment", 
                    False, 
                    f"Missing packages: {', '.join(missing_packages)}",
                    time.time() - start_time
                )
                return False
            
            self._log_test_result(
                "Python Environment", 
                True, 
                "All required packages available",
                time.time() - start_time
            )
            return True
            
        except Exception as e:
            self._log_test_result(
                "Python Environment", 
                False, 
                f"Error: {str(e)}",
                time.time() - start_time
            )
            return False
    
    def test_file_structure(self) -> bool:
        """Test that required files exist"""
        start_time = time.time()
        
        required_files = [
            'activities.py',
            'workflows.py',
            'models.py',
            'callback_server.py',
            'worker_service.py'
        ]
        
        optional_files = [
            'test_config.yaml',
            'run_all_tests.py',
            'comprehensive_test_plan.md'
        ]
        
        missing_required = []
        missing_optional = []
        
        for file in required_files:
            if not os.path.exists(file):
                missing_required.append(file)
        
        for file in optional_files:
            if not os.path.exists(file):
                missing_optional.append(file)
        
        if missing_required:
            self._log_test_result(
                "File Structure", 
                False, 
                f"Missing required files: {', '.join(missing_required)}",
                time.time() - start_time
            )
            return False
        
        message = "All required files present"
        if missing_optional:
            message += f" (optional files missing: {', '.join(missing_optional)})"
        
        self._log_test_result(
            "File Structure", 
            True, 
            message,
            time.time() - start_time
        )
        return True
    
    def test_temporal_connection(self) -> bool:
        """Test connection to Temporal server"""
        start_time = time.time()
        
        try:
            # Try to import and create a client
            from temporalio.client import Client
            
            async def check_temporal():
                try:
                    client = await Client.connect("localhost:7233")
                    # Try to list workflows (this will fail if server is not running)
                    await client.list_workflows()
                    return True
                except Exception as e:
                    self.logger.debug(f"Temporal connection error: {e}")
                    return False
            
            # Run the async check
            result = asyncio.run(check_temporal())
            
            if result:
                self._log_test_result(
                    "Temporal Connection", 
                    True, 
                    "Successfully connected to Temporal server",
                    time.time() - start_time
                )
                return True
            else:
                self._log_test_result(
                    "Temporal Connection", 
                    False, 
                    "Cannot connect to Temporal server (localhost:7233)",
                    time.time() - start_time
                )
                return False
                
        except Exception as e:
            self._log_test_result(
                "Temporal Connection", 
                False, 
                f"Error testing Temporal connection: {str(e)}",
                time.time() - start_time
            )
            return False
    
    async def test_callback_server(self) -> bool:
        """Test callback server functionality"""
        start_time = time.time()
        
        try:
            # Start callback server in background
            server_process = subprocess.Popen(
                ['python', 'callback_server.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait a moment for server to start
            await asyncio.sleep(3)
            
            # Test health endpoint
            client_kwargs = {}
            if self.no_proxy:
                client_kwargs['proxies'] = {}
            
            async with httpx.AsyncClient(**client_kwargs) as client:
                try:
                    response = await client.get(
                        "http://127.0.0.1:16883/health",
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        # Test callback endpoint with dummy data
                        callback_response = await client.post(
                            "http://127.0.0.1:16883/callback/kling",
                            json={
                                "user_id": "test_user",
                                "task_id": "test_task_123",
                                "status": "completed",
                                "result": {
                                    "video_url": "https://example.com/test.mp4",
                                    "duration": 10.0
                                }
                            },
                            timeout=10.0
                        )
                        
                        # Stop server
                        server_process.terminate()
                        server_process.wait(timeout=5)
                        
                        # Check if callback was processed (500 is expected for non-existent workflow)
                        if callback_response.status_code in [200, 500]:
                            self._log_test_result(
                                "Callback Server", 
                                True, 
                                f"Server responding (health: {response.status_code}, callback: {callback_response.status_code})",
                                time.time() - start_time
                            )
                            return True
                        else:
                            self._log_test_result(
                                "Callback Server", 
                                False, 
                                f"Unexpected callback response: {callback_response.status_code}",
                                time.time() - start_time
                            )
                            return False
                    else:
                        server_process.terminate()
                        self._log_test_result(
                            "Callback Server", 
                            False, 
                            f"Health check failed: {response.status_code}",
                            time.time() - start_time
                        )
                        return False
                        
                except httpx.RequestError as e:
                    server_process.terminate()
                    self._log_test_result(
                        "Callback Server", 
                        False, 
                        f"Request error: {str(e)}",
                        time.time() - start_time
                    )
                    return False
                    
        except Exception as e:
            self._log_test_result(
                "Callback Server", 
                False, 
                f"Error: {str(e)}",
                time.time() - start_time
            )
            return False
    
    def test_workflow_imports(self) -> bool:
        """Test that workflow and activity modules can be imported"""
        start_time = time.time()
        
        try:
            # Test importing main modules
            import activities
            import workflows
            import models
            
            # Check for key classes/functions
            required_items = [
                ('activities', 'gen_image'),
                ('workflows', 'GenVideoWorkflow'),
                ('models', 'VideoRequest')
            ]
            
            missing_items = []
            for module_name, item_name in required_items:
                module = sys.modules[module_name]
                if not hasattr(module, item_name):
                    missing_items.append(f"{module_name}.{item_name}")
            
            if missing_items:
                self._log_test_result(
                    "Workflow Imports", 
                    False, 
                    f"Missing items: {', '.join(missing_items)}",
                    time.time() - start_time
                )
                return False
            
            self._log_test_result(
                "Workflow Imports", 
                True, 
                "All workflow modules imported successfully",
                time.time() - start_time
            )
            return True
            
        except ImportError as e:
            self._log_test_result(
                "Workflow Imports", 
                False, 
                f"Import error: {str(e)}",
                time.time() - start_time
            )
            return False
        except Exception as e:
            self._log_test_result(
                "Workflow Imports", 
                False, 
                f"Error: {str(e)}",
                time.time() - start_time
            )
            return False
    
    def test_configuration(self) -> bool:
        """Test configuration files and environment"""
        start_time = time.time()
        
        try:
            issues = []
            
            # Check for environment variables
            env_vars = [
                'KLING_API_KEY',
                'COMFYUI_API_URL'
            ]
            
            missing_env = []
            for var in env_vars:
                if not os.getenv(var):
                    missing_env.append(var)
            
            if missing_env:
                issues.append(f"Missing environment variables: {', '.join(missing_env)}")
            
            # Check test config if it exists
            if os.path.exists('test_config.yaml'):
                try:
                    import yaml
                    with open('test_config.yaml', 'r') as f:
                        config = yaml.safe_load(f)
                    
                    # Basic validation
                    if not isinstance(config, dict):
                        issues.append("Invalid test_config.yaml format")
                    elif 'global' not in config:
                        issues.append("Missing 'global' section in test_config.yaml")
                        
                except Exception as e:
                    issues.append(f"Error reading test_config.yaml: {str(e)}")
            
            if issues:
                self._log_test_result(
                    "Configuration", 
                    False, 
                    "; ".join(issues),
                    time.time() - start_time
                )
                return False
            
            message = "Configuration looks good"
            if missing_env:
                message += " (some optional env vars missing)"
            
            self._log_test_result(
                "Configuration", 
                True, 
                message,
                time.time() - start_time
            )
            return True
            
        except Exception as e:
            self._log_test_result(
                "Configuration", 
                False, 
                f"Error: {str(e)}",
                time.time() - start_time
            )
            return False
    
    async def run_all_tests(self) -> Dict:
        """Run all quick tests"""
        self.logger.info("Starting quick system validation...")
        start_time = time.time()
        
        # Run tests in order
        tests = [
            ("Python Environment", self.test_python_environment),
            ("File Structure", self.test_file_structure),
            ("Workflow Imports", self.test_workflow_imports),
            ("Configuration", self.test_configuration),
            ("Temporal Connection", self.test_temporal_connection),
            ("Callback Server", self.test_callback_server)
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                if asyncio.iscoroutinefunction(test_func):
                    result = await test_func()
                else:
                    result = test_func()
                
                if result:
                    passed += 1
                else:
                    failed += 1
                    
            except Exception as e:
                self.logger.error(f"Test {test_name} crashed: {e}")
                failed += 1
                self._log_test_result(test_name, False, f"Test crashed: {str(e)}")
        
        total_time = time.time() - start_time
        
        # Generate summary
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_tests': len(tests),
            'passed': passed,
            'failed': failed,
            'success_rate': (passed / len(tests)) * 100,
            'duration': total_time,
            'results': self.results
        }
        
        # Print summary
        print("\n" + "="*50)
        print("QUICK TEST SUMMARY")
        print("="*50)
        print(f"Tests Run: {len(tests)}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Duration: {total_time:.2f}s")
        
        if failed == 0:
            print("\n🎉 All quick tests passed! System appears to be ready.")
            print("\n💡 Next steps:")
            print("   - Run comprehensive tests: python run_all_tests.py")
            print("   - Start Temporal server if not running")
            print("   - Check environment variables for external services")
        else:
            print("\n⚠️  Some tests failed. Please address the issues before running comprehensive tests.")
            print("\n🔧 Common fixes:")
            print("   - Install missing Python packages: pip install -r requirements.txt")
            print("   - Start Temporal server: temporal server start-dev")
            print("   - Set environment variables for external APIs")
        
        # Save results
        with open('quick_test_results.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        return summary


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Quick Test for Temporal Video Generation System')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--no-proxy', action='store_true', help='Disable proxy for HTTP requests')
    
    args = parser.parse_args()
    
    tester = QuickTester(verbose=args.verbose, no_proxy=args.no_proxy)
    
    try:
        summary = asyncio.run(tester.run_all_tests())
        
        # Exit with appropriate code
        if summary['failed'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n❌ Quick test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Quick test failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()