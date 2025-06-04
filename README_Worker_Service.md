# Temporal Worker Service

这是一个专门的 Temporal Worker 服务，用于执行工作流和活动，具有适当的配置和生命周期管理。

## 功能特性

### 🚀 核心功能
- **专用 Worker 服务**: 独立的 Worker 进程，专门处理 Temporal 工作流和活动
- **优雅关闭**: 支持 SIGINT 和 SIGTERM 信号的优雅关闭处理
- **配置灵活**: 支持环境变量和参数配置
- **健康检查**: 内置健康检查功能
- **日志记录**: 完整的日志记录和错误处理

### 📋 支持的工作流
- `GenVideoWorkflow`: 视频生成工作流
- `VideoGenerationWorkflow`: 视频生成工作流（旧版）
- `ImageGenerationWorkflow`: 图像生成工作流
- `BatchProcessingWorkflow`: 批处理工作流

### 🔧 支持的活动
- **视频活动**: `submit_video_request`, `check_video_status`, `download_video_result`, `send_video_notification`
- **图像活动**: `submit_image_request`, `check_image_status`, `download_image_result`, `send_image_notification`, `gen_image`
- **通用活动**: `validate_request`, `log_activity`, `handle_error`, `cleanup_resources`

## 安装和配置

### 前置条件
1. Python 3.8+
2. Temporal Server 运行在 `localhost:7233`
3. 安装依赖包：
   ```bash
   pip install temporalio
   ```

### 环境变量配置

创建 `.env` 文件或设置环境变量：

```bash
# Temporal 服务器配置
TEMPORAL_HOST=localhost:7233          # Temporal 服务器地址
TEMPORAL_NAMESPACE=default            # Temporal 命名空间
TEMPORAL_TASK_QUEUE=gen-video-queue   # 任务队列名称

# Worker 性能配置
MAX_CONCURRENT_ACTIVITIES=10          # 最大并发活动数
MAX_CONCURRENT_WORKFLOWS=100          # 最大并发工作流数
```

## 使用方法

### 1. 直接运行 Worker

```bash
# 使用默认配置运行
python3 worker.py

# 查看帮助信息
python3 worker.py --help

# 查看版本信息
python3 worker.py --version
```

### 2. 程序化使用

```python
import asyncio
from worker import TemporalWorkerService

async def main():
    # 创建 Worker 服务
    worker_service = TemporalWorkerService(
        temporal_host="localhost:7233",
        namespace="default",
        task_queue="gen-video-queue",
        max_concurrent_activities=10,
        max_concurrent_workflows=100
    )
    
    try:
        # 初始化服务
        await worker_service.initialize()
        
        # 启动服务
        await worker_service.start()
    except KeyboardInterrupt:
        print("收到中断信号")
    finally:
        # 优雅关闭
        await worker_service.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. Docker 部署

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# 设置环境变量
ENV TEMPORAL_HOST=temporal-server:7233
ENV TEMPORAL_TASK_QUEUE=gen-video-queue
ENV MAX_CONCURRENT_ACTIVITIES=20
ENV MAX_CONCURRENT_WORKFLOWS=200

CMD ["python3", "worker.py"]
```

## 配置选项

### Worker 配置

| 参数 | 环境变量 | 默认值 | 描述 |
|------|----------|--------|------|
| `temporal_host` | `TEMPORAL_HOST` | `localhost:7233` | Temporal 服务器地址 |
| `namespace` | `TEMPORAL_NAMESPACE` | `default` | Temporal 命名空间 |
| `task_queue` | `TEMPORAL_TASK_QUEUE` | `gen-video-queue` | 任务队列名称 |
| `max_concurrent_activities` | `MAX_CONCURRENT_ACTIVITIES` | `10` | 最大并发活动数 |
| `max_concurrent_workflows` | `MAX_CONCURRENT_WORKFLOWS` | `100` | 最大并发工作流数 |

### 性能调优

```python
# 高性能配置示例
worker_service = TemporalWorkerService(
    temporal_host="localhost:7233",
    namespace="production",
    task_queue="high-throughput-queue",
    max_concurrent_activities=50,     # 增加并发活动
    max_concurrent_workflows=500      # 增加并发工作流
)
```

## 监控和日志

### 日志配置

Worker 服务会生成详细的日志：
- **控制台输出**: 实时日志显示
- **文件日志**: 保存到 `worker.log` 文件
- **日志级别**: INFO（可通过 logging 配置调整）

### 健康检查

```python
# 检查 Worker 健康状态
health = await worker_service.health_check()
print(f"Worker 健康状态: {health}")
```

### 监控指标

Worker 服务提供以下监控信息：
- 连接状态
- 注册的工作流数量
- 注册的活动数量
- 运行状态
- 配置参数

## 故障排除

### 常见问题

1. **连接失败**
   ```
   Failed to initialize Temporal Worker Service: ...
   ```
   - 检查 Temporal Server 是否运行
   - 验证 `TEMPORAL_HOST` 配置
   - 检查网络连接

2. **导入错误**
   ```
   ImportError: cannot import name '...' from '...'
   ```
   - 检查所有依赖模块是否存在
   - 验证 Python 路径配置
   - 确保所有必需的文件都在正确位置

3. **权限错误**
   ```
   PermissionError: [Errno 13] Permission denied: 'worker.log'
   ```
   - 检查日志文件写入权限
   - 确保运行用户有适当权限

### 调试模式

```python
# 启用调试日志
import logging
logging.getLogger().setLevel(logging.DEBUG)

# 或者在环境变量中设置
export PYTHONPATH="."
export LOG_LEVEL="DEBUG"
```

## 测试

### 运行测试

```bash
# 运行 Worker 服务测试
python3 test_worker_service.py
```

测试包括：
- ✅ 服务创建和配置
- ✅ 属性和方法完整性
- ✅ 初始状态检查
- ✅ 工作流和活动导入
- ✅ 信号处理器设置
- ✅ 环境变量支持

### 集成测试

要进行完整的集成测试，需要：
1. 启动 Temporal Server
2. 运行 Worker 服务
3. 提交测试工作流
4. 验证执行结果

## 生产部署

### 推荐配置

```bash
# 生产环境配置
TEMPORAL_HOST=temporal-cluster:7233
TEMPORAL_NAMESPACE=production
TEMPORAL_TASK_QUEUE=video-generation
MAX_CONCURRENT_ACTIVITIES=50
MAX_CONCURRENT_WORKFLOWS=500
```

### 高可用性

1. **多实例部署**: 运行多个 Worker 实例
2. **负载均衡**: Temporal 自动分配任务
3. **故障恢复**: Worker 重启后自动重新连接
4. **监控告警**: 集成监控系统

### 安全考虑

1. **网络安全**: 使用 TLS 连接
2. **认证授权**: 配置 Temporal 认证
3. **资源限制**: 设置适当的并发限制
4. **日志安全**: 避免记录敏感信息

## API 参考

### TemporalWorkerService 类

```python
class TemporalWorkerService:
    def __init__(
        self,
        temporal_host: str = "localhost:7233",
        namespace: str = "default",
        task_queue: str = "gen-video-queue",
        max_concurrent_activities: int = 10,
        max_concurrent_workflows: int = 100
    )
    
    async def initialize(self) -> None
    async def start(self) -> None
    async def shutdown(self) -> None
    async def health_check(self) -> bool
```

### 主要方法

- `initialize()`: 初始化 Temporal 客户端和 Worker
- `start()`: 启动 Worker 服务
- `shutdown()`: 优雅关闭服务
- `health_check()`: 检查服务健康状态

## 版本历史

- **v1.0.0**: 初始版本
  - 基本 Worker 服务功能
  - 优雅关闭支持
  - 环境变量配置
  - 健康检查功能

## 许可证

本项目采用 MIT 许可证。