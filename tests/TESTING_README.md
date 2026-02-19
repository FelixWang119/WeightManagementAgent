# 行为管理教练测试框架使用指南

## 概述

本测试框架专为行为管理教练系统设计，支持：

✅ **时间可控** - 可以模拟任意日期，测试长期习惯养成
✅ **接口驱动** - 所有测试通过HTTP API进行，真实模拟用户交互
✅ **认证模拟** - 支持真实JWT token，模拟真实用户登录
✅ **场景混合** - 支持教练场景和顾问场景穿插测试
✅ **通知监控** - 捕获和验证AI主动发送的通知

## 快速开始

### 1. 环境准备

确保服务已启动：

```bash
# 在项目根目录
cd /Users/felix/open_workdspace
./start.sh start
```

### 2. 运行完整测试

```bash
# 运行习惯生命周期测试（含主动通知）
cd /Users/felix/open_workdspace
source venv/bin/activate
python tests/scenarios/test_habit_lifecycle_with_notifications.py
```

预期输出：
```
======================================================================
习惯生命周期测试（含主动通知）
======================================================================

场景: 习惯生命周期+主动通知测试
步骤数: 25
期望通知: 1

[步骤 1/25] 用户表达目标
✅ AI回复: 好！已帮你创建每天喝8杯水的习惯打卡...
🔧 工具调用: ['create_habit_tool']

[步骤 2/25] 验证习惯创建
✅ 成功

[步骤 3/25] 穿越到第2天
✅ 时间已设置为: 2024-01-02

[步骤 4/25] 第2天喝水打卡
✅ AI回复: 已记录！今天喝了600ml水...
🔧 工具调用: ['record_water_tool']

...

🎯 第7天：验证AI主动通知
✅ 捕获到主动通知: [proactive_guidance] 恭喜你坚持喝水一周了！
通知内容: "你已经坚持喝水一周了，真棒！要不要考虑开始每天称重，全面跟踪你的健康变化？"

测试报告已保存: test_reports/habit_lifecycle_20240101_120000.json
======================================================================
测试结果
======================================================================
状态: ✅ 通过
总耗时: 45.32 秒
总步骤: 25

通知统计:
  捕获总数: 1
  按类型: {'proactive_guidance': 1}

捕获的通知:
  [16:32:15] [proactive_guidance] system: 恭喜你坚持喝水一周了！要不要考虑开始每天称重...
```

## 框架核心组件

### 1. 时间穿越服务 (`tests/framework/time_travel.py`)

#### 基本用法

```python
from tests.framework.time_travel import TimeTravelClock, today, now

# 获取当前日期（支持时间穿越）
current_date = today()  # 替代 date.today()
current_datetime = now()  # 替代 datetime.now()

# 在测试中冻结时间
TimeTravelClock.enable_test_mode()
TimeTravelClock.set_frozen_time("2024-01-15")

print(today())  # 输出: 2024-01-15

# 相对偏移（前进7天）
TimeTravelClock.set_offset_days(7)
print(today())  # 输出: 2024-01-22

# 重置
TimeTravelClock.reset()
TimeTravelClock.disable_test_mode()
```

#### 上下文管理器（推荐）

```python
from tests.framework.time_travel import travel_to, offset_time

# 临时冻结时间
with travel_to("2024-03-01"):
    print(today())  # 2024-03-01
    # 执行测试...

# 退出上下文后自动恢复
print(today())  # 恢复真实时间

# 临时偏移
with offset_time(days=10):
    print(today())  # 当前日期 + 10天
```

### 2. 测试运行器 (`tests/framework/test_runner.py`)

#### 基本使用

```python
import asyncio
from tests.framework.test_runner import BehavioralTestRunner

async def run_test():
    async with BehavioralTestRunner() as runner:
        # 登录用户
        user = await runner.login_user("test_user_001")
        print(f"登录成功: {user.nickname} (ID: {user.id})")
        
        # 发送消息
        result = await runner.send_chat_message("今天体重65kg")
        print(f"AI回复: {result['response']}")
        print(f"工具调用: {result['tools_used']}")

# 运行
asyncio.run(run_test())
```

#### 完整场景测试

```python
import asyncio
from datetime import date
from tests.framework.test_runner import (
    BehavioralTestRunner, TestScenario, InteractionStep, StepType
)

async def test_scenario():
    # 创建场景
    scenario = TestScenario(
        name="我的测试场景",
        description="测试喝水习惯",
        user_code="test_user",
        initial_date=date(2024, 1, 1)
    )
    
    # 添加步骤
    scenario.add_step(InteractionStep(
        name="创建习惯",
        type=StepType.CHAT,
        message="我想养成喝水习惯"
    ))
    
    scenario.add_step(InteractionStep(
        name="第2天打卡",
        type=StepType.TIME_TRAVEL,
        target_date=date(2024, 1, 2)
    ))
    
    scenario.add_step(InteractionStep(
        name="喝水打卡",
        type=StepType.CHAT,
        message="喝了500ml水"
    ))
    
    # 运行
    async with BehavioralTestRunner() as runner:
        result = await runner.run_scenario(scenario)
        print(f"测试{'通过' if result.success else '失败'}")

asyncio.run(test_scenario())
```

### 3. 通知监控器 (`tests/framework/notification_watcher.py`)

#### 基本监控

```python
import asyncio
from tests.framework.notification_watcher import NotificationWatcher

async def watch_notifications():
    watcher = NotificationWatcher()
    
    try:
        # 开始监控（用户ID为1）
        await watcher.start_watching(user_id=1)
        
        # 等待30秒
        print("监控30秒...")
        await asyncio.sleep(30)
        
        # 获取通知
        notifications = watcher.get_notifications()
        print(f"捕获到 {len(notifications)} 条通知")
        
        for notif in notifications:
            print(f"[{notif.type}] {notif.message}")
    
    finally:
        await watcher.stop_watching()

asyncio.run(watch_notifications())
```

#### 等待特定通知

```python
# 等待主动通知（最多10秒）
notification = await watcher.wait_for_notification(
    notif_type="proactive_guidance",
    timeout=10.0
)

if notification:
    print(f"收到通知: {notification.message}")
else:
    print("超时，未收到通知")
```

## 测试场景示例

### 示例1：习惯养成 + 主动通知

```python
# tests/scenarios/test_habit_with_proactive_notification.py

from datetime import date
from tests.framework.test_runner import (
    TestScenario, InteractionStep, StepType, NotificationExpectation
)

# 创建场景
scenario = TestScenario(
    name="习惯养成+主动通知",
    description="测试用户养成习惯后AI主动通知",
    user_code="test_user",
    initial_date=date(2024, 1, 1)
)

# 连续打卡7天
for day in range(1, 8):
    scenario.add_step(InteractionStep(
        name=f"第{day}天打卡",
        type=StepType.TIME_TRAVEL,
        target_date=date(2024, 1, day)
    ))
    
    scenario.add_step(InteractionStep(
        name=f"喝水打卡",
        type=StepType.CHAT,
        message=f"喝了{day*200}ml水"
    ))

# 期望AI在第7天发送主动通知
scenario.expected_notifications.append(NotificationExpectation(
    type="proactive_guidance",
    contains_text=["坚持", "一周", "新习惯"],
    timeout_seconds=10
))
```

### 示例2：混合场景测试

```python
# 教练场景：创建习惯
scenario.add_coaching_flow("我想养成运动习惯")

# 顾问场景：查询数据
scenario.add_advisor_flow("今天体重多少")

# 教练场景：用户坚持不住
scenario.add_step(InteractionStep(
    name="用户表达困难",
    type=StepType.CHAT,
    message="最近工作太忙，坚持不下去了"
))

scenario.add_step(InteractionStep(
    name="验证AI给予鼓励",
    type=StepType.VERIFY,
    verification_type="response_contains",
    expected_keywords=["鼓励", "支持", "调整", "小目标"]
))
```

## 高级功能

### 自定义验证

```python
async def custom_verification(runner, params):
    """自定义验证函数"""
    # 查询数据库或调用API验证
    result = await runner.send_chat_message("我的统计数据")
    
    return {
        "success": "坚持" in result["response"],
        "data": result
    }

# 在场景中使用
scenario.add_step(InteractionStep(
    name="自定义验证",
    type=StepType.CUSTOM,
    custom_func=custom_verification,
    custom_params={"check": "streak"}
))
```

### 批量测试

```python
# tests/run_multiple_scenarios.py

import asyncio
from tests.scenarios import (
    test_habit_lifecycle_with_notifications,
    test_weight_management,
    test_exercise_tracking
)

async def run_all():
    results = {}
    
    # 运行多个场景
    results["habit"] = await test_habit_lifecycle_with_notifications.main()
    results["weight"] = await test_weight_management.main()
    results["exercise"] = await test_exercise_tracking.main()
    
    # 统计
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    print(f"\n{'='*60}")
    print(f"批量测试完成: {passed}/{total} 通过")
    print(f"{'='*60}")

asyncio.run(run_all())
```

## 测试报告

框架自动生成详细的测试报告：

```bash
# 报告位置
test_reports/
├── habit_lifecycle_20240101_120000.json
├── weight_management_20240101_121500.json
└── notification_flow_20240101_123000.json
```

报告内容：

```json
{
  "test_run_id": "habit_lifecycle_20240101_120000",
  "timestamp": "2024-01-01T12:00:00",
  "scenario": {
    "name": "习惯生命周期+主动通知测试",
    "description": "...",
    "steps_count": 25
  },
  "results": {
    "success": true,
    "duration": 45.32,
    "steps": [
      {
        "step": "用户表达目标",
        "success": true,
        "duration": 2.15
      }
    ],
    "tools_called": ["create_habit_tool", "record_water_tool"],
    "notifications": [
      {
        "type": "proactive_guidance",
        "message": "恭喜你坚持喝水一周了！"
      }
    ]
  }
}
```

## 最佳实践

### 1. 测试命名规范

```python
# 场景名称: [功能]_[场景]_[期望结果]
scenario = TestScenario(
    name="habit_create_then_proactive_notify_on_day7",
    description="用户创建习惯后，AI在第7天主动通知扩展"
)
```

### 2. 步骤命名清晰

```python
# 好的命名
scenario.add_step(InteractionStep(
    name="user_creates_water_habit",  # 动作+对象
    type=StepType.CHAT,
    message="我想养成喝水习惯"
))

# 不好的命名
scenario.add_step(InteractionStep(
    name="step_1",  # 不清晰
    type=StepType.CHAT,
    message="我想养成喝水习惯"
))
```

### 3. 添加详细注释

```python
# 场景说明
scenario = TestScenario(
    name="habit_with_interruption_recovery",
    description="""
    测试场景：
    1. 用户创建喝水习惯
    2. 连续打卡5天
    3. 中断2天（未打卡）
    4. AI主动询问是否继续
    5. 用户恢复打卡
    期望：AI能够识别中断并提供恢复建议
    """
)
```

### 4. 验证要全面

```python
# 不仅验证成功，还要验证内容
scenario.add_step(InteractionStep(
    name="验证AI回复包含鼓励",
    type=StepType.VERIFY,
    verification_type="response_contains",
    expected_keywords=["鼓励", "支持", "调整"]  # 不仅仅是"成功"
))
```

### 5. 测试数据清理

```python
# 测试前准备
def setup():
    # 创建测试用户
    # 清理旧数据
    pass

# 测试后清理
def teardown():
    # 删除测试用户
    # 清理测试数据
    pass
```

## 常见问题

### Q1: 时间穿越后，数据库里的时间也变吗？

**A**: 是的，如果代码中使用 `TimeTravelClock.today()`，那么所有时间相关操作都会使用虚拟时间。这包括：
- 新记录的创建时间
- 查询的时间范围
- 统计数据的时间维度

### Q2: 如何调试测试失败？

**A**: 启用详细日志：

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("tests.framework").setLevel(logging.DEBUG)
```

### Q3: 测试运行太慢怎么办？

**A**: 
1. 减少等待时间：`wait_seconds` 设置为较小值
2. 并行运行测试（需要确保测试之间不冲突）
3. 使用模拟数据而非真实API调用（不推荐，会降低测试真实性）

### Q4: 通知监控收不到通知？

**A**:
1. 确保服务器支持SSE通知
2. 检查用户ID是否正确
3. 确认通知确实已发送（查看服务器日志）
4. 增加超时时间：`timeout_seconds=20`

### Q5: 如何在CI/CD中运行？

**A**: 在GitHub Actions/GitLab CI中：

```yaml
# .github/workflows/test.yml
name: Run Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Start services
        run: ./start.sh start
      
      - name: Run tests
        run: |
          source venv/bin/activate
          python tests/scenarios/test_habit_lifecycle_with_notifications.py
      
      - name: Upload reports
        uses: actions/upload-artifact@v2
        with:
          name: test-reports
          path: test_reports/
```

## 扩展框架

### 添加新步骤类型

```python
# tests/framework/test_runner.py

class StepType(Enum):
    LOGIN = "login"
    CHAT = "chat"
    TIME_TRAVEL = "time_travel"
    VERIFY = "verify"
    RECORD_DATA = "record_data"
    EXPECT_NOTIFICATION = "expect_notification"
    WAIT = "wait"
    CUSTOM = "custom"
    NEW_STEP = "new_step"  # 添加新类型

# 在执行步骤中添加处理
async def execute_step(self, step: InteractionStep):
    if step.type == StepType.NEW_STEP:
        # 处理新步骤
        result = await self.handle_new_step(step)
        return result

async def handle_new_step(self, step: InteractionStep):
    """处理新步骤类型"""
    # 实现新步骤逻辑
    pass
```

### 添加新验证类型

```python
# 在 verify_step 方法中添加
async def verify_step(self, step: InteractionStep):
    if step.verification_type == "new_verification":
        # 新验证逻辑
        return {
            "success": True,
            "message": "新验证通过"
        }
```

## 相关文档

- [测试框架设计](./TEST_FRAMEWORK_DESIGN.md) - 详细设计文档
- [时间迁移指南](./framework/TIME_MIGRATION_GUIDE.md) - 如何改造现有代码
- [API文档](./API_REFERENCE.md) - 完整的API接口文档

## 获取帮助

如果遇到问题：

1. 查看日志：`logs/app.log` 和 `logs/test.log`
2. 运行快速测试：`python tests/framework/test_runner.py`
3. 检查时间服务：`python tests/framework/time_travel.py`
4. 提交Issue到项目仓库
