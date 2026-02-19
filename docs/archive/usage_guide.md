# 使用指南

## 概述

本文档提供项目的使用指南，包括环境设置、运行测试、查看报告等。

## 环境要求

### Python版本
- Python 3.8+
- 推荐使用 Python 3.10+

### 依赖安装
```bash
# 安装项目依赖
pip install -r requirements.txt

# 或使用 pipenv
pipenv install
```

### 环境变量
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量
vim .env
```

## 项目结构

### 快速了解
```
open_workdspace/
├── main.py                    # 主程序入口
├── test_runners/              # 测试运行器
├── scripts/                   # 工具脚本
├── logs/                      # 日志文件
├── reports/                   # 测试报告
├── config/                    # 配置文件
└── docs/                      # 文档
```

### 关键目录
- `test_runners/` - 测试运行器，执行各种测试
- `scripts/` - 工具脚本，用于调试和修复
- `logs/` - 日志文件，记录运行信息
- `reports/` - 测试报告，保存测试结果

## 快速开始

### 1. 启动后端服务
```bash
# 启动主服务
python main.py

# 或使用uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 创建测试用户
```bash
# 运行创建测试用户脚本
python scripts/create_test_user.py

# 验证用户创建
ls -la test_users_*.json
```

### 3. 运行测试

#### 快速测试
```bash
# 运行快速测试
python test_runners/run_quick_test.py

# 运行简单测试
python test_runners/run_simple_real_test.py
```

#### 完整测试
```bash
# 运行完整智能聊天测试
python test_runners/run_complete_smart_chat_test.py

# 运行真实API测试
python test_runners/run_real_smart_chat_test.py
```

### 4. 查看结果

#### 查看日志
```bash
# 查看最新日志
tail -f logs/$(date +%Y%m%d).log

# 查看错误日志
grep ERROR logs/*.log
```

#### 查看报告
```bash
# 列出最新报告
ls -lt reports/*.json | head -5

# 查看报告摘要
cat reports/*.txt | tail -20
```

## 测试运行器详解

### 可用测试运行器

| 测试运行器 | 说明 | 使用场景 |
|------------|------|----------|
| `run_quick_test.py` | 快速测试框架功能 | 验证基本功能 |
| `run_simple_real_test.py` | 简单真实API测试 | 测试API连接 |
| `run_smart_chat_test.py` | 智能聊天测试演示 | 了解测试框架 |
| `run_complete_smart_chat_test.py` | 完整智能聊天测试 | 全面功能测试 |
| `run_real_smart_chat_test.py` | 真实API完整测试 | 生产环境测试 |
| `run_real_api_test.py` | 真实API测试 | API功能验证 |

### 运行参数

#### 跳过确认
```bash
# 跳过用户确认
python test_runners/run_real_smart_chat_test.py --skip-confirm
```

#### 指定后端地址
```bash
# 修改测试运行器中的base_url
# 默认: http://127.0.0.1:8000
# 可修改为: http://localhost:8000 或其他地址
```

## 工具脚本使用

### 调试脚本

#### 检查数据
```bash
# 检查舞蹈记录
python scripts/check_dance_record.py

# 检查运动类型
python scripts/check_exercise_types.py

# 检查最新记录
python scripts/check_latest_records.py
```

#### 调试问题
```bash
# 调试代理工具调用
python scripts/debug_agent_tool_calls.py

# 调试余额问题
python scripts/debug_balance.py

# 调试签到问题
python scripts/debug_checkin_issue.py
```

### 修复脚本

#### 数据修复
```bash
# 修复批量问题
python scripts/fix_batch.py

# 修复运动问题
python scripts/fix_exercise_issue.py
```

#### API测试
```bash
# 测试API修复
python scripts/test_api_fix.py

# 测试API响应
python scripts/test_api_response.py

# 测试时间模拟
python scripts/test_time_simulation.py
```

## 配置管理

### 路径配置
```python
# 使用统一路径配置
from config.paths import (
    get_log_file,
    get_report_file,
    get_test_runner_path,
    get_script_path
)

# 获取日志文件路径
log_file = get_log_file("test")

# 获取报告文件路径
report_file = get_report_file("test_report")

# 获取脚本路径
script_path = get_script_path("test_api_fix")
```

### 日志配置
```python
# 使用统一日志配置
from config.logging_config import setup_logging, get_module_logger

# 设置日志
setup_logging(level=logging.INFO, log_to_file=True)

# 获取模块日志记录器
logger = get_module_logger(__name__)
logger.info("开始处理")
```

## 测试框架

### 测试类型

#### 1. 功能测试
- 验证基本聊天功能
- 测试记忆能力
- 验证工具调用

#### 2. 集成测试
- API集成测试
- 数据库集成测试
- 外部服务集成测试

#### 3. 性能测试
- 响应时间测试
- 并发测试
- 负载测试

### 测试数据

#### 用户画像
```python
from tests.smart_chat_api_test_framework import UserProfileGenerator

# 创建用户画像
user_profiles = [
    UserProfileGenerator.create_middle_age_official(),      # 中年公务员
    UserProfileGenerator.create_female_office_worker(),     # 女性上班族
    UserProfileGenerator.create_college_student(),          # 大学生
    UserProfileGenerator.create_retired_elder()             # 退休老人
]
```

#### 测试场景
```python
from tests.holiday_simulator import HolidaySimulator
from tests.memory_test_generator import MemoryTestGenerator

# 生成测试日历
simulator = HolidaySimulator()
calendar = simulator.generate_20_day_calendar()

# 生成记忆测试
generator = MemoryTestGenerator()
memory_tests = generator.generate_memory_tests(user_profile)
```

## 报告系统

### 报告类型

#### JSON详细报告
```json
{
  "summary": {
    "total_tests": 100,
    "passed_tests": 85,
    "failed_tests": 15,
    "success_rate": 85.0
  },
  "user_statistics": {
    "user_001": {
      "total": 25,
      "passed": 20,
      "failed": 5
    }
  },
  "recommendations": [
    "优化记忆召回功能",
    "改进工具调用准确性"
  ]
}
```

#### 文本摘要报告
```
智能聊天API测试报告
============================================================

测试概览:
- 测试时间: 2025-02-13 14:30:22
- 后端地址: http://127.0.0.1:8000
- 测试周期: 20天 (2026-02-01 到 2026-02-20)
- 用户数量: 4
- 认证模式: 真实认证

📊 测试结果汇总:
----------------------------------------
总测试数: 100
通过测试: 85
失败测试: 15
成功率: 85.0%

👥 用户表现:
----------------------------------------
张三 (公务员):
  测试数: 25
  通过数: 20
  成功率: 80.0%
```

### 报告分析

#### 成功指标
- 成功率 > 90%: 优秀
- 成功率 80-90%: 良好
- 成功率 70-80%: 需要改进
- 成功率 < 70%: 需要重点关注

#### 常见问题
1. **API连接失败**: 检查后端服务是否运行
2. **认证失败**: 检查用户token是否有效
3. **响应超时**: 检查网络连接和服务器负载
4. **数据不一致**: 检查测试数据格式

## 故障排除

### 常见问题

#### 1. 测试运行失败
```bash
# 检查后端服务
curl http://127.0.0.1:8000/health

# 检查用户token文件
ls -la test_users_*.json

# 查看错误日志
tail -f logs/error_*.log
```

#### 2. API连接问题
```bash
# 测试API连接
python -c "
import requests
try:
    response = requests.get('http://127.0.0.1:8000/health', timeout=5)
    print(f'API状态: {response.status_code}')
except Exception as e:
    print(f'连接失败: {e}')
"
```

#### 3. 内存不足
```bash
# 查看内存使用
free -h

# 清理Python缓存
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "*.pyc" -delete
```

### 调试技巧

#### 启用详细日志
```python
# 修改日志级别
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### 使用调试器
```python
# 添加断点
import pdb
pdb.set_trace()

# 或使用breakpoint() (Python 3.7+)
breakpoint()
```

#### 检查网络请求
```python
# 启用请求日志
import http.client
http.client.HTTPConnection.debuglevel = 1

import logging
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True
```

## 最佳实践

### 测试最佳实践

1. **先运行快速测试**: 验证基本功能
2. **逐步增加复杂度**: 从简单到复杂测试
3. **记录测试结果**: 保存详细报告
4. **定期回归测试**: 确保功能稳定

### 开发最佳实践

1. **使用统一配置**: 使用config模块管理配置
2. **遵循日志规则**: 使用统一日志格式
3. **保持代码整洁**: 定期清理临时文件
4. **更新文档**: 及时更新使用指南

### 维护最佳实践

1. **定期清理日志**: 清理旧日志文件
2. **备份重要数据**: 备份测试数据和配置
3. **监控系统资源**: 监控内存和磁盘使用
4. **更新依赖**: 定期更新Python包

## 扩展开发

### 添加新测试

#### 1. 创建测试运行器
```python
# test_runners/run_new_test.py
#!/usr/bin/env python3
"""
新功能测试
"""

import asyncio
import logging
from tests.main_test_runner import MainTestRunner

async def run_new_test():
    """运行新功能测试"""
    runner = MainTestRunner()
    # 测试逻辑
    
if __name__ == "__main__":
    asyncio.run(run_new_test())
```

#### 2. 添加测试场景
```python
# tests/new_test_scenarios.py
class NewTestScenario:
    """新测试场景"""
    
    def generate_tests(self, user_profile):
        """生成测试点"""
        tests = []
        # 生成测试逻辑
        return tests
```

#### 3. 更新文档
- 更新使用指南
- 更新目录结构文档
- 更新README（如需要）

### 自定义配置

#### 修改日志配置
```python
# config/logging_config.py
def setup_custom_logging():
    """自定义日志配置"""
    # 自定义配置逻辑
```

#### 添加新路径
```python
# config/paths.py
def get_custom_path(name: str) -> Path:
    """获取自定义路径"""
    custom_dir = PROJECT_ROOT / "custom"
    custom_dir.mkdir(exist_ok=True)
    return custom_dir / name
```

## 支持与反馈

### 获取帮助
1. 查看本文档
2. 查看代码注释
3. 查看日志文件
4. 联系开发团队

### 报告问题
1. 描述问题现象
2. 提供错误日志
3. 提供复现步骤
4. 提供环境信息

### 贡献指南
1. Fork项目仓库
2. 创建功能分支
3. 提交代码更改
4. 创建Pull Request

## 更新记录

| 日期 | 版本 | 变更说明 |
|------|------|----------|
| 2025-02-13 | 1.0.0 | 初始版本，基本使用指南 |
| 2025-02-13 | 1.1.0 | 添加故障排除和最佳实践 |