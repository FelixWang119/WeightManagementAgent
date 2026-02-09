# API 接口规范文档

## 1. 通用返回格式

所有API必须统一返回以下格式：

```json
{
  "success": true|false,
  "data": {},           // 业务数据
  "message": "string",  // 提示信息（可选）
  "error": "string"     // 错误信息（仅success=false时）
}
```

## 2. 字段命名规范

### 2.1 时间相关
- `created_at` - 创建时间（ISO格式）
- `updated_at` - 更新时间
- `date` - 日期（YYYY-MM-DD）
- `time` - 时间（HH:MM）
- `bed_time` - 入睡时间（ISO格式）
- `wake_time` - 起床时间（ISO格式）

### 2.2 分页相关
- `data` - 数据列表（不是records）
- `count` - 总数量
- `page` - 当前页
- `page_size` - 每页大小
- `total_pages` - 总页数

### 2.3 常用字段
- `id` - 唯一标识
- `user_id` - 用户ID
- `amount` → `amount_ml`（饮水）
- `duration` → `duration_hours` 或 `duration_minutes`
- `weight` - 体重(kg)
- `height` - 身高(cm)

## 3. 列表API统一规范

**请求参数：**
```
GET /api/xxx/list
  ?page=1          // 页码，默认1
  &page_size=20    // 每页数量，默认20
  &start_date=     // 开始日期（可选）
  &end_date=       // 结束日期（可选）
```

**返回格式：**
```json
{
  "success": true,
  "data": [
    {"id": 1, ...},
    {"id": 2, ...}
  ],
  "count": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5
}
```

## 4. 历史记录API规范

**请求：**
```
GET /api/xxx/history
  ?days=7          // 最近N天，默认7
  &limit=50        // 最大数量，默认50
```

**返回：**
```json
{
  "success": true,
  "data": [...],   // 使用data不是records
  "count": 10
}
```

## 5. 前端调用规范

### 5.1 必须使用Auth.check()
```javascript
document.addEventListener('DOMContentLoaded', () => {
  if (!Auth.check()) {
    window.location.href = 'login.html';
    return;
  }
  // 页面初始化...
});
```

### 5.2 处理响应数据
```javascript
// ✅ 正确
const response = await API.xxx.getHistory();
if (response.success && response.data) {
  renderData(response.data);
}

// ❌ 错误 - 使用records
if (response.success && response.records) {
  renderData(response.records);
}
```

### 5.3 POST请求必须序列化
```javascript
// ✅ 正确
await request('/api/xxx/create', {
  method: 'POST',
  body: JSON.stringify(data)
});

// ❌ 错误
await request('/api/xxx/create', {
  method: 'POST',
  body: data  // 没有JSON.stringify
});
```

## 6. 错误码规范

- 200 - 成功
- 400 - 参数错误（字段验证失败）
- 401 - 未授权（token无效）
- 404 - 资源不存在
- 422 - 验证错误（业务逻辑验证失败）
- 500 - 服务器内部错误

## 7. 已修复问题清单

### 7.1 数据路径问题（已修复）
- ✅ water.html: response.records → response.data
- ✅ meal.html: response.records → response.data
- ✅ sleep.html: response.records → response.data

### 7.2 参数名问题（已修复）
- ✅ waterAPI.record: amount → amount_ml
- ✅ sleepAPI.record: 参数格式对齐

### 7.3 缺失Auth.check（已修复）
- ✅ weight.html
- ✅ meal.html
- ✅ exercise.html
- ✅ report.html
- ✅ profile.html
