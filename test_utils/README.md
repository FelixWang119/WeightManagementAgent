# 用户登录模拟器测试框架

这是一个可复用的端到端测试框架，用于测试体重管理助手的各项功能。

## 功能特性

- ✅ **用户登录模拟** - 模拟本地登录逻辑
- ✅ **测试数据管理** - 自动创建运动、体重数据
- ✅ **API测试** - 测试运动、体重、聊天API
- ✅ **AI功能测试** - 测试AI体重/运动记录
- ✅ **测试报告** - 生成详细的JSON测试报告
- ✅ **预定义测试场景** - 体重管理、运动跟踪、AI助手等

## 目录结构

```
test_utils/
├── user_simulator.py      # 核心用户模拟器类
├── example_usage.py       # 使用示例
├── README.md             # 本文档
└── __init__.py

test_e2e_template.py      # 端到端测试模板
test_reports/             # 测试报告输出目录（自动创建）
```

## 快速开始

### 1. 基础使用

```python
from test_utils.user_simulator import UserSimulator

# 创建模拟器
simulator = UserSimulator(base_url="http://localhost:8000")

# 登录用户
user = simulator.login("test_user")

# 创建测试数据
simulator.create_test_data(
    exercise_count=3,
    weight_count=2,
    include_ai_records=True
)

# 测试API
exercise_results = simulator.test_exercise_api()
weight_results = simulator.test_weight_api()
chat_results = simulator.test_chat_api("你好")
```

### 2. 快速测试函数

```python
from test_utils.user_simulator import quick_test

# 一键运行快速测试
results = quick_test("demo_user")
```

### 3. 完整端到端测试

```python
from test_e2e_template import E2ETestTemplate

# 创建测试实例
test = E2ETestTemplate("我的测试")

# 运行完整测试
results = test.run_full_test(
    test_code="e2e_test_user",
    create_data=True
)

# 保存报告
test.save_report()
```

## 预定义测试场景

### 体重管理测试
```bash
python test_e2e_template.py --test weight
```

### 运动跟踪测试
```bash
python test_e2e_template.py --test exercise
```

### AI助手测试
```bash
python test_e2e_template.py --test ai
```

### 回归测试
```bash
python test_e2e_template.py --test regression
```

### 运行所有测试
```bash
python test_e2e_template.py --test all
```

## 预定义测试用户

框架提供了几个预定义用户：

| 用户code | 描述 | 用途 |
|---------|------|------|
| `exercise_test_user` | 运动测试用户 | 已有运动数据 |
| `weight_test_user` | 体重测试用户 | 测试体重功能 |
| `chat_test_user` | 聊天测试用户 | 测试AI聊天 |
| `full_test_user` | 完整测试用户 | 端到端测试 |

## 自定义测试

### 创建自定义测试场景

```python
from test_utils.user_simulator import UserSimulator

def my_custom_test():
    simulator = UserSimulator()
    
    # 登录自定义用户
    user = simulator.login("my_custom_user")
    
    # 自定义数据创建
    simulator.create_test_data(
        exercise_count=5,
        weight_count=3,
        include_ai_records=True
    )
    
    # 自定义测试逻辑
    print("测试体重记录功能...")
    weight_chat = simulator.test_chat_api("我体重65.5kg")
    
    if weight_chat.get("has_tool_calls"):
        print("✅ AI成功记录体重")
    
    # 测试运动记录功能
    print("测试运动记录功能...")
    exercise_chat = simulator.test_chat_api("我今天跑步了30分钟")
    
    if exercise_chat.get("has_tool_calls"):
        print("✅ AI成功记录运动")
```

### 使用测试模板类

```python
from test_e2e_template import E2ETestTemplate

class MyCustomTest(E2ETestTemplate):
    def __init__(self):
        super().__init__("自定义测试")
    
    def run_custom_validation(self):
        """自定义验证逻辑"""
        print("运行自定义验证...")
        
        # 验证运动页面显示
        exercise_results = self.simulator.test_exercise_api()
        
        # 验证体重页面显示
        weight_results = self.simulator.test_weight_api()
        
        # 验证AI功能
        chat_results = self.simulator.test_chat_api("我体重65.5kg")
        
        return {
            "exercise": exercise_results,
            "weight": weight_results,
            "chat": chat_results
        }

# 运行测试
test = MyCustomTest()
test.run_login_test("custom_user")
test.run_custom_validation()
test.save_report("custom_test.json")
```

## 测试报告

测试框架会自动生成详细的JSON测试报告：

```json
{
  "test_name": "体重管理测试",
  "timestamp": "2026-02-15T09:00:00",
  "steps": [
    {
      "name": "用户登录",
      "success": true,
      "timestamp": "2026-02-15T09:00:01",
      "details": {
        "user_id": 35,
        "nickname": "测试用户fced4c",
        "exercise_count": 6,
        "weight_count": 5
      }
    },
    {
      "name": "运动API测试",
      "success": true,
      "timestamp": "2026-02-15T09:00:02",
      "details": {
        "record_count": 6,
        "has_ai_records": true
      }
    }
  ],
  "summary": {
    "total_steps": 5,
    "successful_steps": 5,
    "success_rate": 100.0,
    "overall_success": true
  }
}
```

报告保存在 `test_reports/` 目录中。

## 命令行使用

### 基本命令
```bash
# 运行所有测试
python test_e2e_template.py

# 运行特定测试
python test_e2e_template.py --test exercise

# 使用自定义用户code
python test_e2e_template.py --code my_test_user

# 不创建测试数据
python test_e2e_template.py --no-data
```

### 用户模拟器命令行
```bash
# 查看帮助
python -m test_utils.user_simulator --help

# 快速测试
python -m test_utils.user_simulator --code demo_user --create-data

# 完整测试
python -m test_utils.user_simulator --full-test --code full_test_user
```

## 集成到现有测试

### 在现有测试中使用
```python
import sys
sys.path.insert(0, "/path/to/project")

from test_utils.user_simulator import UserSimulator

class TestMyFeature:
    def setup_method(self):
        self.simulator = UserSimulator()
        self.user = self.simulator.login("test_feature_user")
    
    def test_feature_a(self):
        # 使用模拟器进行测试
        headers = self.simulator.get_headers()
        # ... 测试逻辑
    
    def test_feature_b(self):
        # 创建测试数据
        self.simulator.create_test_data(exercise_count=2)
        # ... 测试逻辑
```

### 在CI/CD中集成
```yaml
# GitHub Actions 示例
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Start server
      run: |
        python main.py &
        sleep 5
    
    - name: Run E2E tests
      run: |
        python test_e2e_template.py --test all
    
    - name: Upload test reports
      uses: actions/upload-artifact@v2
      with:
        name: test-reports
        path: test_reports/
```

## 注意事项

1. **服务器运行**：确保后端服务器正在运行（默认 `http://localhost:8000`）
2. **数据清理**：测试数据会持久化到数据库，测试间使用不同的用户code
3. **API兼容性**：如果API有变化，需要更新 `user_simulator.py` 中的请求格式
4. **错误处理**：框架包含基本的错误处理，但复杂的错误可能需要手动调试

## 扩展开发

### 添加新的测试类型
1. 在 `user_simulator.py` 中添加新的测试方法
2. 在 `test_e2e_template.py` 中添加新的测试场景
3. 更新命令行参数支持新的测试类型

### 自定义验证逻辑
继承 `E2ETestTemplate` 类并重写相关方法：
```python
class MyValidationTest(E2ETestTemplate):
    def run_custom_validation(self):
        # 自定义验证逻辑
        pass
    
    def run_full_test(self):
        # 重写完整测试流程
        pass
```

## 故障排除

### 常见问题

1. **导入错误**：确保 `test_utils` 目录在 Python 路径中
2. **连接错误**：检查服务器是否运行在正确的地址和端口
3. **认证错误**：确认用户登录逻辑与后端一致
4. **数据创建失败**：检查API端点是否可用，请求格式是否正确

### 调试模式
```python
import logging
logging.basicConfig(level=logging.DEBUG)

simulator = UserSimulator()
# 现在会显示详细的HTTP请求信息
```

## 贡献指南

1. 添加新的测试功能时，请同时更新示例和文档
2. 保持向后兼容性
3. 添加适当的错误处理和日志
4. 为新功能编写使用示例

## 许可证

MIT License