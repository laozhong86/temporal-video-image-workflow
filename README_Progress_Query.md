# Progress Query Interface

本文档介绍如何使用 Temporal 工作流的进度查询接口，包括 REST API 端点和直接查询工具。

## 概述

进度查询接口提供了多种方式来监控 Temporal 工作流的执行进度：

1. **REST API 端点** - 通过 HTTP 请求查询进度
2. **直接 Temporal 查询** - 直接连接 Temporal 服务器查询
3. **CLI 工具** - 命令行工具用于快速查询
4. **Python 客户端** - 编程接口用于集成到其他应用

## REST API 端点

### 1. 基础工作流状态

```http
GET /workflows/{workflow_id}/status
```

返回基础的工作流状态信息：

```json
{
  "workflow_id": "gen-video-123",
  "status": "RUNNING",
  "start_time": "2024-01-15T10:30:00Z",
  "close_time": null,
  "workflow_type": "GenVideoWorkflow",
  "task_queue": "gen-video-queue"
}
```

### 2. 进度查询

```http
GET /workflows/{workflow_id}/progress
```

返回详细的进度信息：

```json
{
  "workflow_id": "gen-video-123",
  "workflow_status": "RUNNING",
  "progress": {
    "step": "video_generation",
    "status": "running",
    "percent": 75,
    "message": "Generating video...",
    "asset_url": "https://example.com/temp.mp4",
    "updated_at": "2024-01-15T10:35:00Z"
  },
  "timestamp": "2024-01-15T10:35:30Z"
}
```

### 3. 详细状态查询

```http
GET /workflows/{workflow_id}/detailed-status
```

返回完整的工作流状态和进度信息：

```json
{
  "workflow_id": "gen-video-123",
  "workflow_status": "RUNNING",
  "start_time": "2024-01-15T10:30:00Z",
  "close_time": null,
  "workflow_type": "GenVideoWorkflow",
  "task_queue": "gen-video-queue",
  "progress": {
    "step": "video_generation",
    "status": "running",
    "percent": 75,
    "message": "Generating video...",
    "asset_url": "https://example.com/temp.mp4",
    "updated_at": "2024-01-15T10:35:00Z"
  },
  "detailed_status": {
    "workflow_id": "gen-video-123",
    "job_input": {...},
    "current_progress": {...},
    "started_at": "2024-01-15T10:30:00Z",
    "progress_history": [...]
  },
  "timestamp": "2024-01-15T10:35:30Z"
}
```

## CLI 工具使用

### 安装和设置

```bash
# 确保脚本有执行权限
chmod +x scripts/query_progress.py

# 或者使用 Python 直接运行
python scripts/query_progress.py --help
```

### 基本用法

#### 1. 查询单个工作流

```bash
# 使用默认的回退方法（先尝试直接查询，失败后使用 API）
python scripts/query_progress.py single workflow-123

# 强制使用 API 查询
python scripts/query_progress.py single workflow-123 --method api

# 获取详细状态
python scripts/query_progress.py single workflow-123 --method detailed

# 输出为 JSON 格式
python scripts/query_progress.py single workflow-123 --json
```

#### 2. 查询多个工作流

```bash
# 查询多个工作流的进度
python scripts/query_progress.py multiple "workflow-1,workflow-2,workflow-3"

# 使用 API 方法查询多个工作流
python scripts/query_progress.py multiple "workflow-1,workflow-2" --method api --json
```

#### 3. 监控工作流进度

```bash
# 监控工作流进度（每5秒查询一次）
python scripts/query_progress.py monitor workflow-123

# 自定义监控间隔和最大次数
python scripts/query_progress.py monitor workflow-123 --interval 2 --max-iterations 50

# 使用 API 方法监控
python scripts/query_progress.py monitor workflow-123 --method api --interval 1
```

### 配置选项

```bash
# 指定 Temporal 服务器地址
python scripts/query_progress.py single workflow-123 --temporal-host localhost:7233

# 指定命名空间
python scripts/query_progress.py single workflow-123 --namespace production

# 指定 API 服务器地址
python scripts/query_progress.py single workflow-123 --api-url http://api.example.com:8000

# 启用详细日志
python scripts/query_progress.py single workflow-123 --verbose
```

## Python 客户端使用

### 基本使用

```python
import asyncio
from utils.progress_client import ProgressQueryClient

async def main():
    # 创建客户端
    client = ProgressQueryClient(
        temporal_host="localhost:7233",
        namespace="default",
        api_base_url="http://localhost:8000"
    )
    
    try:
        # 查询单个工作流进度
        result = await client.query_progress_with_fallback("workflow-123")
        
        if result.success:
            print(f"Progress: {result.progress}")
        else:
            print(f"Error: {result.error}")
        
        # 查询多个工作流
        workflow_ids = ["wf-1", "wf-2", "wf-3"]
        results = await client.query_multiple_workflows(workflow_ids)
        
        for result in results:
            print(client.format_progress_result(result))
        
        # 监控工作流进度
        monitor_results = await client.monitor_progress(
            "workflow-123",
            interval=2.0,
            max_iterations=30
        )
        
        print("Progress history:")
        for i, result in enumerate(monitor_results):
            print(f"[{i+1}] {client.format_progress_result(result)}")
    
    finally:
        await client.close()

# 运行
asyncio.run(main())
```

### 高级用法

```python
# 仅使用直接 Temporal 查询
result = await client.query_progress_direct("workflow-123")

# 仅使用 API 查询
result = await client.query_progress_api("workflow-123")

# 查询详细状态
result = await client.query_detailed_status_api("workflow-123")

# 并发查询多个工作流
workflow_ids = ["wf-1", "wf-2", "wf-3"]
results = await client.query_multiple_workflows(workflow_ids, use_api=True)
```

## 工作流集成

### 在工作流中实现进度查询

```python
from temporalio import workflow
from models.core_models import Progress, JobStatus, Step

@workflow.defn
class GenVideoWorkflow:
    def __init__(self):
        self.current_progress = Progress(
            step=Step.PENDING,
            status=JobStatus.PENDING,
            percent=0
        )
    
    @workflow.query
    def get_progress(self) -> dict:
        """查询当前进度。"""
        return self.current_progress.to_json()
    
    @workflow.query
    def get_status(self) -> dict:
        """查询详细状态。"""
        return {
            "workflow_id": workflow.info().workflow_id,
            "current_progress": self.current_progress.to_json(),
            "started_at": workflow.info().start_time.isoformat(),
            # 其他状态信息...
        }
    
    async def _update_progress(self, step: Step, status: JobStatus, percent: int, message: str = ""):
        """更新工作流进度。"""
        self.current_progress = Progress(
            step=step,
            status=status,
            percent=percent,
            message=message,
            updated_at=datetime.now()
        )
        
        # 记录进度更新
        await workflow.execute_activity(
            log_progress_update,
            self.current_progress.to_json(),
            schedule_to_close_timeout=timedelta(seconds=30)
        )
```

## 错误处理

### 常见错误和解决方案

1. **工作流未找到**
   ```json
   {
     "detail": "Workflow not found or error: workflow not found"
   }
   ```
   - 检查工作流 ID 是否正确
   - 确认工作流是否已启动
   - 检查命名空间设置

2. **连接失败**
   ```json
   {
     "detail": "Failed to connect to Temporal server"
   }
   ```
   - 检查 Temporal 服务器是否运行
   - 验证服务器地址和端口
   - 检查网络连接

3. **查询超时**
   ```json
   {
     "detail": "Query timeout"
   }
   ```
   - 工作流可能已停止或崩溃
   - 增加查询超时时间
   - 检查工作流状态

## 性能考虑

### 查询频率

- **实时监控**: 1-2 秒间隔适合实时 UI 更新
- **定期检查**: 5-10 秒间隔适合后台监控
- **批量查询**: 使用 `query_multiple_workflows` 提高效率

### 缓存策略

```python
# 实现简单的进度缓存
class CachedProgressClient(ProgressQueryClient):
    def __init__(self, *args, cache_ttl=5.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = {}
        self.cache_ttl = cache_ttl
    
    async def query_progress_cached(self, workflow_id: str):
        now = time.time()
        
        # 检查缓存
        if workflow_id in self.cache:
            cached_result, timestamp = self.cache[workflow_id]
            if now - timestamp < self.cache_ttl:
                return cached_result
        
        # 查询新数据
        result = await self.query_progress_with_fallback(workflow_id)
        
        # 更新缓存
        if result.success:
            self.cache[workflow_id] = (result, now)
        
        return result
```

## 测试

### 运行测试

```bash
# 运行单元测试
pytest tests/test_progress_query.py -v

# 运行集成测试（需要 API 服务器运行）
python tests/test_progress_query.py

# 运行特定测试
pytest tests/test_progress_query.py::TestProgressQueryClient::test_query_progress_direct_success -v
```

### 手动测试

```bash
# 启动 API 服务器
python api_server.py --host 0.0.0.0 --port 8000

# 在另一个终端测试 API
curl http://localhost:8000/health
curl http://localhost:8000/workflows/test-workflow/progress

# 测试 CLI 工具
python scripts/query_progress.py single test-workflow --method api
```

## 部署注意事项

### 生产环境配置

1. **安全性**
   - 使用 HTTPS 进行 API 通信
   - 实现身份验证和授权
   - 限制 API 访问频率

2. **监控**
   - 监控 API 响应时间
   - 记录查询错误和失败率
   - 设置告警阈值

3. **扩展性**
   - 使用负载均衡器分发请求
   - 实现查询结果缓存
   - 考虑使用消息队列处理大量查询

### Docker 部署

```dockerfile
# Dockerfile 示例
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "api_server.py", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml 示例
version: '3.8'
services:
  progress-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - TEMPORAL_HOST=temporal:7233
      - TEMPORAL_NAMESPACE=default
    depends_on:
      - temporal
```

## 故障排除

### 常见问题

1. **进度查询返回空结果**
   - 检查工作流是否实现了 `get_progress` 查询方法
   - 确认工作流正在运行
   - 验证查询方法名称是否正确

2. **API 服务器无法连接 Temporal**
   - 检查 Temporal 服务器地址配置
   - 验证网络连接
   - 检查防火墙设置

3. **查询性能问题**
   - 减少查询频率
   - 实现结果缓存
   - 使用批量查询

### 调试技巧

```bash
# 启用详细日志
python scripts/query_progress.py single workflow-123 --verbose

# 检查 API 服务器日志
python api_server.py --reload  # 开发模式

# 使用 curl 直接测试 API
curl -v http://localhost:8000/workflows/test-workflow/progress
```

## 扩展功能

### 自定义查询方法

```python
# 在工作流中添加自定义查询
@workflow.query
def get_custom_metrics(self) -> dict:
    """获取自定义指标。"""
    return {
        "processing_time": self.processing_time,
        "memory_usage": self.memory_usage,
        "error_count": self.error_count
    }
```

### WebSocket 实时更新

```python
# 实现 WebSocket 端点用于实时进度更新
@app.websocket("/ws/workflows/{workflow_id}/progress")
async def websocket_progress(websocket: WebSocket, workflow_id: str):
    await websocket.accept()
    
    try:
        while True:
            result = await query_progress(workflow_id)
            await websocket.send_json(result)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
```

这个进度查询接口提供了全面的工作流监控能力，支持多种查询方式和集成选项，适合各种使用场景。