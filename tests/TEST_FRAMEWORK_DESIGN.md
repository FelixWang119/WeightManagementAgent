# 行为管理教练测试框架设计

## 核心需求实现方案

### 1. 时间可控性（时间穿越）

**问题**：代码中大量使用 `date.today()` 和 `datetime.now()`，无法模拟不同日期场景

**解决方案**：
- 创建 `TimeTravelClock` 服务，统一时间获取入口
- 通过环境变量或请求头控制当前时间
- 在测试模式下，所有时间相关操作都通过TimeTravelClock获取

```python
# 时间服务设计
class TimeTravelClock:
    """时间穿越时钟 - 测试时可控制时间"""
    
    _frozen_time = None  # 冻结的时间
    _offset_days = 0     # 相对偏移天数
    
    @classmethod
    def set_frozen_time(cls, target_date: date):
        """冻结到指定日期"""
        cls._frozen_time = target_date
    
    @classmethod  
    def set_offset_days(cls, offset: int):
        """设置相对偏移（正数=未来，负数=过去）"""
        cls._offset_days = offset
        cls._frozen_time = None
    
    @classmethod
    def reset(cls):
        """重置为真实时间"""
        cls._frozen_time = None
        cls._offset_days = 0
    
    @classmethod
    def today(cls) -> date:
        """获取当前日期（测试时可能返回模拟日期）"""
        if cls._frozen_time:
            return cls._frozen_time
        elif cls._offset_days != 0:
            return date.today() + timedelta(days=cls._offset_days)
        return date.today()
```

**改造代码**：
需要替换所有 `date.today()` 为 `TimeTravelClock.today()`

### 2. 接口驱动测试

**设计原则**：
- 所有测试操作都通过HTTP API接口完成
- 不直接操作数据库
- 真实模拟用户端到端交互

**测试运行器架构**：
```python
class BehavioralTestRunner:
    """行为管理教练测试运行器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.user_simulator = UserSimulator(base_url)
        self.time_travel = TimeTravelController(base_url)
        self.notification_watcher = NotificationWatcher(base_url)
        
    async def run_test_scenario(self, scenario: TestScenario):
        """运行测试场景"""
        # 1. 设置时间
        if scenario.initial_date:
            await self.time_travel.set_date(scenario.initial_date)
        
        # 2. 创建用户并登录
        user = await self.user_simulator.login(scenario.user_code)
        assert user is not None, "登录失败"
        
        # 3. 运行交互步骤
        for step in scenario.steps:
            result = await self.execute_step(step, user)
            assert result.success, f"步骤失败: {step.name}"
        
        # 4. 验证通知
        if scenario.expected_notifications:
            notifications = await self.notification_watcher.get_notifications()
            self.verify_notifications(notifications, scenario.expected_notifications)
```

### 3. 真实认证模拟

**实现方案**：
- 使用JWT TokenManager生成真实token
- 支持用户登录接口获取token
- 所有API调用都携带认证头

```python
# 认证流程
async def login_user(self, user_code: str) -> TestUser:
    """登录用户并获取真实token"""
    response = await self.http.post(
        f"{self.base_url}/api/user/login",
        params={"code": user_code}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"]
    
    # 创建测试用户对象
    return TestUser(
        id=data["user"]["id"],
        nickname=data["user"]["nickname"],
        token=data["token"],  # JWT令牌
        code=user_code
    )

# 使用token调用API
headers = {"Authorization": f"Bearer {user.token}"}
response = await self.http.post(
    f"{self.base_url}/api/chat/send",
    headers=headers,
    json={"message": message}
)
```

### 4. 场景混合测试

**测试场景定义**：
```python
@dataclass
class TestScenario:
    """测试场景 - 混合教练和顾问交互"""
    
    name: str  # 场景名称
    description: str  # 场景描述
    user_code: str  # 测试用户
    initial_date: date  # 起始日期
    
    steps: List[InteractionStep]  # 交互步骤
    expected_notifications: List[NotificationExpectation]  # 期望通知
    
    def add_coaching_flow(self):
        """添加教练引导流程"""
        self.steps.extend([
            InteractionStep(
                type="chat",
                action="用户表达目标",
                input="我想养成每天喝水的习惯"
            ),
            InteractionStep(
                type="verify",
                action="验证习惯创建",
                expected_tools=["create_habit_tool"]
            )
        ])
    
    def add_advisor_flow(self):
        """添加顾问咨询流程"""
        self.steps.extend([
            InteractionStep(
                type="chat",
                action="用户查询数据",
                input="今天体重多少"
            ),
            InteractionStep(
                type="verify",
                action="验证数据查询"
            )
        ])
```

**完整场景示例**：
```python
# 场景：用户养成习惯过程中咨询数据
scenario = TestScenario(
    name="习惯养成+数据查询混合场景",
    description="测试用户在养成喝水习惯的同时查询体重数据",
    user_code="test_user_001",
    initial_date=date(2024, 1, 1)
)

# 第1天：用户想养成习惯（教练场景）
scenario.add_step(chat("我想养成喝水习惯"))
scenario.add_step(verify_tools(["create_habit_tool"]))

# 第2-7天：每天打卡（混合场景）
for day in range(2, 8):
    scenario.add_step(time_travel_to(date(2024, 1, day)))
    scenario.add_step(chat(f"今天喝了{day*200}ml水"))
    scenario.add_step(verify_tools(["record_water_tool"]))
    
    # 穿插顾问咨询（每3天问一次体重）
    if day % 3 == 0:
        scenario.add_step(chat("今天体重多少"))

# 第8天：AI主动通知用户扩展习惯
scenario.add_step(time_travel_to(date(2024, 1, 8)))
scenario.add_step(expect_notification(
    type="proactive_guidance",
    contains="坚持一周了",
    suggests="是否开始称重"
))
```

### 5. 通知模拟与响应

**通知监控器**：
```python
class NotificationWatcher:
    """通知监控器 - 捕获和验证主动通知"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.captured_notifications = []
    
    async def start_watching(self, user_id: int):
        """开始监控用户的通知"""
        # 连接到SSE端点监听通知
        self.sse_client = await self.connect_sse(
            f"{self.base_url}/api/sse/notifications?user_id={user_id}"
        )
        
        # 在后台任务中监听
        asyncio.create_task(self._listen_notifications())
    
    async def _listen_notifications(self):
        """监听通知事件"""
        async for event in self.sse_client.events():
            if event.type == "notification":
                notification = json.loads(event.data)
                self.captured_notifications.append({
                    "timestamp": datetime.now(),
                    "data": notification
                })
    
    def get_notifications(self, since: datetime = None) -> List[Dict]:
        """获取捕获的通知"""
        if since:
            return [n for n in self.captured_notifications 
                   if n["timestamp"] >= since]
        return self.captured_notifications
```

**通知响应测试**：
```python
# 测试通知响应流程
async def test_notification_response():
    """测试用户收到通知后的响应"""
    
    # 1. 触发主动通知（例如：用户连续打卡7天）
    result = await runner.chat("今天也完成喝水目标了，已经坚持一周了！")
    
    # 2. 验证AI发送了主动通知
    notifications = watcher.get_notifications()
    assert len(notifications) > 0
    assert "坚持一周" in notifications[0]["data"]["message"]
    
    # 3. 用户响应通知（接受建议）
    response = await runner.chat("好的，那我也开始每天称重吧")
    
    # 4. 验证AI创建了新的习惯
    assert "create_habit_tool" in response.tools_used
```

## 测试框架目录结构

```
tests/
├── framework/                      # 测试框架核心
│   ├── __init__.py
│   ├── test_runner.py             # 测试运行器
│   ├── time_travel.py             # 时间穿越服务
│   ├── notification_watcher.py    # 通知监控器
│   └── scenario_builder.py        # 场景构建器
│
├── scenarios/                      # 测试场景定义
│   ├── __init__.py
│   ├── test_habit_lifecycle.py    # 习惯生命周期测试
│   ├── test_mixed_scenes.py       # 混合场景测试
│   ├── test_notification_flow.py  # 通知流程测试
│   └── test_proactive_guidance.py # 主动引导测试
│
├── utils/                          # 测试工具
│   ├── __init__.py
│   ├── auth_helper.py             # 认证辅助
│   ├── api_client.py              # API客户端
│   └── assertion_helper.py        # 断言辅助
│
└── run_all_tests.py               # 运行所有测试
```

## 关键特性

### 1. 时间穿越
- ✅ 支持冻结到指定日期
- ✅ 支持相对偏移（前进/后退N天）
- ✅ 自动应用于所有时间相关操作
- ✅ 可恢复真实时间

### 2. 接口驱动
- ✅ 所有操作通过HTTP API
- ✅ 真实认证token
- ✅ 端到端验证
- ✅ 不绕过业务逻辑

### 3. 认证模拟
- ✅ 生成真实JWT token
- ✅ 支持用户登录接口
- ✅ 自动携带认证头
- ✅ 支持多用户并发测试

### 4. 场景混合
- ✅ 教练场景（习惯创建、引导）
- ✅ 顾问场景（数据查询、记录）
- ✅ 自然切换和穿插
- ✅ 验证工具调用

### 5. 通知测试
- ✅ 监控主动通知
- ✅ 验证通知内容
- ✅ 模拟用户响应
- ✅ 验证后续交互

## 测试运行示例

```bash
# 运行所有测试
python tests/run_all_tests.py

# 运行指定场景
python tests/run_all_tests.py --scenario habit_lifecycle

# 指定日期范围测试
python tests/run_all_tests.py --start-date 2024-01-01 --end-date 2024-01-31

# 启用通知监控
python tests/run_all_tests.py --watch-notifications

# 生成测试报告
python tests/run_all_tests.py --report-format json --output-dir test_reports/
```

## 测试报告

框架自动生成详细测试报告：

```json
{
  "test_run_id": "2024-01-01_120000",
  "total_scenarios": 5,
  "passed": 4,
  "failed": 1,
  "duration": 125.3,
  "scenarios": [
    {
      "name": "习惯养成+数据查询混合场景",
      "status": "passed",
      "steps": 15,
      "duration": 28.5,
      "tools_called": [
        "create_habit_tool",
        "record_water_tool",
        "record_weight_tool"
      ],
      "notifications_received": 2,
      "timeline": {
        "start_date": "2024-01-01",
        "end_date": "2024-01-10",
        "time_travel_calls": 10
      }
    }
  ]
}
```

## 后续扩展

1. **并行测试**：支持多用户同时测试
2. **性能测试**：记录响应时间和资源消耗
3. **可视化报告**：生成HTML测试报告
4. **CI集成**：集成到持续集成流程
5. **Mock服务**：支持离线测试模式
