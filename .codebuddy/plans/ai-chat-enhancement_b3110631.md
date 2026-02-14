---
name: ai-chat-enhancement
overview: 增强AI对话系统：实现自然语言记录功能和富媒体消息支持
design:
  architecture:
    framework: html
  styleKeywords:
    - 卡片式
    - 渐变背景
    - 快捷操作
    - 微交互动画
  fontSystem:
    fontFamily: PingFang SC
    heading:
      size: 16px
      weight: 600
    subheading:
      size: 14px
      weight: 500
    body:
      size: 14px
      weight: 400
  colorSystem:
    primary:
      - "#667eea"
      - "#764ba2"
    background:
      - "#f5f5f5"
      - "#ffffff"
    text:
      - "#333333"
      - "#666666"
      - "#999999"
    functional:
      - "#28a745"
      - "#ffc107"
      - "#dc3545"
      - "#17a2b8"
todos:
  - id: extend-tools
    content: 扩展services/langchain/tools.py，补充餐食/运动/饮水记录工具
    status: completed
  - id: integrate-tool-calling
    content: 修改services/langchain/agents.py，集成工具调用和自然语言理解
    status: completed
    dependencies:
      - extend-tools
  - id: update-api-response
    content: 修改api/routes/chat.py，支持结构化消息返回
    status: completed
    dependencies:
      - integrate-tool-calling
  - id: frontend-render
    content: 修改static/index.html，实现富媒体消息渲染
    status: completed
    dependencies:
      - update-api-response
  - id: test-integration
    content: 联调测试，验证自然语言记录和富媒体消息功能
    status: completed
    dependencies:
      - frontend-render
---

## 产品概述

实现AI对话系统的两个核心功能：

1. **自然语言记录**：用户通过聊天输入自然语言，AI自动识别意图并记录体重、餐食、运动、饮水等数据
2. **富媒体消息**：AI回复支持卡片消息、快捷按钮等富媒体形式

## 核心功能

### 功能1：自然语言记录

- 用户输入："我今天早上吃了豆浆和油条"
- AI识别意图为"记录早餐" → 解析食物内容 → 调用API创建餐食记录 → 返回确认消息
- 支持记录类型：体重、餐食（早/午/晚/加餐）、运动、饮水

### 功能2：富媒体消息

- **卡片消息**：展示数据统计（今日摄入、运动消耗等）
- **快捷按钮**：消息下方显示操作按钮（确认/修改/查看详情）
- **结构化响应**：AI返回JSON格式，前端根据类型渲染不同UI

## 功能边界

- 复用现有LangChain Agent架构
- 扩展现有工具定义（services/langchain/tools.py）
- 修改API响应格式支持结构化消息
- 前端index.html支持渲染富媒体消息

## 技术栈选择

- **后端**：Python + LangChain + FastAPI（现有架构）
- **前端**：原生HTML + CSS + JavaScript（现有架构）
- **AI模型**：OpenAI GPT / 通义千问（现有配置）

## 实现方案

### 架构设计

```
用户输入自然语言
    ↓
LangChain Agent（带工具调用）
    ↓
意图识别 → 工具选择 → 执行记录 → 生成回复
    ↓
返回结构化消息 {type, content, actions, data}
    ↓
前端根据type渲染（文本/卡片/按钮）
```

### 关键修改点

**1. 后端工具扩展**（services/langchain/tools.py）

- 补充 `record_meal`、`record_exercise`、`record_water` 工具
- 完善工具描述，增强AI意图识别能力
- 添加自然语言解析辅助函数

**2. Agent集成工具调用**（services/langchain/agents.py）

- 修改 `chat_with_agent` 函数，使用工具调用模式
- 集成 OpenAI Function Calling 或 LangChain Tool Calling
- 支持返回结构化响应（包含actions和data）

**3. API响应格式**（api/routes/chat.py）

- 修改 `/api/chat/send` 返回格式
- 支持 `message_type`: "text" | "card" | "actions"
- 新增 `actions` 字段用于快捷按钮

**4. 前端渲染**（static/index.html + static/js/api.js）

- 修改 `appendMessage()` 支持多种消息类型
- 新增卡片渲染函数
- 新增快捷按钮绑定逻辑

### 目录结构

```
services/langchain/
├── tools.py          # [MODIFY] 补充记录工具
├── agents.py         # [MODIFY] 集成工具调用
└── base.py           # [EXISTING] 复用

api/routes/
└── chat.py           # [MODIFY] 支持结构化响应

static/
├── index.html        # [MODIFY] 渲染富媒体消息
└── js/
    └── api.js        # [MODIFY] 消息类型处理
```

### 响应数据格式

```
{
  "success": true,
  "data": {
    "content": "已为您记录早餐：豆浆、油条，约350千卡",
    "role": "assistant",
    "message_type": "card",
    "card_data": {
      "type": "meal_record",
      "meal_type": "breakfast",
      "items": ["豆浆", "油条"],
      "calories": 350
    },
    "actions": [
      {"text": "确认", "action": "confirm", "type": "primary"},
      {"text": "修改", "action": "edit", "type": "secondary"}
    ]
  }
}
```

## 设计概述

保持与现有index.html一致的视觉风格，新增富媒体消息组件。

### 消息类型设计

**1. 文本消息（现有）**

- 普通对话气泡
- 白底黑字，圆角边框

**2. 卡片消息（新增）**

- 渐变背景（蓝紫/粉橙根据类型）
- 圆角16px，阴影效果
- 展示结构化数据（图标+数值+标签）

**3. 快捷按钮（新增）**

- 位于消息下方
- 胶囊形状按钮
- 主操作（实心）/ 次操作（描边）

### 交互设计

- 卡片加载时淡入动画
- 按钮悬停上浮效果
- 点击按钮触发对应操作