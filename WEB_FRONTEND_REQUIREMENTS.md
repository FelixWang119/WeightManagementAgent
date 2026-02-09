# Web前端需求登记表

> 所有前端调整、优化、新功能需求都记录在此  
> 将来迁移到小程序时，可据此文档复用逻辑

---

## 📅 2026-02-07 - 项目启动

### 基础架构决策
- [x] 技术栈：HTML5 + Vanilla JS + Tailwind CSS (CDN)
- [x] 图表库：Chart.js (CDN)
- [x] 图标库：Font Awesome (CDN)
- [x] 页面结构：AI对话作为首页(index.html)，其他功能通过菜单访问
- [x] 登录方式：模拟登录（简化实现）

### 目录结构
```
static/
├── index.html          # 首页 - AI对话（主界面）✅
├── weight.html         # 体重记录 ✅
├── meal.html           # 饮食记录
├── exercise.html       # 运动记录
├── water.html          # 饮水记录
├── sleep.html          # 睡眠记录
├── report.html         # 数据报告
├── profile.html        # 个人中心
├── login.html          # 登录页 ✅
├── css/
│   ├── base.css        # 基础样式、CSS变量 ✅
│   ├── components.css  # 通用组件样式 ✅
│   └── layout.css      # 布局、导航、菜单 ✅
├── js/
│   ├── api.js          # API封装（所有后端调用）✅
│   ├── auth.js         # 认证管理 ✅
│   ├── utils.js        # 工具函数 ✅
│   ├── components.js   # 通用组件 ✅
│   └── pages/
│       ├── index.js    # 首页逻辑
│       ├── weight.js   # 体重页逻辑
│       └── ...
└── assets/images/      # 静态资源
```

---

## 📅 2026-02-07 - 首页设计需求

### AI对话首页 (index.html)
**类型：** 功能设计  
**优先级：** P0  
**状态：** ✅ 已完成  
**描述：**
- 将AI对话作为主界面
- 顶部显示用户信息和快捷菜单入口
- 中部为对话区域
- 底部为输入框和快捷功能按钮
- 侧边栏/底部导航提供其他功能入口

**技术要点：**
- 流式响应处理（SSE或轮询）- 已实现基础轮询
- 消息历史记录展示 ✅
- 快捷指令按钮（如"记录体重"、"查看今日摄入"）✅
- 语音输入支持（Web Speech API，可选）- 待实现

**页面布局：**
```
┌─────────────────────────────────────┐
│  🤖 AI助手          [☰ 菜单按钮]     │  ← Header
├─────────────────────────────────────┤
│                                     │
│  🤖 你好！今天想聊些什么？           │  ← Chat
│                                     │    Messages
│  👤 我今天吃了...                    │
│                                     │
├─────────────────────────────────────┤
│ [⚖️记体重] [🍽️记饮食] [🏃记运动] [💧记饮水] │  ← Quick Toolbar
├─────────────────────────────────────┤
│ [输入消息...                 ] [发送] │  ← Input Area
└─────────────────────────────────────┘
```

**关联API：**
- `POST /api/chat/send` ✅
- `GET /api/chat/history` ✅
- `GET /api/user/profile` ✅

**迁移到小程序时需注意：**
- 使用 `<scroll-view>` 替代普通div做消息滚动
- 输入框使用小程序原生input组件
- 快捷菜单可改为底部tabBar或侧边抽屉

---

## 📅 2026-02-07 - 登录页设计

### 登录页 (login.html)
**类型：** 功能开发  
**优先级：** P0  
**状态：** ✅ 已完成  
**描述：**
- 简化的模拟登录界面
- 输入任意code即可登录
- 自动跳转到首页
- Token存储到localStorage
- 渐变色背景 + 卡片式布局

**技术要点：**
- 调用 `POST /api/user/login?code=xxx` ✅
- 存储返回的token ✅
- 登录成功后自动跳转 ✅
- 已登录用户自动跳转到首页 ✅

**迁移到小程序时需注意：**
- 替换为 `wx.login()` 获取code
- 调用微信auth.code2Session接口
- Token存储使用 `wx.setStorageSync`

---

## 📅 2026-02-07 - 体重记录页

### 体重记录页 (weight.html)
**类型：** 功能开发  
**优先级：** P0  
**状态：** ✅ 已完成  
**描述：**
- 显示当前体重统计数据（4个卡片）
- 记录新体重表单（体重、体脂率、备注）
- Chart.js趋势图表（7/30/90天切换）
- 历史记录列表（带变化趋势）
- 响应式设计

**技术要点：**
- Chart.js折线图展示体重趋势 ✅
- 统计数据实时计算 ✅
- 表单验证 ✅
- 历史记录倒序展示 ✅

**关联API：**
- `GET /api/weight/stats` ✅
- `POST /api/weight/record` ✅
- `GET /api/weight/history` ✅

**迁移到小程序时需注意：**
- 使用 `<canvas>` 组件绑定Chart.js
- 列表使用 `<scroll-view>`
- 表单使用小程序原生form组件
- 考虑增加滑动删除历史记录功能

---

## 📅 2026-02-07 - 导航菜单设计

### 侧边导航菜单
**类型：** UI组件  
**优先级：** P0  
**状态：** ✅ 已完成  
**描述：**
- 汉堡菜单按钮触发
- 滑出式侧边栏
- 包含所有功能入口
- 显示用户基本信息
- ESC键和点击外部关闭

**菜单项：**
1. 🤖 AI助手（首页）- index.html
2. ⚖️ 体重记录 - weight.html ✅
3. 🍽️ 饮食记录 - meal.html
4. 🏃 运动记录 - exercise.html
5. 💧 饮水记录 - water.html
6. 😴 睡眠记录 - sleep.html
7. 📊 数据报告 - report.html
8. ⚙️ 个人设置 - profile.html
9. 🚪 退出登录

**技术要点：**
- CSS transform实现滑入动画 ✅
- 当前页面高亮 ✅
- 用户信息动态加载 ✅

**迁移到小程序时需注意：**
- 使用小程序 `<navigator>` 组件
- 或整合到app.json的tabBar配置

---

## 📅 2026-02-07 - 样式系统

### CSS变量定义
**类型：** 设计规范  
**优先级：** P0  
**状态：** ✅ 已完成

```css
:root {
  /* 主色调 - 健康蓝 */
  --primary-color: #3498db;
  --primary-light: #5dade2;
  --primary-dark: #2980b9;
  --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  
  /* 功能色 */
  --success-color: #27ae60;
  --warning-color: #f39c12;
  --error-color: #e74c3c;
  --info-color: #3498db;
  
  /* 功能模块色 */
  --weight-color: #e74c3c;
  --meal-color: #f39c12;
  --exercise-color: #27ae60;
  --water-color: #3498db;
  --sleep-color: #9b59b6;
}
```

---

## 📅 日期 - 新增需求模板

### 需求名称
**类型：** [功能增强/bug修复/UI优化/性能优化/新页面]  
**优先级：** [P0-P3]  
**状态：** [待办/进行中/已完成]  
**描述：** 详细描述需求内容  
**关联页面：** 影响的页面列表  
**技术要点：** 实现的关键技术点  
**迁移到小程序时需注意：** 平台差异说明

---

## 📋 开发进度追踪

### 第一阶段：基础设施 ✅
- [x] 创建目录结构
- [x] 创建需求登记文档
- [x] 创建base.css（CSS变量、重置样式）
- [x] 创建components.css（按钮、卡片、表单）
- [x] 创建layout.css（导航、布局）
- [x] 创建api.js（API封装）
- [x] 创建auth.js（认证管理）
- [x] 创建utils.js（工具函数）
- [x] 创建components.js（通用组件）

### 第二阶段：核心页面 ✅
- [x] login.html - 登录页
- [x] index.html - AI对话首页（含导航菜单）
- [x] weight.html - 体重记录页

### 第三阶段：功能页面 ⏳
- [ ] meal.html - 饮食记录（含AI图片识别）
- [ ] exercise.html - 运动记录
- [ ] water.html - 饮水记录
- [ ] sleep.html - 睡眠记录
- [ ] report.html - 数据报告
- [ ] profile.html - 个人中心

---

## 📅 2026-02-07 - AI图片识别功能修复

### 问题修复：智能识别不准且返回过快
**类型：** Bug修复  
**优先级：** P0  
**状态：** ✅ 已完成

**问题描述：**
- 上传照片后AI返回结果太快（1.5秒）
- 识别结果不准确（固定模拟数据）
- 前端使用的是mock数据，未真正调用后端AI

**修复内容：**

#### 1. 后端修改 (`api/routes/meal.py`)
- 修改 `/analyze` 接口真正调用AI服务
- 使用base64编码将图片直接传给AI（无需公开URL）
- 构造专业提示词让AI识别食物并估算热量
- 返回标准JSON格式：`{foods: [...], total_calories, suggestions}`

#### 2. 前端修改 (`static/meal.html`)
- `analyzeImage()` 函数改为真实API调用
- 使用 `FormData` 上传图片文件
- 调用 `POST /api/meal/analyze`
- 解析AI返回的真实数据并显示
- 添加错误处理和用户提示

#### 3. API模块修改 (`static/js/api.js`)
- 更新 `mealAPI.analyzeImage()` 支持文件上传
- 更新 `mealAPI.record()` 适配后端参数

**技术实现：**
```javascript
// 前端调用示例
const formData = new FormData();
formData.append('file', imageFile);
formData.append('meal_type', 'lunch');

const response = await fetch('/api/meal/analyze', {
    method: 'POST',
    headers: { 'Authorization': 'Bearer ' + token },
    body: formData
});
```

**预期效果：**
- AI分析时间：5-15秒（真实AI处理时间）
- 识别准确率：根据照片清晰度，可识别常见中餐
- 返回格式：JSON结构化数据，含食物名称、分量、热量、emoji图标

**注意事项：**
- 需要配置AI服务（OpenAI或Qwen）
- 大图片会先保存到服务器再分析
- 分析失败时会提示用户手动输入

---

## 📅 2026-02-07 - AI每日建议功能增强

### AI建议内容多样化
**类型：** 功能增强  
**优先级：** P1  
**状态：** ✅ 已完成

**需求描述：**
用户反馈AI每日建议全是督促打卡的内容，希望能提供更多科普知识，让建议更加丰富多样。

**修改内容：**

#### 1. 后端 AI Prompt 优化 (`api/routes/chat.py`)
**新增内容类型（随机选择）：**
- 打卡提醒类 (30%) - 温柔提醒记录数据
- 营养科普类 (20%) - 分享营养小知识
- 运动科普类 (20%) - 分享运动知识
- 饮食技巧类 (15%) - 实用饮食技巧
- 代谢/习惯类 (15%) - 代谢知识和习惯养成

**科普主题池：**
- 为什么早餐很重要
- 如何计算基础代谢率
- 什么是低GI食物
- 有氧vs无氧的区别
- 睡眠与减重的关系
- 蛋白质的作用和来源
- 如何识别隐形热量
- 间歇性断食的原理
- 皮质醇与压力性肥胖
- 肌肉量对代谢的影响

**Prompt要求：**
- 不要总是督促打卡，40%概率选择科普/知识分享类
- 语气温暖亲切，像 knowledgeable friend
- 科普内容准确、实用、易懂

#### 2. 前端默认建议更新 (`static/index.html`)
更新 `displayDefaultSuggestion()` 函数，加入科普内容：
```javascript
const defaults = [
    // 打卡提醒类
    { content: "坚持记录是减重的第一步...", ... },
    
    // 营养科普类
    { content: "💡 小知识：蛋白质是肌肉的基石，每餐摄入20-30g为佳", ... },
    { content: "💡 小知识：低GI食物能让血糖更平稳...", ... },
    
    // 运动科普类
    { content: "💡 小知识：快走30分钟约消耗150-200kcal...", ... },
    
    // 饮食技巧类
    { content: "💡 小技巧：细嚼慢咽能增加饱腹感...", ... },
    
    // 代谢/习惯类
    { content: "💡 小知识：基础代谢占每日消耗的60-70%...", ... }
];
```

**效果：**
- 建议内容更加丰富多样
- 不仅督促打卡，还提供实用知识
- 用户能学到减重相关的科学知识
- 提升用户体验和粘性

---

### 第四阶段：优化
- [ ] 响应式适配细节优化
- [ ] 加载状态
- [ ] 错误处理
- [ ] 动画效果

---

## 🚀 使用说明

### 启动应用
1. 确保后端已启动：`python main_new.py`
2. 访问登录页：http://localhost:8000/static/login.html
3. 输入任意代码登录
4. 进入AI对话首页

### 测试功能
- **AI对话**：首页可直接与AI助手对话
- **记录体重**：通过侧边栏进入体重记录页
- **查看趋势**：体重页支持7/30/90天趋势图
- **快捷操作**：首页底部工具栏可快速记录各项数据

---

*最后更新：2026-02-07 17:00*
