# Temporal 自定义搜索属性集成指南

本文档介绍了如何在 Temporal 工作流中使用新集成的 `CustomProgress` 和 `CustomTag` 搜索属性，以及如何通过 Temporal UI 进行监控和搜索。

## 🎯 概述

我们已经成功集成了两个新的自定义搜索属性：

- **CustomProgress**: 详细的工作流进度跟踪，格式为 `step:status:percent`
- **CustomTag**: 工作流分类和标记，用于过滤和监控

## 📋 目录

- [快速开始](#快速开始)
- [搜索属性详解](#搜索属性详解)
- [使用示例](#使用示例)
- [监控和搜索](#监控和搜索)
- [最佳实践](#最佳实践)
- [故障排除](#故障排除)

## 🚀 快速开始

### 1. 启动 Temporal 服务

```bash
# 使用我们的自定义启动脚本
./scripts/start_temporal_ui.sh

# 或者手动启动
docker-compose up -d
```

### 2. 注册自定义搜索属性

启动脚本会自动注册搜索属性，也可以手动注册：

```bash
# 注册 CustomProgress 属性
docker exec temporal-admin-tools tctl --address temporal:7233 cluster add-search-attributes \
    --name CustomProgress --type Text

# 注册 CustomTag 属性
docker exec temporal-admin-tools tctl --address temporal:7233 cluster add-search-attributes \
    --name CustomTag --type Text
```

### 3. 访问监控界面

- **Temporal UI**: http://localhost:8080
- **自定义监控仪表板**: `monitoring/dashboard.html`

## 🔍 搜索属性详解

### CustomProgress 属性

**格式**: `step:status:percent`

**组成部分**:
- `step`: 当前执行步骤（如 `video_generation`, `image_processing`）
- `status`: 状态（`pending`, `processing`, `completed`, `failed`）
- `percent`: 进度百分比（0-100）

**示例值**:
```
video_generation:processing:75
image_creation:completed:100
data_processing:failed:45
COMPLETION:success:100
initial_step:pending:0
```

### CustomTag 属性

**用途**: 工作流分类、优先级标记、错误类型标识

**示例值**:
```
benchmark_test_high_priority
production_video_processing
error_recoverable_retry
completion_success_final
initial_step_pending_initialized
```

## 💻 使用示例

### 在工作流中更新搜索属性

```python
from activities.search_attributes import SearchAttributeUpdater

# 创建搜索属性更新器
updater = SearchAttributeUpdater()

# 设置自定义进度
updater.set_custom_progress("video_generation:processing:75")

# 设置自定义标签
updater.set_custom_tag("production_high_priority")

# 应用更新
updater.apply_updates()
```

### 在活动中使用

```python
# 在 state_activities.py 中的示例
def update_workflow_progress(state: WorkflowState, additional_data: dict = None):
    updater = SearchAttributeUpdater()
    
    # 设置标准属性
    updater.set_workflow_status(state.status)
    updater.set_progress_percentage(state.progress_percentage)
    
    # 设置自定义进度
    custom_progress = f"{state.current_step}:{state.status.lower()}:{state.progress_percentage}"
    updater.set_custom_progress(custom_progress)
    
    # 设置自定义标签
    custom_tag = f"{state.current_step}_{state.status.lower()}"
    if additional_data and 'priority' in additional_data:
        custom_tag += f"_{additional_data['priority']}"
    updater.set_custom_tag(custom_tag)
    
    updater.apply_updates()
```

## 🔎 监控和搜索

### Temporal UI 搜索查询

#### 基础搜索

```sql
-- 搜索特定进度状态
CustomProgress:"*:processing:*"

-- 搜索特定步骤
CustomProgress:"video_generation:*"

-- 搜索特定标签
CustomTag:"benchmark*"

-- 搜索错误相关
CustomTag:"*error*"
```

#### 组合搜索

```sql
-- 运行中的生产工作流
WorkflowStatus:RUNNING AND CustomTag:"production"

-- 失败的工作流及其进度
CustomProgress:"*:failed:*" AND ErrorCount:[1 TO *]

-- 视频处理中的工作流
JobType:VIDEO AND CustomProgress:"*:processing:*"

-- 基准测试工作流
CustomTag:"benchmark" AND ProgressPercentage:[50 TO 100]
```

#### 时间范围搜索

```sql
-- 最近1小时的错误
StartTime:[now-1h TO now] AND CustomTag:"error"

-- 最近30分钟更新的工作流
LastUpdateTime:[now-30m TO now]

-- 今天完成的工作流
WorkflowStatus:COMPLETED AND StartTime:[now-1d TO now]
```

### 预定义搜索视图

在 `config/temporal_ui_config.yaml` 中定义了以下视图：

1. **基准测试工作流**: 过滤包含 "benchmark" 标签的工作流
2. **生产工作流**: 排除测试工作流，只显示生产环境
3. **错误分析**: 专门用于分析失败的工作流

## 📊 监控仪表板

### 自定义监控仪表板

打开 `monitoring/dashboard.html` 查看：

- 搜索属性格式说明
- 常用搜索查询示例
- 实时监控指标
- 快速链接到 Temporal UI

### 关键监控指标

- **活跃工作流数量**: `WorkflowStatus:RUNNING`
- **今日完成数量**: `WorkflowStatus:COMPLETED AND StartTime:[now-1d TO now]`
- **平均进度**: 基于 `ProgressPercentage` 字段
- **错误率**: `ErrorCount:[1 TO *]`

## 🎯 最佳实践

### 1. CustomProgress 命名规范

```python
# 推荐格式
"video_generation:processing:75"  # 清晰的步骤名称
"image_creation:completed:100"     # 明确的状态
"data_processing:failed:45"       # 包含失败信息

# 避免
"step1:running:50"                # 不够描述性
"process:ok:75"                   # 状态不明确
```

### 2. CustomTag 策略

```python
# 分层标记
"production_video_high_priority"   # 环境_类型_优先级
"test_benchmark_performance"       # 环境_用途_类别
"error_recoverable_network"        # 类型_可恢复性_原因

# 保持一致性
# 使用下划线分隔
# 使用小写字母
# 包含关键分类信息
```

### 3. 更新频率

- **高频更新**: 长时间运行的任务每30秒更新一次进度
- **状态变更**: 每次状态改变时立即更新
- **错误处理**: 发生错误时立即更新标签和进度

### 4. 搜索优化

- 使用通配符进行模糊搜索：`CustomTag:"production*"`
- 组合多个条件提高精确度
- 利用时间范围缩小搜索结果
- 保存常用搜索查询

## 🔧 故障排除

### 常见问题

#### 1. 搜索属性未注册

**症状**: 搜索时提示属性不存在

**解决方案**:
```bash
# 检查已注册的搜索属性
docker exec temporal-admin-tools tctl --address temporal:7233 cluster get-search-attributes

# 重新注册
./scripts/start_temporal_ui.sh register
```

#### 2. 搜索结果为空

**症状**: 明确存在的工作流搜索不到

**解决方案**:
- 检查搜索语法是否正确
- 确认属性值格式是否符合预期
- 使用通配符进行模糊搜索
- 检查时间范围设置

#### 3. UI 无法访问

**症状**: http://localhost:8080 无法打开

**解决方案**:
```bash
# 检查服务状态
docker-compose ps

# 重启服务
docker-compose restart temporal-web

# 查看日志
docker-compose logs temporal-web
```

### 调试命令

```bash
# 查看所有搜索属性
docker exec temporal-admin-tools tctl --address temporal:7233 cluster get-search-attributes

# 查看特定工作流的搜索属性
docker exec temporal-admin-tools tctl --address temporal:7233 workflow show \
    --workflow_id <WORKFLOW_ID>

# 测试搜索查询
docker exec temporal-admin-tools tctl --address temporal:7233 workflow list \
    --query 'CustomProgress:"*:processing:*"'
```

## 📚 相关文件

- `activities/search_attributes.py`: 搜索属性定义和更新逻辑
- `activities/state_activities.py`: 工作流状态管理和属性更新
- `config/temporal_ui_config.yaml`: UI 配置和视图定义
- `scripts/start_temporal_ui.sh`: 启动脚本和属性注册
- `monitoring/dashboard.html`: 自定义监控仪表板
- `docker-compose.yml`: Temporal 服务配置

## 🔗 有用链接

- [Temporal UI](http://localhost:8080): 主要的 Temporal Web 界面
- [工作流列表](http://localhost:8080/namespaces/default/workflows): 查看所有工作流
- [处理中的工作流](http://localhost:8080/namespaces/default/workflows?query=CustomProgress%3A%22*%3Aprocessing%3A*%22): 过滤处理中的工作流
- [基准测试工作流](http://localhost:8080/namespaces/default/workflows?query=CustomTag%3A%22benchmark*%22): 查看基准测试

---

**注意**: 确保 Temporal 服务正在运行，并且已经注册了自定义搜索属性，然后就可以开始使用这些强大的监控和搜索功能了！