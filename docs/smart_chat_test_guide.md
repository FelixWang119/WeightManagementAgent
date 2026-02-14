# 智能对话功能API级别测试指南

## 概述

本测试框架用于对智能对话功能进行API级别的全面测试，覆盖20天生活场景、多用户画像、节假日场景，深度验证agent的记忆能力和tool调用能力。

## 测试架构

### 核心组件

1. **用户画像系统** (`tests/smart_chat_api_test_framework.py`)
   - 4种预定义用户画像：中年公务员、职场女白领、大学生、退休老人
   - 每个画像包含：作息习惯、健康目标、约束条件、节假日行为

2. **节假日模拟器** (`tests/holiday_simulator.py`)
   - 支持常规周末和法定节假日
   - 20天时间线包含春节等节假日场景
   - 不同用户在节假日的特殊行为模式

3. **记忆测试生成器** (`tests/memory_test_generator.py`)
   - 短期记忆测试（当天内）
   - 中期记忆测试（跨天）
   - 长期记忆测试（多天跨度）
   - 节假日特殊测试

4. **API测试执行器** (`tests/api_test_executor.py`)
   - 实际调用聊天API
   - 验证记忆回忆和工具调用
   - 结果验证和统计

5. **主测试运行器** (`tests/main_test_runner.py`)
   - 整合所有组件
   - 运行20天完整测试
   - 生成详细测试报告

## 快速开始

### 1. 环境准备

```bash
# 确保后端服务依赖已安装
pip install -r requirements.txt

# 确保测试依赖
pip install pytest pytest-asyncio aiohttp
```

### 2. 启动后端服务

```bash
# 启动FastAPI服务
python main.py
# 或使用启动脚本
./start.sh
```

服务将在 `http://localhost:8000` 启动。

### 3. 运行演示测试

```bash
# 运行演示测试，验证框架功能
python run_smart_chat_test.py
```

### 4. 运行完整测试

```bash
# 运行完整的20天测试（需要后端服务运行）
python -m tests.main_test_runner
```

### 5. 查看测试报告

测试完成后，将生成两个报告文件：
- `smart_chat_test_report.json` - JSON格式详细报告
- `smart_chat_test_report.txt` - 文本格式简明报告

```bash
# 查看测试报告
cat smart_chat_test_report.txt
```

## 测试验证点

### 1. 记忆能力验证

**短期记忆**（当天内）：
- 早餐承诺的记忆和关联
- 运动计划的跟踪
- 多轮对话的上下文保持

**中期记忆**（跨天）：
- 昨天/前天承诺的跟踪
- 习惯模式的识别
- 连续事件的关联

**长期记忆**（多天跨度）：
- 周度总结能力
- 趋势分析能力
- 用户画像的持续应用

### 2. 工具调用验证

- `record_weight` - 体重记录
- `record_meal` - 餐食记录
- `record_exercise` - 运动记录
- `record_water` - 饮水记录
- `get_daily_summary` - 每日总结
- `get_weekly_summary` - 周度总结
- `get_weight_trend` - 体重趋势

### 3. 节假日场景验证

**常规周末**：
- 休息日提醒调整
- 周末活动建议
- 作息时间适应

**法定节假日**（春节）：
- 节日特殊场景识别
- 节日饮食建议
- 节后恢复指导

### 4. 用户画像适配验证

**中年公务员**：
- 高血压管理建议
- 应酬场景处理
- 久坐办公提醒

**职场女白领**：
- 健身计划适配
- 工作压力管理
- 轻食建议

**大学生**：
- 作息调整建议
- 预算友好建议
- 社交活动平衡

**退休老人**：
- 慢性病管理
- 轻度运动建议
- 易消化饮食

## 自定义测试

### 添加新用户画像

在 `tests/smart_chat_api_test_framework.py` 的 `UserProfileGenerator` 类中添加：

```python
@staticmethod
def create_custom_profile() -> UserProfile:
    return UserProfile(
        user_id="custom_001",
        name="自定义用户",
        age=35,
        occupation="职业",
        health_goal="健康目标",
        daily_routine={"07:00": "起床", "22:00": "睡觉"},
        habits=["习惯1", "习惯2"],
        constraints=["约束1", "约束2"],
        personality_traits=["特质1", "特质2"],
        weekend_behavior={"周六": "活动1", "周日": "活动2"},
        holiday_behavior={"春节": "节日活动"}
    )
```

### 添加新节假日

在 `tests/holiday_simulator.py` 的 `_initialize_holidays` 方法中添加：

```python
"custom_holiday": HolidayEvent(
    name="自定义节日",
    date="MM-DD",  # 日期格式
    duration_days=1,
    type="statutory",  # 或 "weekend"/"personal"
    description="节日描述",
    typical_activities=["活动1", "活动2"]
)
```

### 添加新测试场景

在 `tests/memory_test_generator.py` 中添加新的测试生成方法：

```python
def generate_custom_tests(self) -> List[MemoryTestPoint]:
    tests = []
    tests.append(MemoryTestPoint(
        day=1,
        time="10:00",
        user_input="自定义测试输入",
        expected_memory_recall=["期望记忆内容"],
        expected_tool_calls=["期望工具调用"],
        memory_type="short"  # 或 "mid"/"long"
    ))
    return tests
```

## 测试配置

### 调整测试参数

可以通过修改以下参数调整测试：

1. **测试时长**：默认20天，可在 `HolidaySimulator` 中调整
2. **用户数量**：默认4种，可在 `MainTestRunner.setup_test_users` 中调整
3. **测试密度**：在 `MemoryTestGenerator` 中调整测试点数量
4. **验证严格度**：在 `APITestExecutor._verify_memory_recall` 中调整

### 环境变量

```bash
# 指定后端服务地址
export TEST_BASE_URL="http://localhost:8000"

# 指定测试用户token（如使用真实用户）
export TEST_USER_TOKEN="your_token_here"
```

## 故障排除

### 常见问题

1. **API连接失败**
   ```
   错误：API调用失败: 500 - Internal Server Error
   ```
   解决方案：确保后端服务正常运行，检查 `TEST_BASE_URL` 配置

2. **测试超时**
   ```
   错误：asyncio.TimeoutError
   ```
   解决方案：增加API超时时间，或在 `APITestExecutor` 中调整重试逻辑

3. **记忆验证失败**
   ```
   警告：未找到期望的记忆内容: ...
   ```
   解决方案：调整 `expected_memory_recall` 为更通用的关键词

4. **工具调用验证失败**
   ```
   警告：期望的工具未调用: ...
   ```
   解决方案：检查后端服务的工具调用逻辑，或调整测试期望

### 调试模式

启用详细日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 测试报告解读

### 关键指标

1. **整体成功率**：所有测试点的通过率
2. **用户表现**：各用户画像的测试表现
3. **记忆类型表现**：短期/中期/长期记忆的测试表现
4. **工具调用表现**：各工具调用的成功率

### 改进建议

测试报告会根据测试结果生成改进建议：
- 成功率 < 80%：建议检查agent核心逻辑
- 特定用户表现差：建议优化用户画像适配
- 特定工具调用失败：建议检查工具实现
- 节假日场景问题：建议优化节假日处理逻辑

## 性能考虑

### 测试执行时间

- **演示测试**：< 1秒
- **完整20天测试**：取决于API响应时间，通常5-10分钟
- **并发测试**：支持多用户并发，提高测试效率

### 资源使用

- **内存**：测试框架内存占用 < 100MB
- **网络**：API调用频率可配置，避免对后端造成压力
- **存储**：测试报告文件大小 < 1MB

## 扩展开发

### 集成现有测试框架

可以集成现有的 `time_simulation_framework.py` 和 `extended_test_scenarios.py`：

```python
from tests.time_simulation_framework import TimeSimulationFramework
from tests.extended_test_scenarios import ExtendedTestSuite

# 集成时间模拟
time_framework = TimeSimulationFramework()

# 集成扩展测试场景
extended_suite = ExtendedTestSuite(base_test_users)
```

### 添加新的验证维度

1. **情感分析验证**：验证agent的情感响应能力
2. **多模态验证**：验证图片、语音等多模态处理
3. **实时性验证**：验证响应时间和实时交互能力
4. **安全性验证**：验证输入过滤和安全防护

## 贡献指南

1. 遵循现有代码风格和结构
2. 为新功能添加完整的测试
3. 更新相关文档
4. 确保向后兼容性

## 许可证

MIT License