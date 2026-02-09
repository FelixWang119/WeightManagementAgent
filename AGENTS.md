# User Preferences

## System Preferences
- **Machine Performance**: Low (older/slower hardware)
- **Installation Preference**: Always prefer pre-built binaries over source compilation
  - Homebrew: Use bottles instead of building from source
  - pip: Use wheels (--only-binary when needed)
  - npm: Avoid build-from-source flags
  - cargo: Use pre-built binaries when available
  - gem: Avoid compilation when possible

## Performance Considerations
- Minimize CPU-intensive operations
- Avoid long-running compilation tasks
- Prefer lightweight alternatives

## Coding Standards

### Language
- **Primary**: Python 3.8+

### Logging Standards
```python
# 统一日志配置
from config.logging_config import setup_logging, get_module_logger

# 模块级初始化（每个模块一次）
logger = get_module_logger(__name__)

# 日志级别使用规范
logger.debug("调试信息 - 仅开发使用")
logger.info("关键流程节点 - 如'开始选股'、'分析完成'")
logger.warning("异常情况但不影响主流程 - 如'某股票数据缺失'")
logger.error("功能失败 - 必须处理的问题")
logger.exception("捕获异常时自动记录堆栈")

# 避免字符串拼接，使用占位符（性能优化）
# ✅ 推荐
logger.info("处理股票 %s，评分 %.2f", stock_code, score)
# ❌ 避免
logger.info(f"处理股票 {stock_code}，评分 {score}")

# 禁止在循环中高频打印（低配置机器考虑）
# 使用采样或仅记录关键节点
```

### Error Handling Standards

#### 1. 异常捕获层级
```python
# 函数级捕获 - 最内层
from utils.exceptions import DataError, ValidationError

def fetch_data(symbol: str) -> pd.DataFrame:
    try:
        return data_accessor.get_data(symbol)
    except DataError as e:
        logger.warning("获取 %s 数据失败: %s", symbol, e)
        return pd.DataFrame()  # 返回空数据，不中断流程
    except Exception as e:
        logger.exception("获取 %s 数据时发生未知错误", symbol)
        return pd.DataFrame()

# 模块级捕获 - 入口函数
def run_analysis():
    try:
        result = process_data()
        return result
    except ValidationError as e:
        logger.error("参数验证失败: %s", e)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.exception("分析过程发生错误")
        return {"success": False, "error": "内部错误"}
```

#### 2. 统一异常装饰器
```python
from utils.exceptions import retry_on_error

# 网络/IO 操作自动重试
@retry_on_error(max_attempts=3, delay=1.0)
def fetch_remote_data(url: str) -> dict:
    return requests.get(url).json()

# 数据库操作自动回滚
from utils.exceptions import transaction_context

with transaction_context(db) as ctx:
    ctx.execute("INSERT ...")
    ctx.commit()
```

#### 3. 错误处理原则
- **不要吞噬异常**：至少记录日志
- **尽早失败**：入口验证，避免深层错误
- **优雅降级**：部分失败时返回可用数据
- **上下文信息**：记录失败时的关键变量

### Code Style

#### Python 规范
- **PEP 8**: 4空格缩进，行宽100字符
- **类型提示**: 必须标注函数参数和返回值
  ```python
  def calculate_score(data: pd.DataFrame, threshold: float = 0.5) -> dict:
      ...
  ```
- **文档字符串**: Google风格
  ```python
  def process_stock(symbol: str) -> dict:
      """
      处理单只股票数据。

      Args:
          symbol: 股票代码，如 '000001'

      Returns:
          包含评分和分析结果的字典

      Raises:
          ValidationError: 当股票代码格式无效时
      """
  ```

#### 性能优化（低配置机器）
```python
# 1. 避免大数据复制，使用视图
# ✅ 推荐
df_view = df[['代码', '名称']]  # 返回视图
# ❌ 避免
df_copy = df.copy()  # 内存复制

# 2. 延迟加载/懒加载
class HeavyService:
    def __init__(self):
        self._client = None  # 延迟初始化
    
    @property
    def client(self):
        if self._client is None:
            self._client = create_client()  # 首次使用时创建
        return self._client

# 3. 批量操作优于循环单条处理
# ✅ 推荐
df['新列'] = df['价格'] * df['数量']  # 向量化
# ❌ 避免
for i in range(len(df)):
    df.loc[i, '新列'] = df.loc[i, '价格'] * df.loc[i, '数量']

# 4. 缓存重复计算
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_calculation(key: str) -> float:
    return heavy_computation(key)
```

### File Organization
```
project/
├── config/
│   ├── logging_config.py      # 统一日志配置
│   └── settings.py            # 全局配置
├── utils/
│   ├── exceptions.py          # 自定义异常和装饰器
│   └── logger.py             # 日志工具
├── core/
│   └── data_fetcher.py
└── AGENTS.md                  # 本文件
```

### Mandatory Patterns

#### 1. 模块入口保护
```python
if __name__ == "__main__":
    from utils.exceptions import protect_main
    protect_main(main)
```

#### 2. 配置管理
```python
# 所有可配置项集中管理，避免硬编码
from config.settings import get_config

config = get_config()
timeout = config.get('timeout', 30)  # 提供默认值
```

#### 3. 资源清理
```python
# 确保资源释放
with open('file.txt', 'r') as f:
    data = f.read()

# 或上下文管理器
from contextlib import closing
with closing(create_connection()) as conn:
    conn.execute(...)
```

### Testing Standards
```python
# 测试文件名: test_<module>.py
import pytest
from unittest.mock import Mock, patch

def test_calculate_score_with_valid_data():
    """测试正常数据计算"""
    data = pd.DataFrame({'价格': [10.0, 20.0]})
    result = calculate_score(data)
    assert result['total'] > 0

def test_calculate_score_with_empty_data():
    """测试空数据边界情况"""
    result = calculate_score(pd.DataFrame())
    assert result == {'total': 50, 'details': {}}

@pytest.mark.slow  # 标记慢测试
@patch('module.external_api')
def test_with_mock(mock_api):
    """使用 Mock 避免真实调用"""
    mock_api.return_value = {'score': 80}
    ...
```

### Review Checklist
提交代码前检查：
- [ ] 所有函数都有类型提示
- [ ] 异常都被捕获并记录
- [ ] 日志使用占位符而非 f-string
- [ ] 没有硬编码的魔法数字/字符串
- [ ] 资源使用 with 语句管理
- [ ] 代码通过 flake8/pylint 检查
- [ ] 新增功能有对应的测试
