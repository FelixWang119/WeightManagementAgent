# 目录结构规范

## 概述

本项目采用标准化的目录结构，确保代码组织清晰、维护方便。所有文件和目录应遵循本规范。

## 完整目录结构

```
open_workdspace/
├── .gitignore                    # Git忽略规则
├── AGENTS.md                     # 代理配置和用户偏好
├── README.md                     # 项目说明
├── main.py                       # 主程序入口
├── main_template.py              # 主程序模板
├── test_users_tokens.json        # 测试用户token（不提交到Git）
├── test_users_mapping.json       # 测试用户映射（不提交到Git）
│
├── logs/                         # 日志文件目录
│   ├── 20250213.log             # 按日期命名的日志文件
│   ├── test_20250213.log        # 测试日志
│   └── .gitkeep                 # 保持目录结构
│
├── reports/                      # 测试报告目录
│   ├── smart_chat_test_report_20250213_143022.json
│   ├── basic_chat_test_report_20250213_143022.txt
│   └── .gitkeep                 # 保持目录结构
│
├── test_runners/                 # 测试运行器目录
│   ├── __init__.py              # 包初始化文件
│   ├── run_smart_chat_test.py   # 智能聊天测试
│   ├── run_real_smart_chat_test.py
│   ├── run_simple_real_test.py
│   ├── run_complete_smart_chat_test.py
│   ├── run_quick_test.py
│   └── run_real_api_test.py
│
├── scripts/                      # 工具脚本目录
│   ├── __init__.py              # 包初始化文件
│   ├── test_api_fix.py          # API修复测试
│   ├── test_api_response.py     # API响应测试
│   ├── test_time_simulation.py  # 时间模拟测试
│   ├── check_dance_record.py    # 舞蹈记录检查
│   ├── check_exercise_types.py  # 运动类型检查
│   ├── check_latest_records.py  # 最新记录检查
│   ├── check_user_20.py         # 用户20检查
│   ├── create_test_user.py      # 创建测试用户
│   ├── debug_agent_tool_calls.py
│   ├── debug_balance.py
│   ├── debug_checkin_issue.py
│   ├── debug_duplicate_records.py
│   ├── debug_exercise_data.py
│   ├── debug_user_detail.py
│   ├── fix_batch.py
│   ├── fix_exercise_issue.py
│   ├── run_active_notification_tests.py
│   ├── run_all_notification_tests.py
│   ├── run_conversation_tests.py
│   └── run_extended_tests.py
│
├── examples/                     # 示例代码目录
│   ├── __init__.py              # 包初始化文件
│   ├── run_all_tests.sh         # 运行所有测试的示例脚本
│   └── cleanup_logs.sh          # 清理日志的示例脚本
│
├── docs/                         # 文档目录
│   ├── rules/                   # 规则文档
│   │   ├── logging_rules.md     # 日志规则
│   │   └── directory_structure.md # 目录结构（本文档）
│   ├── usage_guide.md           # 使用指南
│   └── intelligent_notification_decision_system.md
│
├── config/                       # 配置文件目录
│   ├── __init__.py              # 包初始化文件
│   ├── paths.py                 # 统一路径配置
│   ├── logging_config.py        # 日志配置
│   └── settings.py              # 项目设置
│
├── tests/                        # 测试框架代码
│   ├── __init__.py              # 包初始化文件
│   ├── main_test_runner.py      # 主测试运行器
│   ├── smart_chat_api_test_framework.py
│   ├── holiday_simulator.py
│   ├── memory_test_generator.py
│   ├── api_test_executor.py
│   ├── extended_test_scenarios.py
│   ├── time_simulation_framework.py
│   └── test_chat_features.py
│
├── api/                          # API相关代码
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py
│       ├── chat.py
│       └── admin/
│           ├── __init__.py
│           └── users.py
│
├── services/                     # 服务层代码
│   ├── __init__.py
│   ├── intelligent_decision_engine.py
│   └── user_profile_service.py
│
├── models/                       # 数据模型
│   ├── __init__.py
│   └── database.py
│
└── utils/                        # 工具函数
    ├── __init__.py
    ├── exceptions.py            # 自定义异常
    └── logger.py               # 日志工具
```

## 目录说明

### 1. 根目录文件

| 文件 | 说明 | Git状态 |
|------|------|----------|
| `main.py` | 主程序入口 | 提交 |
| `AGENTS.md` | 代理配置和用户偏好 | 提交 |
| `README.md` | 项目说明文档 | 提交 |
| `test_users_tokens.json` | 测试用户token | **不提交** |
| `test_users_mapping.json` | 测试用户映射 | **不提交** |

### 2. 核心目录

#### `logs/` - 日志文件目录
- 存储所有日志文件
- 按日期和类型组织
- 自动轮转和清理
- `.gitkeep` 保持目录结构

#### `reports/` - 测试报告目录
- 存储测试报告文件
- JSON格式详细报告
- 文本格式摘要报告
- `.gitkeep` 保持目录结构

#### `test_runners/` - 测试运行器目录
- 所有测试运行器脚本
- 独立的测试执行程序
- 支持不同测试场景

#### `scripts/` - 工具脚本目录
- 调试和修复脚本
- 数据检查脚本
- 测试辅助脚本
- 一次性工具脚本

### 3. 代码目录

#### `config/` - 配置文件目录
- 项目配置和设置
- 路径配置
- 日志配置
- 环境变量管理

#### `tests/` - 测试框架代码
- 测试框架核心代码
- 测试场景定义
- 测试执行器
- 测试数据生成

#### `api/` - API相关代码
- API路由定义
- 请求处理
- 响应格式化
- 认证和授权

#### `services/` - 服务层代码
- 业务逻辑服务
- 数据处理
- 外部服务集成

#### `models/` - 数据模型
- 数据库模型定义
- 数据验证
- 关系映射

#### `utils/` - 工具函数
- 通用工具函数
- 异常处理
- 日志工具
- 辅助函数

### 4. 文档和示例

#### `docs/` - 文档目录
- 项目文档
- 使用指南
- 规则说明
- 设计文档

#### `examples/` - 示例代码目录
- 使用示例
- 脚本示例
- 配置示例
- 最佳实践示例

## 文件命名规范

### Python文件
- 使用小写字母和下划线：`module_name.py`
- 描述性名称：`smart_chat_api_test_framework.py`
- 避免缩写：使用完整单词

### 日志文件
- 日期格式：`YYYYMMDD.log`
- 类型前缀：`type_YYYYMMDD.log`
- 示例：`test_20250213.log`

### 报告文件
- 时间戳格式：`report_YYYYMMDD_HHMMSS.json`
- 描述性名称：`smart_chat_test_report_20250213_143022.json`

### 配置文件
- 明确用途：`paths.py`, `logging_config.py`
- 环境区分：`settings_dev.py`, `settings_prod.py`

## Git忽略规则

### 不提交的文件
```gitignore
# 日志文件
logs/*.log
!logs/.gitkeep

# 报告文件
reports/*.json
reports/*.txt
!reports/.gitkeep

# 敏感信息
test_users_tokens.json
test_users_mapping.json

# 临时文件
*.tmp
*.temp

# 环境文件
.env
.env.local
```

### 提交的文件
- 所有源代码文件（`.py`）
- 配置文件模板
- 文档文件（`.md`）
- 目录结构文件（`.gitkeep`）

## 新增文件流程

### 1. 确定文件类型
- 测试运行器 → `test_runners/`
- 工具脚本 → `scripts/`
- 配置文件 → `config/`
- 测试代码 → `tests/`
- 示例代码 → `examples/`

### 2. 检查命名规范
- 是否符合命名规则
- 是否与现有文件冲突
- 是否描述清晰

### 3. 更新文档
- 更新本目录结构文档
- 更新相关使用指南
- 更新README（如需要）

### 4. 验证路径引用
- 使用 `config.paths` 模块
- 更新相关导入语句
- 测试文件访问

## 迁移指南

### 从旧结构迁移
1. 移动测试运行器到 `test_runners/`
2. 移动工具脚本到 `scripts/`
3. 更新文件导入路径
4. 使用 `config.paths` 模块

### 更新导入语句
```python
# 旧方式
from tests.main_test_runner import MainTestRunner

# 新方式（如果文件移动了）
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.main_test_runner import MainTestRunner
```

### 路径引用更新
```python
# 旧方式
log_file = "logs/test.log"

# 新方式
from config.paths import get_log_file
log_file = get_log_file("test")
```

## 维护说明

### 定期清理
1. 清理旧日志文件（30天前）
2. 清理临时报告文件
3. 检查未使用的脚本
4. 更新文档

### 结构验证
```bash
# 验证目录结构
python -c "from config.paths import validate_paths; validate_paths()"

# 检查文件权限
find . -type f -name "*.py" -exec chmod 644 {} \;
find . -type f -name "*.sh" -exec chmod 755 {} \;
```

### 备份策略
1. 重要配置文件定期备份
2. 测试数据定期备份
3. 文档版本控制

## 常见问题

### Q: 新文件应该放在哪里？
A: 根据文件类型参考目录说明部分。

### Q: 如何引用其他目录的文件？
A: 使用 `config.paths` 模块或相对导入。

### Q: 日志文件太大怎么办？
A: 启用日志轮转，定期清理旧文件。

### Q: 测试报告应该提交吗？
A: 不，测试报告不提交到Git，使用 `.gitignore` 排除。

### Q: 如何添加新的目录？
A: 更新本文档，创建目录并添加 `.gitkeep` 文件。

## 更新记录

| 日期 | 版本 | 变更说明 |
|------|------|----------|
| 2025-02-13 | 1.0.0 | 初始版本，定义标准目录结构 |
| 2025-02-13 | 1.1.0 | 添加迁移指南和维护说明 |