# Temporal Video/Image Generation Workflow

这是一个基于 Temporal 的视频和图片生成工作流系统，支持异步处理、错误重试、状态监控和批量处理。

## 功能特性

- **视频生成工作流**: 支持异步视频生成请求处理
- **图片生成工作流**: 支持异步图片生成请求处理
- **批量处理工作流**: 支持多个请求的并行或串行处理
- **错误处理和重试**: 内置重试机制和错误恢复
- **状态监控**: 实时查询工作流状态和进度
- **资源管理**: 自动清理临时文件和资源
- **通知系统**: 支持 Webhook、邮件和 Slack 通知

## 项目结构

```
.
├── models/                 # 数据模型定义
│   ├── __init__.py
│   ├── video_request.py    # 视频请求/响应模型
│   └── image_request.py    # 图片请求/响应模型
├── activities/             # Temporal 活动定义
│   ├── __init__.py
│   ├── video_activities.py # 视频相关活动
│   ├── image_activities.py # 图片相关活动
│   └── common_activities.py# 通用活动
├── workflows/              # Temporal 工作流定义
│   ├── __init__.py
│   ├── video_workflow.py   # 视频生成工作流
│   ├── image_workflow.py   # 图片生成工作流
│   └── batch_workflow.py   # 批量处理工作流
├── main.py                 # 主应用程序入口
├── config.py               # 配置管理
├── requirements.txt        # Python 依赖
├── .env.example           # 环境变量示例
├── .gitignore             # Git 忽略文件
└── README.md              # 项目文档
```

## 安装和配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制环境变量示例文件并配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置必要的参数：

```bash
# 必需配置
VIDEO_API_KEY=your_video_api_key_here
IMAGE_API_KEY=your_image_api_key_here

# 可选配置
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=default
```

### 3. 启动 Temporal Server

使用 Docker 启动 Temporal 开发环境：

```bash
# 使用 Docker Compose
docker run --rm -p 7233:7233 -p 8233:8233 temporalio/auto-setup:latest

# 或者使用 Temporal CLI
temporal server start-dev
```

### 4. 启动 Worker

```bash
python main.py
```

## 使用方法

### 视频生成工作流

```python
from main import TemporalApp

app = TemporalApp()
await app.initialize()

# 提交视频生成请求
video_request = {
    "request_id": "video_001",
    "type": "video",
    "prompt": "A beautiful sunset over the ocean",
    "duration": 10,
    "resolution": "1920x1080",
    "fps": 30,
    "style": "realistic",
    "webhook_url": "https://example.com/webhook",
    "user_id": "user123"
}

workflow_id = await app.submit_video_workflow(video_request)
print(f"Video workflow started: {workflow_id}")
```

### 图片生成工作流

```python
# 提交图片生成请求
image_request = {
    "request_id": "image_001",
    "type": "image",
    "prompt": "A majestic mountain landscape",
    "width": 1024,
    "height": 1024,
    "style": "photorealistic",
    "num_images": 2,
    "webhook_url": "https://example.com/webhook",
    "user_id": "user123"
}

workflow_id = await app.submit_image_workflow(image_request)
print(f"Image workflow started: {workflow_id}")
```

### 批量处理工作流

```python
# 提交批量处理请求
batch_request = {
    "batch_id": "batch_001",
    "processing_strategy": "parallel",  # 或 "sequential"
    "max_concurrent": 3,
    "requests": [video_request, image_request]
}

workflow_id = await app.submit_batch_workflow(batch_request)
print(f"Batch workflow started: {workflow_id}")
```

### 查询工作流状态

```python
# 查询工作流状态
status = await app.get_workflow_status(workflow_id)
print(f"Workflow status: {status}")

# 取消工作流
success = await app.cancel_workflow(workflow_id)
print(f"Cancellation successful: {success}")
```

## 数据模型

### 视频请求模型

```python
class VideoRequest(BaseModel):
    request_id: str
    prompt: str
    duration: int = 10  # 秒
    resolution: str = "1920x1080"
    fps: int = 30
    style: str = "realistic"
    webhook_url: Optional[str] = None
    user_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### 图片请求模型

```python
class ImageRequest(BaseModel):
    request_id: str
    prompt: str
    width: int = 1024
    height: int = 1024
    style: str = "photorealistic"
    num_images: int = 1
    webhook_url: Optional[str] = None
    user_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

## 工作流特性

### 错误处理和重试

- 自动重试失败的活动
- 可配置的重试策略
- 详细的错误日志和通知

### 状态监控

- 实时查询工作流状态
- 进度跟踪
- 性能指标收集

### 资源管理

- 自动清理临时文件
- 内存使用监控
- 超时处理

### 通知系统

- Webhook 通知
- 邮件通知（可选）
- Slack 通知（可选）

## 配置选项

### Temporal 配置

- `TEMPORAL_HOST`: Temporal 服务器地址
- `TEMPORAL_NAMESPACE`: 命名空间
- `TEMPORAL_TASK_QUEUE`: 任务队列名称

### API 配置

- `VIDEO_API_BASE_URL`: 视频生成 API 地址
- `VIDEO_API_KEY`: 视频生成 API 密钥
- `IMAGE_API_BASE_URL`: 图片生成 API 地址
- `IMAGE_API_KEY`: 图片生成 API 密钥

### 存储配置

- `TEMP_DIR`: 临时文件目录
- `RESULTS_DIR`: 结果文件目录
- `S3_BUCKET`: S3 存储桶（可选）

### 安全配置

- `REQUIRE_API_KEY`: 是否需要 API 密钥验证
- `API_KEYS`: 有效的 API 密钥列表
- `ENABLE_RATE_LIMITING`: 是否启用速率限制

## 开发和测试

### 运行测试

```bash
# 运行示例测试
python main.py test
```

### 开发模式

```bash
# 设置开发环境变量
export DEBUG=true
export MOCK_EXTERNAL_APIS=true

# 启动开发服务器
python main.py
```

## 监控和日志

### 日志配置

```bash
# 设置日志级别
export LOG_LEVEL=DEBUG

# 设置日志文件
export LOG_FILE_PATH=./logs/app.log

# 启用 JSON 格式日志
export USE_JSON_LOGGING=true
```

### Temporal Web UI

访问 Temporal Web UI 查看工作流状态：

```
http://localhost:8233
```

## 部署

### Docker 部署

```dockerfile
# Dockerfile 示例
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "main.py"]
```

### Kubernetes 部署

```yaml
# deployment.yaml 示例
apiVersion: apps/v1
kind: Deployment
metadata:
  name: temporal-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: temporal-worker
  template:
    metadata:
      labels:
        app: temporal-worker
    spec:
      containers:
      - name: worker
        image: your-registry/temporal-worker:latest
        env:
        - name: TEMPORAL_HOST
          value: "temporal-server:7233"
        - name: VIDEO_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: video-api-key
```

## 故障排除

### 常见问题

1. **连接 Temporal 服务器失败**
   - 检查 `TEMPORAL_HOST` 配置
   - 确保 Temporal 服务器正在运行

2. **API 调用失败**
   - 检查 API 密钥配置
   - 验证 API 端点可访问性

3. **工作流超时**
   - 调整超时配置
   - 检查外部服务响应时间

### 日志分析

```bash
# 查看错误日志
grep "ERROR" logs/app.log

# 查看特定工作流日志
grep "workflow_id=video_001" logs/app.log
```

## 贡献

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License