# 术语表

## Temporal 相关术语

**Workflow（工作流）**
- 定义业务逻辑的持久化函数，可以跨越长时间执行
- 本项目中包括：GenVideoWorkflow, ImageGenerationWorkflow, VideoGenerationWorkflow, BatchProcessingWorkflow

**Activity（活动）**
- 执行具体业务操作的函数，如API调用、文件操作等
- 本项目中包括：gen_image, request_video, 状态检查等

**Worker（工作器）**
- 执行工作流和活动的进程，连接到 Temporal Server

**Signal（信号）**
- 向运行中的工作流发送消息的机制
- 本项目中用于处理异步回调：video_ready, kling_done

**Query（查询）**
- 从运行中的工作流获取状态信息的机制
- 本项目中用于进度查询：get_progress

**Search Attributes（搜索属性）**
- 用于在 Temporal UI 中搜索和过滤工作流的自定义属性
- 本项目中使用：CustomProgress, CustomTag

## 业务术语

**生图→图转视频**
- 核心业务流程：先生成图像，然后将图像转换为视频

**ComfyUI**
- 图像生成服务，提供 HTTP API 接口

**Kling API**
- 视频生成服务，支持异步处理和回调机制

**渐进式压力测试**
- 从单任务逐步增加到100并发任务的测试策略

## 技术术语

**并发控制**
- 通过全局信号量限制同时执行的任务数量

**状态持久化**
- 将工作流状态保存到持久化存储（PostgreSQL）

**审计日志**
- 记录工作流事件和状态变更的日志系统

**回调服务器**
- 专门处理外部API异步回调的HTTP服务