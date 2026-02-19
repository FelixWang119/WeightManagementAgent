# 成就与积分系统集成示例

## 已完成的核心功能

### 1. 数据库模型
- ✅ `PointsHistory` 表 - 积分历史记录
- ✅ `UserProfile` 表已包含成就和积分字段

### 2. 服务层
- ✅ `achievement_service.py` - 成就和积分服务（已增强）
- ✅ `integration_service.py` - 业务集成服务
- ✅ `leaderboard_service.py` - 排行榜服务
- ✅ `daily_summary.py` - 每日汇总任务

### 3. API路由
- ✅ `achievements.py` - 成就和积分API（已添加排行榜）
- ✅ `tasks.py` - 任务管理API

### 4. 集成示例
- ✅ `weight.py` - 体重记录API集成示例

## 集成指南

### 1. 导入集成服务
在每个业务API文件中添加：
```python
from services.integration_service import AchievementIntegrationService
```

### 2. 修改记录接口
在保存记录后调用集成服务：

```python
# 保存记录后
record_id = record.id  # 获取记录ID

# 处理成就和积分
achievement_results = await AchievementIntegrationService.process_weight_record(
    current_user.id, record_id, db
)

# 在响应中添加成就和积分信息
response_data = {
    "success": True,
    "message": "记录成功",
    "data": {
        "id": record_id,
        # ... 其他数据
    }
}

if achievement_results["points_earned"] > 0:
    response_data["data"]["points_earned"] = achievement_results["points_earned"]

if achievement_results["achievements_unlocked"]:
    response_data["data"]["achievements_unlocked"] = achievement_results["achievements_unlocked"]

return response_data
```

### 3. 支持的集成方法

| 业务类型 | 集成方法 | 功能 |
|---------|---------|------|
| 体重记录 | `process_weight_record()` | 积分+成就检查 |
| 饮食记录 | `process_meal_record()` | 积分+成就检查 |
| 运动记录 | `process_exercise_record()` | 积分+成就检查 |
| 饮水记录 | `process_water_record()` | 积分+成就检查 |
| 睡眠记录 | `process_sleep_record()` | 积分+成就检查 |
| 每日打卡 | `process_daily_checkin()` | 登录积分+连续打卡 |

### 4. 成就规则

#### 自动检查的成就：
- **首次记录** - 任何类型的首次记录
- **累计记录** - 体重、饮食、运动等累计次数
- **连续打卡** - 7天、30天、100天
- **体重目标** - 达成减重目标
- **热量控制** - 连续7天热量达标
- **饮水达标** - 连续30天饮水达标
- **睡眠达标** - 连续14天睡眠达标
- **完美一周** - 一周内完成所有类型记录
- **早起鸟儿** - 连续一周早上记录

### 5. 积分规则

#### 自动发放的积分：
- **每日登录** +5分（每天首次）
- **记录体重** +10分
- **记录饮食** +5分（每餐）
- **记录运动** +10分
- **饮水达标** +5分（每天）
- **记录睡眠** +5分
- **连续7天打卡** +50分
- **连续30天打卡** +200分
- **连续100天打卡** +500分
- **达成体重目标** +300分

### 6. API端点

#### 成就和积分API：
- `GET /api/achievements/achievements` - 获取用户成就
- `GET /api/achievements/points` - 获取用户积分
- `POST /api/achievements/points/earn` - 获得积分
- `POST /api/achievements/points/spend` - 消费积分
- `GET /api/achievements/points/history` - 积分历史
- `GET /api/achievements/dashboard` - 成就仪表盘

#### 排行榜API：
- `GET /api/achievements/leaderboard/points` - 积分排行榜
- `GET /api/achievements/leaderboard/achievements` - 成就排行榜
- `GET /api/achievements/leaderboard/streak` - 连续打卡榜
- `GET /api/achievements/leaderboard/my-rank` - 我的排名

#### 任务API：
- `POST /api/tasks/daily-summary` - 手动触发每日汇总
- `POST /api/tasks/daily-summary/all` - 触发全量汇总（管理员）

## 使用示例

### 1. 记录体重并自动获得积分
```bash
curl -X POST http://localhost:8000/api/weight/record \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"weight": 70.5}'
```

响应示例：
```json
{
  "success": true,
  "message": "体重记录成功",
  "data": {
    "id": 123,
    "weight": 70.5,
    "record_date": "2025-02-19",
    "is_new_record": true,
    "points_earned": 10,
    "achievements_unlocked": [
      {
        "id": "first_step",
        "name": "第一步",
        "icon": "🎯",
        "points": 10,
        "rarity": "common"
      }
    ]
  }
}
```

### 2. 查看成就排行榜
```bash
curl -X GET http://localhost:8000/api/achievements/leaderboard/achievements \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. 手动触发每日汇总
```bash
curl -X POST http://localhost:8000/api/tasks/daily-summary \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 数据库迁移

需要运行数据库迁移来创建PointsHistory表：

```bash
# 生成迁移文件
alembic revision --autogenerate -m "add points_history table"

# 应用迁移
alembic upgrade head
```

## 注意事项

1. **错误处理**：所有集成点都有try-except包裹，不会影响主流程
2. **性能考虑**：排行榜查询可能需要优化（添加索引）
3. **并发处理**：成就检查和积分发放考虑并发情况
4. **日志记录**：所有关键操作都有日志记录，便于调试
5. **扩展性**：成就和积分规则可轻松扩展

## 测试建议

1. 运行现有测试确保不破坏现有功能
2. 测试成就解锁逻辑
3. 测试积分发放和消费
4. 测试排行榜查询性能
5. 测试每日汇总任务