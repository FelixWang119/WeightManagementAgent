# 智能通知决策系统 - 主动提醒测试指南

## 🎯 测试目标
验证智能通知决策系统的主动提醒功能，确保系统能够：
- ✅ 智能识别用户情境和事件
- ✅ 动态调整通知策略
- ✅ 生成个性化话术
- ✅ 正确发送通知

## 🔧 测试环境准备

### 1. 安装依赖
```bash
pip install pytest pytest-asyncio
```

### 2. 配置日志
确保 `config/logging_config.py` 已配置，测试时查看详细日志输出。

## 📋 测试分类

### A. 单元测试（已实现）
**文件**: `tests/test_intelligent_notification.py`

**测试内容**:
- ✅ 决策引擎功能测试
- ✅ 事件检测准确性测试
- ✅ 话术生成质量测试
- ✅ 服务集成测试
- ✅ 性能基准测试

**运行方式**:
```bash
# 运行所有测试
pytest tests/test_intelligent_notification.py -v

# 运行特定测试类
pytest tests/test_intelligent_notification.py::TestIntelligentDecisionEngine -v

# 运行性能测试
pytest tests/test_intelligent_notification.py::TestPerformance -v
```

### B. 集成测试
**文件**: `tests/integration_test_demo.py` (将创建)

**测试内容**:
- 端到端通知流程
- 与现有系统集成
- 多用户场景测试

### C. 手动测试
**文件**: `manual_test_scripts/` (将创建)

**测试内容**:
- 交互式测试脚本
- 实时对话模拟
- 可视化测试结果

## 🚀 快速开始测试

### 方法1: 运行演示脚本
```bash
python tests/test_intelligent_notification.py
```
这个脚本会自动运行演示套件，展示核心功能。

### 方法2: 交互式测试控制台
```bash
python scripts/interactive_notification_tester.py
```

### 方法3: 直接调用API测试
```python
from services.intelligent_notification_service import intelligent_notification_service

# 测试单个用户
result = await intelligent_notification_service.send_active_notification(
    user_id=1,
    notification_type="exercise",
    plan_data={"scheduled_time": "19:00"}
)
print(result)
```

## 🎭 测试场景设计

### 场景1: 标准运动提醒
**输入**: 用户无特殊事件，正常运动时间
**预期**: 发送标准提醒消息

### 场景2: 应酬事件冲突
**输入**: 用户提到"今晚有应酬"
**预期**: 调整提醒时间，生成温和建议

### 场景3: 生病事件
**输入**: 用户说"感冒了不舒服"
**预期**: 暂停提醒或发送关怀消息

### 场景4: 旅行事件
**输入**: 用户说"明天出差"
**预期**: 调整计划，提供异地建议

### 场景5: 用户压力高
**输入**: 检测到用户近期回复简短消极
**预期**: 降低频率，使用温和语气

## 📊 测试指标

### 功能指标
- 事件检测准确率 ≥ 90%
- 决策正确率 ≥ 85%
- 话术生成质量评分 ≥ 8/10

### 性能指标
- 单次决策时间 < 500ms
- 消息生成时间 < 200ms
- 10次并发决策 < 2s

### 用户体验指标
- 通知接受度 ≥ 80%
- 用户满意度评分 ≥ 4/5
- 调整建议采纳率 ≥ 70%

## 🔍 调试技巧

### 1. 查看详细日志
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 2. 事件检测调试
```python
from services.context_aware_event_detector import ContextAwareEventDetector
detector = ContextAwareEventDetector()

# 测试特定文本
events = await detector.detect_events_from_conversation("今晚有应酬")
print(f"检测到事件: {[e.type for e in events]}")
```

### 3. 决策过程跟踪
```python
from services.intelligent_decision_engine import IntelligentDecisionEngine
engine = IntelligentDecisionEngine()

# 启用详细日志
engine.logger.setLevel(logging.DEBUG)
result = await engine.make_decision(1, "exercise")
```

## 🧪 测试数据生成

### 模拟用户数据
```python
test_users = [
    {"id": 1, "profile": "灵活型", "stress": 0.3},
    {"id": 2, "profile": "压力型", "stress": 0.7},
    {"id": 3, "profile": "严谨型", "stress": 0.5}
]
```

### 测试对话样本
```python
test_conversations = [
    "今晚有应酬，可能没时间运动了",
    "感冒了不舒服，想休息",
    "明天出差三天，运动计划怎么安排",
    "最近工作压力大，运动有点坚持不下去"
]
```

## 📈 测试报告生成

测试完成后，系统会自动生成：
- HTML测试报告
- 性能分析图表
- 用户满意度模拟数据

## 🚨 常见问题排查

### 问题1: 事件检测不准确
**解决**: 检查关键词配置，增加正则模式

### 问题2: 决策过于保守
**解决**: 调整决策模式为 `INTELLIGENT`

### 问题3: 话术模板缺失
**解决**: 检查 `intelligent_message_generator.py` 中的模板配置

### 问题4: 性能问题
**解决**: 启用缓存，优化算法复杂度

## 🔮 扩展测试

### A/B测试框架
测试不同决策模式的效果对比。

### 压力测试
模拟高并发用户场景。

### 长期效果测试
跟踪用户行为变化。

---

**立即开始测试**:
```bash
# 最简单的开始方式
python tests/test_intelligent_notification.py

# 或运行完整测试套件
pytest tests/ -v
```

这个测试指南提供了从简单到复杂的多种测试方法，您可以根据需要选择适合的测试方案。