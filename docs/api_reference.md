# API 接口参考手册

> 📌 **编程助手注意**：修改接口前请先查阅本手册  
> 🔄 **Swagger实时文档**：启动服务后访问 `/docs`  
> 📋 **契约规范**：[API契约文档](api_contract.md)

## 🎯 编程助手必读

**重要提示**：在修改任何API代码前，请务必：
1. **先查看本手册** - 了解现有接口定义和规范
2. **检查API契约** - 确保遵循通用规范
3. **测试接口变更** - 使用Swagger文档进行验证
4. **更新前端调用** - 确保前后端API契约一致

## 🚀 快速导航

| 模块 | 基础路径 | 主要功能 | 文件位置 |
|------|---------|---------|----------|
| 👤 用户 | `/api/user` | 登录、档案、偏好设置 | `api/routes/user.py` |
| ⚖️ 体重 | `/api/weight` | 记录、历史、趋势 | `api/routes/weight.py` |
| 🏃 运动 | `/api/exercise` | 打卡、消耗、统计 | `api/routes/exercise.py` |
| 🍽️ 饮食 | `/api/meal` | 记录、AI识别、营养 | `api/routes/meal.py` |
| 💧 饮水 | `/api/water` | 记录、目标、提醒 | `api/routes/water.py` |
| 😴 睡眠 | `/api/sleep` | 记录、质量分析 | `api/routes/sleep.py` |
| 💬 AI对话 | `/api/chat` | 聊天、历史记录 | `api/routes/chat.py` |
| 📊 报告 | `/api/report` | 生成、查看 | `api/routes/report.py` |
| 🔔 提醒 | `/api/reminder` | 设置、通知 | `api/routes/reminder.py` |
| 📈 用户画像 | `/api/profiling` | 分析、偏好 | `api/routes/profiling.py` |
| ⚙️ 配置 | `/api/config` | 系统设置 | `api/routes/config.py` |
| 🔥 热量计算 | `/api/calories` | 计算、消耗 | `api/routes/calories.py` |
| 🎯 目标管理 | `/api/goals` | 设置、进度 | `api/routes/goals.py` |
| 👨‍💼 管理端 | `/admin/*` | 后台管理 | `api/routes/admin/*.py` |

---

## 📋 通用约定

### 认证方式
所有需要认证的接口使用 Bearer Token：
```
Authorization: Bearer {token}
```

### 统一响应格式
```json
{
  "success": true|false,
  "data": {},           // 业务数据
  "message": "string",  // 提示信息（可选）
  "error": "string"     // 错误信息（仅success=false时）
}
```

### 分页参数
```
GET /api/xxx/list?page=1&page_size=20
```

---

## 🔍 详细接口定义

### 1. 用户模块 (`api/routes/user.py`)

#### POST /api/user/login
**用途**：微信小程序登录

**请求体**：
```json
{
  "code": "string"  // wx.login获取的code
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "token": "jwt_token",
    "user_id": 20,
    "is_new": false
  },
  "message": "登录成功"
}
```

**错误码**：
- `400`：参数错误（缺少code）
- `401`：微信授权失败
- `500`：服务器内部错误

---

#### GET /api/user/profile
**用途**：获取用户档案

**请求头**：
```
Authorization: Bearer {token}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "user_id": 20,
    "nickname": "用户d501aa",
    "avatar_url": "string",
    "profile": {
      "height": 170,
      "target_weight": 65.0,
      "birth_date": "1990-01-01"
    }
  }
}
```

---

### 2. 体重模块 (`api/routes/weight.py`)

#### POST /api/weight/record
**用途**：记录体重数据

**请求体**：
```json
{
  "weight": 65.5,
  "body_fat": 20.0,
  "record_date": "2024-01-01",
  "note": "晨起空腹"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "record_id": 123,
    "weight": 65.5,
    "record_date": "2024-01-01"
  },
  "message": "体重记录成功"
}
```

---

#### GET /api/weight/history
**用途**：获取体重历史记录

**查询参数**：
```
GET /api/weight/history?days=7&limit=50
```

**响应**：
```json
{
  "success": true,
  "data": [
    {
      "record_id": 123,
      "weight": 65.5,
      "body_fat": 20.0,
      "record_date": "2024-01-01",
      "created_at": "2024-01-01T08:00:00"
    }
  ],
  "count": 10
}
```

---

### 3. 运动模块 (`api/routes/exercise.py`)

#### POST /api/exercise/record
**用途**：记录运动打卡

**请求体**：
```json
{
  "exercise_type": "跑步",
  "duration_minutes": 30,
  "intensity": "中等",
  "exercise_date": "2024-01-01",
  "note": "晨跑5公里"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "record_id": 456,
    "calories_burned": 300,
    "exercise_date": "2024-01-01"
  },
  "message": "运动记录成功"
}
```

---

#### GET /api/exercise/types
**用途**：获取支持的运动类型

**响应**：
```json
{
  "success": true,
  "data": [
    {"name": "跑步", "calories_per_hour": 600},
    {"name": "快走", "calories_per_hour": 300},
    {"name": "游泳", "calories_per_hour": 500}
  ]
}
```

---

### 4. AI对话模块 (`api/routes/chat.py`)

#### POST /api/chat/message
**用途**：发送消息给AI助手

**请求体**：
```json
{
  "message": "今天应该怎么安排运动？",
  "message_type": "text"
}
```

**响应**（流式响应）：
```json
{
  "success": true,
  "data": {
    "message_id": "msg_123",
    "content": "根据您的体重目标，建议今天安排30分钟有氧运动...",
    "timestamp": "2024-01-01T10:00:00"
  }
}
```

---

#### GET /api/chat/history
**用途**：获取聊天历史

**查询参数**：
```
GET /api/chat/history?page=1&page_size=20
```

---

### 5. 饮食模块 (`api/routes/meal.py`)

#### POST /api/meal/record
**用途**：记录餐食

**请求体**（multipart/form-data）：
- `meal_type`: "breakfast" | "lunch" | "dinner" | "snack"
- `food_items`: JSON字符串，格式：`[{"name": "米饭", "amount": 150}, {"name": "炒青菜", "amount": 200}]`
- `image`: 餐食图片（可选）
- `meal_time`: "2024-01-01T12:00:00"

**响应**：
```json
{
  "success": true,
  "data": {
    "meal_id": 789,
    "total_calories": 450,
    "meal_time": "2024-01-01T12:00:00"
  }
}
```

---

### 6. 饮水模块 (`api/routes/water.py`)

#### POST /api/water/record
**用途**：记录饮水

**请求体**：
```json
{
  "amount_ml": 250
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "record_id": 101,
    "amount_ml": 250,
    "record_time": "2024-01-01T10:30:00"
  }
}
```

---

### 7. 睡眠模块 (`api/routes/sleep.py`)

#### POST /api/sleep/record
**用途**：记录睡眠数据

**请求体**：
```json
{
  "bed_time": "22:30",
  "wake_time": "06:30", 
  "sleep_quality": 4,
  "sleep_date": "2024-01-01"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "record_id": 202,
    "sleep_hours": 8.0,
    "sleep_date": "2024-01-01"
  }
}
```

---

## 🎯 管理端接口

### 认证模块 (`api/routes/admin/auth.py`)

#### POST /admin/auth/login
**用途**：管理员登录

**请求体**：
```json
{
  "username": "admin",
  "password": "password123"
}
```

---

### 用户管理 (`api/routes/admin/users.py`)

#### GET /admin/users/list
**用途**：获取用户列表

**查询参数**：
```
GET /admin/users/list?page=1&page_size=20&search=keyword
```

---

## 🔧 开发注意事项

### 1. 参数验证
- 所有参数必须进行类型验证
- 使用Pydantic模型进行复杂参数验证
- 数值参数必须指定范围限制

### 2. 错误处理
- 必须捕获所有可能的异常
- 错误信息必须清晰明确
- 使用统一的错误码规范

### 3. 性能优化
- 避免N+1查询问题
- 合理使用缓存
- 数据库查询使用索引

### 4. 安全性
- 所有敏感操作必须验证权限
- 用户数据隔离
- 输入参数过滤和转义

---

## 📖 相关文档

- [API契约规范](api_contract.md) - 通用规范和约定
- [数据库设计文档](../database_schema.md) - 数据模型说明
- [前端开发规范](../WEB_FRONTEND_REQUIREMENTS.md) - 前端调用规范

---

## 10. 习惯打卡模块 (`api/routes/habit.py`)

### GET /api/habit/streaks
**用途**：获取连续打卡统计

**查询参数**：
- `days`: 统计天数 (7-365, 默认90)

**响应**：
```json
{
  "success": true,
  "data": {
    "weight": {"current_streak": 5, "max_streak": 10, "completion_rate": 71.4},
    "exercise": {"current_streak": 3, "max_streak": 7, "completion_rate": 42.9}
  }
}
```

### GET /api/habit/heatmap
**用途**：获取打卡热力图

### GET /api/habit/progress
**用途**：获取习惯养成进度

### GET /api/habit/dashboard
**用途**：获取习惯打卡仪表盘

---

## 11. 成就积分模块 (`api/routes/achievements.py`)

### GET /api/achievements/achievements
**用途**：获取用户成就列表

### GET /api/achievements/points
**用途**：获取用户积分

**响应**：
```json
{
  "success": true,
  "data": {
    "points": 150,
    "total_points_earned": 200,
    "total_points_spent": 50
  }
}
```

### POST /api/achievements/points/earn
**用途**：获得积分

**请求体**：
```json
{"reason": "连续打卡7天", "amount": 20}
```

### POST /api/achievements/points/spend
**用途**：消费积分

### GET /api/achievements/dashboard
**用途**：获取成就仪表盘

---

## 12. 智能建议模块 (`api/routes/suggestions.py`)

### GET /api/suggestions/suggestions
**用途**：获取智能建议

### GET /api/suggestions/suggestions/context
**用途**：获取上下文建议

### GET /api/suggestions/suggestions/predictive
**用途**：获取预测性建议

### POST /api/suggestions/suggestions/feedback
**用途**：提交建议反馈

### GET /api/suggestions/suggestions/effects
**用途**：获取建议效果统计

---

## 13. 配置管理模块 (`api/routes/config.py`)

### GET /api/config/decision-mode
**用途**：获取用户决策模式

### POST /api/config/decision-mode
**用途**：更新决策模式

**请求体**：
```json
{"decision_mode": "balanced"}
```

**可选值**: `conservative`, `balanced`, `intelligent`

### GET /api/config/context-events
**用途**：获取上下文事件

### GET /api/config/default-suggestions
**用途**：获取默认建议配置

---

## 14. 数据导出模块 (`api/routes/export.py`)

### GET /api/export/export/summary
**用途**：获取导出数据摘要

**查询参数**：
- `start_date`: 开始日期 (YYYY-MM-DD)
- `end_date`: 结束日期 (YYYY-MM-DD)

### POST /api/export/export/excel
**用途**：导出数据到Excel

**请求体**：
```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-02-14",
  "include_types": ["weight", "meal", "exercise", "water", "sleep"]
}
```

### GET /api/export/export/excel/quick
**用途**：快速导出Excel (默认配置)

### GET /api/export/export/test
**用途**：测试导出功能 (最近7天)

---

## 15. AI洞察模块 (`api/routes/insights.py`)

### GET /api/insights/hidden-patterns
**用途**：获取隐藏模式发现

### GET /api/insights/anomalies
**用途**：获取异常检测结果

### GET /api/insights/predictions
**用途**：获取趋势预测

---

## 16. 首页仪表盘模块 (`api/routes/summary.py`)

### GET /api/summary/daily
**用途**：获取每日数据汇总

### GET /api/summary/weekly
**用途**：获取每周数据汇总

---

## 🚨 常见问题

### Q: 接口返回404错误？
A: 检查路由前缀是否正确，如用户模块是`/api/user`不是`/api/users`

### Q: token无效怎么办？
A: 重新调用`/api/user/login`接口获取新token

### Q: 参数验证失败？
A: 检查参数类型和格式，参考各接口的参数说明

### Q: 如何调试接口？
A: 启动服务后访问`/docs`查看Swagger文档，可以直接测试接口

---

*最后更新：2026-02-14*  
*文档版本：v1.2*