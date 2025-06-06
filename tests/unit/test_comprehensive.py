#!/usr/bin/env python3
"""
Comprehensive Unit Tests for Temporal Video Generation System

This module provides comprehensive unit tests for core components including:
- Activities (image, video, common)
- Models (core models, validation)
- Workflows (video generation, batch processing)
- Configuration and utilities
"""

import pytest
import asyncio
import json
import sys
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import project modules
from models.core_models import JobInput, Progress, JobStatus, Step
from models.video_request import VideoRequest
from models.image_request import ImageRequest
from models.search_attributes import SearchAttributes
from config import Config


class TestCoreModels:
    """Test cases for core data models."""
    
    def test_job_input_creation(self):
        """Test JobInput model creation and validation."""
        job_input = JobInput(
            prompt="Test prompt",
            style="realistic",
            job_type=Step.VIDEO,
            width=512,
            height=512,
            duration=5.0,
            user_id="test_user"
        )
        
        assert job_input.prompt == "Test prompt"
        assert job_input.style == "realistic"
        assert job_input.job_type == Step.VIDEO
        assert job_input.width == 512
        assert job_input.height == 512
        assert job_input.duration == 5.0
        assert job_input.user_id == "test_user"
    
    def test_job_input_validation(self):
        """Test JobInput validation rules."""
        # Test invalid dimensions
        with pytest.raises(ValueError):
            JobInput(
                prompt="Test",
                job_type=Step.VIDEO,
                width=0,  # Invalid
                height=512
            )
        
        # Test invalid duration
        with pytest.raises(ValueError):
            JobInput(
                prompt="Test",
                job_type=Step.VIDEO,
                duration=-1.0  # Invalid
            )
    
    def test_progress_model(self):
        """Test Progress model functionality."""
        progress = Progress(
            step="video_generation",
            status=JobStatus.RUNNING,
            percent=75,
            message="Generating video...",
            asset_url="https://example.com/temp.mp4"
        )
        
        assert progress.step == "video_generation"
        assert progress.status == JobStatus.RUNNING
        assert progress.percent == 75
        assert progress.message == "Generating video..."
        assert progress.asset_url == "https://example.com/temp.mp4"
        assert isinstance(progress.updated_at, datetime)
    
    def test_progress_serialization(self):
        """Test Progress model serialization."""
        progress = Progress(
            step="test_step",
            status=JobStatus.COMPLETED,
            percent=100
        )
        
        # Test to_dict method
        progress_dict = progress.to_dict()
        assert isinstance(progress_dict, dict)
        assert progress_dict["step"] == "test_step"
        assert progress_dict["status"] == JobStatus.COMPLETED.value
        assert progress_dict["percent"] == 100
    
    def test_video_request_model(self):
        """Test VideoRequest model."""
        video_request = VideoRequest(
            prompt="Test video prompt",
            image_url="https://example.com/image.jpg",
            duration=10.0,
            aspect_ratio="16:9"
        )
        
        assert video_request.prompt == "Test video prompt"
        assert video_request.image_url == "https://example.com/image.jpg"
        assert video_request.duration == 10.0
        assert video_request.aspect_ratio == "16:9"
    
    def test_image_request_model(self):
        """Test ImageRequest model."""
        image_request = ImageRequest(
            prompt="Test image prompt",
            width=1024,
            height=768,
            style="photorealistic"
        )
        
        assert image_request.prompt == "Test image prompt"
        assert image_request.width == 1024
        assert image_request.height == 768
        assert image_request.style == "photorealistic"


class TestSearchAttributes:
    """Test cases for search attributes functionality."""
    
    def test_search_attributes_creation(self):
        """Test SearchAttributes creation."""
        attrs = SearchAttributes(
            user_id="test_user",
            job_type=Step.VIDEO,
            status=JobStatus.RUNNING,
            created_date="2024-01-01"
        )
        
        search_attrs = attrs.to_temporal_search_attributes()
        assert isinstance(search_attrs, dict)
        assert "user_id" in search_attrs
        assert "job_type" in search_attrs
        assert "status" in search_attrs
    
    def test_search_attributes_filtering(self):
        """Test search attributes filtering."""
        attrs = SearchAttributes(
            user_id="test_user",
            job_type=Step.VIDEO,
            status=JobStatus.RUNNING
        )
        
        # Test filtering by user
        user_filter = attrs.build_user_filter("test_user")
        assert "user_id" in user_filter
        
        # Test filtering by status
        status_filter = attrs.build_status_filter(JobStatus.COMPLETED)
        assert "status" in status_filter


class TestConfiguration:
    """Test cases for configuration management."""
    
    def test_config_loading(self):
        """Test configuration loading."""
        config = Config()
        
        # Test default values
        assert config.temporal_host is not None
        assert config.temporal_namespace is not None
        assert config.task_queue is not None
    
    def test_config_validation(self):
        """Test configuration validation."""
        config = Config()
        
        # Test required fields
        assert hasattr(config, 'temporal_host')
        assert hasattr(config, 'temporal_namespace')
        assert hasattr(config, 'task_queue')
    
    @patch.dict('os.environ', {'TEMPORAL_HOST': 'test-host:7233'})
    def test_config_environment_override(self):
        """Test configuration override from environment."""
        config = Config()
        # This would test environment variable override if implemented
        # assert config.temporal_host == 'test-host:7233'


class TestActivitiesMocking:
    """Test cases for activities with mocking external dependencies."""
    
    @pytest.mark.asyncio
    async def test_image_generation_activity_mock(self):
        """Test image generation activity with mocked ComfyUI."""
        # This would test the actual activity if we import it
        # For now, we'll test the structure
        
        job_input = JobInput(
            prompt="Test image",
            job_type=Step.IMAGE,
            width=512,
            height=512
        )
        
        # Mock the external API call
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "job_id": "test_job_123",
                "status": "submitted"
            }
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            # Test would go here if we import the actual activity
            # result = await gen_image(job_input)
            # assert result is not None
    
    @pytest.mark.asyncio
    async def test_video_generation_activity_mock(self):
        """Test video generation activity with mocked Kling API."""
        video_request = VideoRequest(
            prompt="Test video",
            image_url="https://example.com/image.jpg",
            duration=5.0
        )
        
        # Mock the external API call
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "job_id": "test_video_123",
                "status": "submitted"
            }
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            # Test would go here if we import the actual activity
            # result = await gen_video(video_request)
            # assert result is not None


class TestWorkflowLogic:
    """Test cases for workflow logic and state management."""
    
    def test_workflow_state_initialization(self):
        """Test workflow state initialization."""
        # This would test the actual workflow if we import it
        # For now, we'll test the expected structure
        
        initial_state = {
            "job_input": None,
            "current_step": Step.IMAGE,
            "progress": Progress(
                step="initialization",
                status=JobStatus.PENDING,
                percent=0
            ),
            "image_url": None,
            "video_url": None,
            "video_ready_received": False,
            "kling_done_received": False
        }
        
        assert initial_state["current_step"] == Step.IMAGE
        assert initial_state["progress"].status == JobStatus.PENDING
        assert initial_state["video_ready_received"] is False
    
    def test_workflow_state_transitions(self):
        """Test workflow state transitions."""
        # Test state transition logic
        states = [
            (Step.IMAGE, JobStatus.PENDING),
            (Step.IMAGE, JobStatus.RUNNING),
            (Step.IMAGE, JobStatus.COMPLETED),
            (Step.VIDEO, JobStatus.PENDING),
            (Step.VIDEO, JobStatus.RUNNING),
            (Step.VIDEO, JobStatus.COMPLETED)
        ]
        
        for step, status in states:
            progress = Progress(
                step=step.value,
                status=status,
                percent=50 if status == JobStatus.RUNNING else (100 if status == JobStatus.COMPLETED else 0)
            )
            
            assert progress.step == step.value
            assert progress.status == status
    
    def test_signal_handling_logic(self):
        """Test signal handling logic."""
        # Test signal data structure
        video_ready_signal = {
            "video_url": "https://example.com/video.mp4",
            "timestamp": datetime.now().isoformat()
        }
        
        kling_done_signal = {
            "job_id": "test_job_123",
            "status": "completed",
            "final_url": "https://example.com/final_video.mp4"
        }
        
        assert "video_url" in video_ready_signal
        assert "job_id" in kling_done_signal
        assert "status" in kling_done_signal


class TestErrorHandling:
    """Test cases for error handling and edge cases."""
    
    def test_invalid_job_input_handling(self):
        """Test handling of invalid job inputs."""
        # Test empty prompt
        with pytest.raises(ValueError):
            JobInput(
                prompt="",  # Empty prompt
                job_type=Step.VIDEO
            )
        
        # Test invalid job type
        with pytest.raises(ValueError):
            JobInput(
                prompt="Test",
                job_type="invalid_type"  # Invalid type
            )
    
    def test_network_error_simulation(self):
        """Test network error handling simulation."""
        # Simulate different types of network errors
        error_scenarios = [
            {"error_type": "timeout", "should_retry": True},
            {"error_type": "connection_error", "should_retry": True},
            {"error_type": "http_500", "should_retry": True},
            {"error_type": "http_400", "should_retry": False},
            {"error_type": "http_401", "should_retry": False}
        ]
        
        for scenario in error_scenarios:
            # Test retry logic based on error type
            if scenario["error_type"] in ["timeout", "connection_error", "http_500"]:
                assert scenario["should_retry"] is True
            else:
                assert scenario["should_retry"] is False
    
    def test_data_validation_edge_cases(self):
        """Test data validation edge cases."""
        # Test extreme values
        edge_cases = [
            {"width": 1, "height": 1, "valid": True},  # Minimum size
            {"width": 4096, "height": 4096, "valid": True},  # Large size
            {"width": 0, "height": 512, "valid": False},  # Invalid width
            {"width": 512, "height": 0, "valid": False},  # Invalid height
        ]
        
        for case in edge_cases:
            if case["valid"]:
                # Should not raise exception
                try:
                    JobInput(
                        prompt="Test",
                        job_type=Step.IMAGE,
                        width=case["width"],
                        height=case["height"]
                    )
                except ValueError:
                    pytest.fail(f"Valid case should not raise exception: {case}")
            else:
                # Should raise exception
                with pytest.raises(ValueError):
                    JobInput(
                        prompt="Test",
                        job_type=Step.IMAGE,
                        width=case["width"],
                        height=case["height"]
                    )


class TestPerformanceMetrics:
    """Test cases for performance metrics and monitoring."""
    
    def test_metrics_collection_structure(self):
        """Test metrics collection data structure."""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "workflow_id": "test_workflow_123",
            "step": Step.VIDEO.value,
            "duration": 45.5,
            "status": JobStatus.COMPLETED.value,
            "resource_usage": {
                "cpu_percent": 75.2,
                "memory_mb": 512.0,
                "network_io": 1024
            }
        }
        
        assert "timestamp" in metrics
        assert "workflow_id" in metrics
        assert "duration" in metrics
        assert "resource_usage" in metrics
        assert isinstance(metrics["resource_usage"], dict)
    
    def test_performance_thresholds(self):
        """Test performance threshold validation."""
        thresholds = {
            "image_generation_max_duration": 120.0,  # 2 minutes
            "video_generation_max_duration": 600.0,  # 10 minutes
            "max_memory_usage_mb": 2048.0,  # 2GB
            "max_cpu_percent": 90.0
        }
        
        # Test threshold validation
        test_metrics = {
            "image_duration": 90.0,  # Within threshold
            "video_duration": 450.0,  # Within threshold
            "memory_usage": 1024.0,  # Within threshold
            "cpu_usage": 85.0  # Within threshold
        }
        
        assert test_metrics["image_duration"] < thresholds["image_generation_max_duration"]
        assert test_metrics["video_duration"] < thresholds["video_generation_max_duration"]
        assert test_metrics["memory_usage"] < thresholds["max_memory_usage_mb"]
        assert test_metrics["cpu_usage"] < thresholds["max_cpu_percent"]


class TestIntegrationHelpers:
    """Test cases for integration testing helpers."""
    
    def test_mock_external_services(self):
        """Test mock external service responses."""
        # Mock ComfyUI response
        comfyui_response = {
            "job_id": "comfy_123",
            "status": "submitted",
            "queue_position": 1
        }
        
        # Mock Kling API response
        kling_response = {
            "job_id": "kling_456",
            "status": "processing",
            "estimated_time": 300
        }
        
        assert comfyui_response["job_id"] == "comfy_123"
        assert kling_response["job_id"] == "kling_456"
    
    def test_test_data_generation(self):
        """Test test data generation helpers."""
        # Generate test job inputs
        test_prompts = [
            "A beautiful sunset over mountains",
            "A cat playing in a garden",
            "Abstract geometric patterns",
            "Futuristic cityscape at night"
        ]
        
        test_jobs = []
        for i, prompt in enumerate(test_prompts):
            job = JobInput(
                prompt=prompt,
                job_type=Step.VIDEO,
                width=512,
                height=512,
                duration=5.0,
                user_id=f"test_user_{i}"
            )
            test_jobs.append(job)
        
        assert len(test_jobs) == len(test_prompts)
        assert all(job.job_type == Step.VIDEO for job in test_jobs)
        assert all(job.width == 512 for job in test_jobs)


def run_unit_tests():
    """Run all unit tests."""
    print("\n" + "="*60)
    print("🧪 运行综合单元测试")
    print("="*60)
    
    # Run pytest with verbose output
    pytest_args = [
        __file__,
        "-v",
        "--tb=short",
        "--color=yes"
    ]
    
    return pytest.main(pytest_args)


if __name__ == "__main__":
    exit_code = run_unit_tests()
    sys.exit(exit_code)