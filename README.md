# TaskMaster 项目

## 项目概述

TaskMaster 是一个强大的任务管理工具，帮助开发者有效地分解、跟踪和完成复杂项目。该工具使用 AI 辅助技术，优化项目开发流程，提高工作效率。

## 主要功能

- **任务分解**：自动将复杂项目拆分为可管理的小任务
- **任务依赖管理**：追踪和维护任务间的依赖关系
- **AI 辅助开发**：利用多种 AI 模型提供智能建议和解决方案
- **项目部署**：简化项目文件的部署和复制过程
- **复杂度分析**：评估任务复杂度，优化资源分配

## 快速入门

### 安装要求

- Node.js (v14.0.0 或更高版本)
- npm 或 yarn 包管理器
- 有效的 API 密钥 (用于 AI 功能)

### 安装步骤

1. 克隆仓库：
   ```
   git clone [仓库URL]
   cd taskmaster
   ```

2. 安装依赖：
   ```
   npm install
   ```
   或
   ```
   yarn install
   ```

3. 配置环境：
   ```
   cp .env.example .env
   ```
   然后编辑 `.env` 文件，添加您的 API 密钥和其他配置

4. 全局安装 CLI（可选）：
   ```
   npm install -g claude-task-master
   ```

## 使用指南

### 基本命令

TaskMaster 提供了一系列命令行工具，帮助您管理项目：

- **初始化项目**：
  ```
  task-master init
  ```
  或
  ```
  node scripts/dev.js parse-prd --input=<prd-file.txt>
  ```

- **查看任务列表**：
  ```
  task-master list
  ```

- **分析任务复杂度**：
  ```
  task-master analyze-complexity --research
  ```

- **分解任务**：
  ```
  task-master expand --id=<id>
  ```

- **更新任务状态**：
  ```
  task-master set-status --id=<id> --status=done
  ```

### 项目部署

使用内置的部署工具，您可以轻松地将项目文件复制到目标目录：

```
node scripts/deploy.js [目标路径]
```

此命令会将当前项目的所有文件（排除特定系统文件）复制到指定目录，并在执行前进行确认。

## 配置选项

TaskMaster 提供了丰富的配置选项，可通过 `.taskmasterconfig` 文件进行设置：

- **模型配置**：设置不同用途的 AI 模型
- **全局设置**：调整日志级别、默认任务数量等
- **API 集成**：配置与各种 AI 服务的连接

## 支持的 AI 提供商

TaskMaster 支持多种 AI 服务提供商：

- OpenRouter
- Anthropic (Claude)
- Perplexity
- OpenAI
- Google (Gemini)
- Mistral AI
- xAI
- Azure OpenAI
- Ollama

## 最佳实践

- 使用 `task-master list` 开始每个编码会话，了解当前任务状态
- 对于复杂任务，先使用 `analyze-complexity` 进行分析
- 按照依赖关系顺序完成任务，避免阻塞
- 及时更新任务状态，保持项目进度透明
- 定期查看复杂度报告，优化工作计划

## 常见问题

**Q: 如何添加新的任务？**
A: 可以通过 `task-master add` 命令添加，或直接编辑 tasks.json 文件。

**Q: 如何处理任务依赖关系变化？**
A: 使用 `task-master update` 命令更新相关任务。

**Q: API 密钥安全存储在哪里？**
A: 所有密钥存储在项目根目录的 .env 文件中，该文件不会被版本控制系统跟踪。

## 贡献指南

欢迎提交问题报告和功能建议。如需贡献代码，请确保：

1. 代码符合项目编码规范
2. 为新功能编写测试
3. 更新相关文档
4. 提交前运行全部测试

## 许可证

本项目采用 [许可证类型] 许可证。详情请参阅 LICENSE 文件。
