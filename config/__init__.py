import sys
import os
import importlib.util

# Import from config.py file directly
config_py_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.py')
spec = importlib.util.spec_from_file_location("config_module", config_py_path)
config_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_module)

# Get the classes from the module
TemporalConfig = config_module.TemporalConfig
ExternalAPIConfig = config_module.ExternalAPIConfig
StorageConfig = config_module.StorageConfig
NotificationConfig = config_module.NotificationConfig
LoggingConfig = config_module.LoggingConfig
SecurityConfig = config_module.SecurityConfig
BatchProcessingConfig = config_module.BatchProcessingConfig
DatabaseConfig = config_module.DatabaseConfig

__all__ = [
    "TemporalConfig",
    "ExternalAPIConfig",
    "StorageConfig",
    "NotificationConfig", 
    "LoggingConfig",
    "SecurityConfig",
    "BatchProcessingConfig",
    "DatabaseConfig"
]