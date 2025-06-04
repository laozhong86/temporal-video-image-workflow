"""Configuration settings for the Temporal application."""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import os
from datetime import timedelta


@dataclass
class TemporalConfig:
    """Temporal server configuration."""
    host: str = "localhost:7233"
    namespace: str = "default"
    task_queue: str = "generation-queue"
    
    # Workflow timeouts (in hours)
    video_workflow_timeout: int = 3
    image_workflow_timeout: int = 2
    batch_workflow_timeout: int = 6
    
    # Activity timeouts (in minutes)
    activity_start_to_close_timeout: int = 30
    activity_schedule_to_close_timeout: int = 60
    
    # Retry policies
    max_retry_attempts: int = 3
    initial_retry_interval: int = 5  # seconds
    max_retry_interval: int = 300  # seconds


@dataclass
class ExternalAPIConfig:
    """External API configuration for video/image generation services."""
    # Video generation service
    video_api_base_url: str = "https://api.video-service.com"
    video_api_key: Optional[str] = None
    video_api_timeout: int = 300  # seconds
    
    # Image generation service
    image_api_base_url: str = "https://api.image-service.com"
    image_api_key: Optional[str] = None
    image_api_timeout: int = 180  # seconds
    
    # Common settings
    max_retries: int = 3
    retry_delay: int = 5  # seconds


@dataclass
class StorageConfig:
    """Storage configuration for temporary files and results."""
    temp_dir: str = "/tmp/temporal_generation"
    results_dir: str = "./results"
    max_file_size: int = 500 * 1024 * 1024  # 500MB
    cleanup_after_hours: int = 24
    
    # S3 configuration (optional)
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None


@dataclass
class NotificationConfig:
    """Notification configuration."""
    # Webhook settings
    webhook_timeout: int = 30  # seconds
    webhook_retries: int = 3
    webhook_retry_delay: int = 5  # seconds
    
    # Email settings (optional)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    
    # Slack settings (optional)
    slack_webhook_url: Optional[str] = None


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    
    # Structured logging
    use_json_format: bool = False
    include_trace_id: bool = True


@dataclass
class SecurityConfig:
    """Security configuration."""
    # API key validation
    require_api_key: bool = True
    api_key_header: str = "X-API-Key"
    valid_api_keys: list = None
    
    # Rate limiting
    enable_rate_limiting: bool = True
    requests_per_minute: int = 100
    requests_per_hour: int = 1000
    
    # Request validation
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: list = None
    
    def __post_init__(self):
        if self.valid_api_keys is None:
            self.valid_api_keys = []
        if self.allowed_file_types is None:
            self.allowed_file_types = ["mp4", "avi", "mov", "jpg", "jpeg", "png", "gif"]


@dataclass
class BatchProcessingConfig:
    """Batch processing configuration."""
    batch_size: int = 10
    max_concurrent_batches: int = 3
    batch_timeout_seconds: int = 300
    retry_failed_items: bool = True
    max_retries_per_item: int = 3


@dataclass
class DatabaseConfig:
    """Database configuration for audit logging."""
    host: str = "localhost"
    port: int = 5432
    database: str = "temporal_audit"
    username: str = "temporal"
    password: str = "temporal"
    min_connections: int = 5
    max_connections: int = 20
    command_timeout: int = 30
    server_settings: Dict[str, str] = field(default_factory=lambda: {
        "application_name": "temporal_audit_logger",
        "timezone": "UTC"
    })
    
    @property
    def dsn(self) -> str:
        """Get database connection string."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class AppConfig:
    """Main application configuration."""
    
    def __init__(self):
        self.temporal = TemporalConfig()
        self.external_api = ExternalAPIConfig()
        self.storage = StorageConfig()
        self.notification = NotificationConfig()
        self.logging = LoggingConfig()
        self.security = SecurityConfig()
        self.batch_processing = BatchProcessingConfig()
        self.database = DatabaseConfig()
        
        # Load from environment variables
        self._load_from_env()
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _load_from_env(self):
        """Load configuration from environment variables."""
        # Temporal configuration
        self.temporal.host = os.getenv("TEMPORAL_HOST", self.temporal.host)
        self.temporal.namespace = os.getenv("TEMPORAL_NAMESPACE", self.temporal.namespace)
        self.temporal.task_queue = os.getenv("TEMPORAL_TASK_QUEUE", self.temporal.task_queue)
        
        # External API configuration
        self.external_api.video_api_base_url = os.getenv("VIDEO_API_BASE_URL", self.external_api.video_api_base_url)
        self.external_api.video_api_key = os.getenv("VIDEO_API_KEY")
        self.external_api.image_api_base_url = os.getenv("IMAGE_API_BASE_URL", self.external_api.image_api_base_url)
        self.external_api.image_api_key = os.getenv("IMAGE_API_KEY")
        
        # Storage configuration
        self.storage.temp_dir = os.getenv("TEMP_DIR", self.storage.temp_dir)
        self.storage.results_dir = os.getenv("RESULTS_DIR", self.storage.results_dir)
        self.storage.s3_bucket = os.getenv("S3_BUCKET")
        self.storage.s3_region = os.getenv("S3_REGION", self.storage.s3_region)
        self.storage.s3_access_key = os.getenv("S3_ACCESS_KEY")
        self.storage.s3_secret_key = os.getenv("S3_SECRET_KEY")
        
        # Notification configuration
        self.notification.smtp_host = os.getenv("SMTP_HOST")
        self.notification.smtp_port = int(os.getenv("SMTP_PORT", self.notification.smtp_port))
        self.notification.smtp_username = os.getenv("SMTP_USERNAME")
        self.notification.smtp_password = os.getenv("SMTP_PASSWORD")
        self.notification.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        
        # Logging configuration
        self.logging.level = os.getenv("LOG_LEVEL", self.logging.level)
        self.logging.file_path = os.getenv("LOG_FILE_PATH")
        
        # Security configuration
        api_keys_env = os.getenv("API_KEYS")
        if api_keys_env:
            self.security.valid_api_keys = api_keys_env.split(",")
        
        # Convert string boolean values
        self.security.require_api_key = os.getenv("REQUIRE_API_KEY", "true").lower() == "true"
        self.security.enable_rate_limiting = os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true"
        self.logging.use_json_format = os.getenv("USE_JSON_LOGGING", "false").lower() == "true"
    
    def _ensure_directories(self):
        """Ensure required directories exist."""
        directories = [
            self.storage.temp_dir,
            self.storage.results_dir
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def get_video_generation_config(self) -> Dict[str, Any]:
        """Get configuration specific to video generation."""
        return {
            "api_base_url": self.external_api.video_api_base_url,
            "api_key": self.external_api.video_api_key,
            "timeout": self.external_api.video_api_timeout,
            "max_retries": self.external_api.max_retries,
            "retry_delay": self.external_api.retry_delay,
            "temp_dir": self.storage.temp_dir,
            "results_dir": self.storage.results_dir
        }
    
    def get_image_generation_config(self) -> Dict[str, Any]:
        """Get configuration specific to image generation."""
        return {
            "api_base_url": self.external_api.image_api_base_url,
            "api_key": self.external_api.image_api_key,
            "timeout": self.external_api.image_api_timeout,
            "max_retries": self.external_api.max_retries,
            "retry_delay": self.external_api.retry_delay,
            "temp_dir": self.storage.temp_dir,
            "results_dir": self.storage.results_dir
        }
    
    def get_notification_config(self) -> Dict[str, Any]:
        """Get notification configuration."""
        return {
            "webhook_timeout": self.notification.webhook_timeout,
            "webhook_retries": self.notification.webhook_retries,
            "webhook_retry_delay": self.notification.webhook_retry_delay,
            "smtp_config": {
                "host": self.notification.smtp_host,
                "port": self.notification.smtp_port,
                "username": self.notification.smtp_username,
                "password": self.notification.smtp_password,
                "use_tls": self.notification.smtp_use_tls
            } if self.notification.smtp_host else None,
            "slack_webhook_url": self.notification.slack_webhook_url
        }
    
    def validate(self) -> list:
        """Validate configuration and return list of errors."""
        errors = []
        
        # Check required API keys
        if not self.external_api.video_api_key:
            errors.append("VIDEO_API_KEY environment variable is required")
        
        if not self.external_api.image_api_key:
            errors.append("IMAGE_API_KEY environment variable is required")
        
        # Check security configuration
        if self.security.require_api_key and not self.security.valid_api_keys:
            errors.append("API keys are required but none are configured")
        
        # Check storage configuration
        if self.storage.s3_bucket and not (self.storage.s3_access_key and self.storage.s3_secret_key):
            errors.append("S3 bucket configured but access credentials are missing")
        
        # Check notification configuration
        if (self.notification.smtp_host and 
            not (self.notification.smtp_username and self.notification.smtp_password)):
            errors.append("SMTP host configured but credentials are missing")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (excluding sensitive data)."""
        return {
            "temporal": {
                "host": self.temporal.host,
                "namespace": self.temporal.namespace,
                "task_queue": self.temporal.task_queue
            },
            "external_api": {
                "video_api_base_url": self.external_api.video_api_base_url,
                "image_api_base_url": self.external_api.image_api_base_url,
                "video_api_timeout": self.external_api.video_api_timeout,
                "image_api_timeout": self.external_api.image_api_timeout
            },
            "storage": {
                "temp_dir": self.storage.temp_dir,
                "results_dir": self.storage.results_dir,
                "s3_bucket": self.storage.s3_bucket,
                "s3_region": self.storage.s3_region
            },
            "security": {
                "require_api_key": self.security.require_api_key,
                "enable_rate_limiting": self.security.enable_rate_limiting,
                "requests_per_minute": self.security.requests_per_minute
            },
            "batch_processing": {
                "batch_size": self.batch_processing.batch_size,
                "max_concurrent_batches": self.batch_processing.max_concurrent_batches,
                "batch_timeout_seconds": self.batch_processing.batch_timeout_seconds
            },
            "database": {
                "host": self.database.host,
                "port": self.database.port,
                "database": self.database.database,
                "username": self.database.username,
                "min_connections": self.database.min_connections,
                "max_connections": self.database.max_connections,
                "command_timeout": self.database.command_timeout
            }
        }


# Global configuration instance
config = AppConfig()


def get_config() -> AppConfig:
    """Get the global configuration instance."""
    return config


def reload_config() -> AppConfig:
    """Reload configuration from environment variables."""
    global config
    config = AppConfig()
    return config