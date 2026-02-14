"""
统一路径配置模块。

提供项目中所有文件路径的统一配置，确保路径一致性。
"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 主要目录路径
LOGS_DIR = PROJECT_ROOT / "logs"
REPORTS_DIR = PROJECT_ROOT / "reports"
TEST_RUNNERS_DIR = PROJECT_ROOT / "test_runners"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
EXAMPLES_DIR = PROJECT_ROOT / "examples"
DOCS_DIR = PROJECT_ROOT / "docs"
CONFIG_DIR = PROJECT_ROOT / "config"
TESTS_DIR = PROJECT_ROOT / "tests"

# 确保目录存在
def ensure_directories():
    """确保所有必要的目录都存在"""
    directories = [
        LOGS_DIR,
        REPORTS_DIR,
        TEST_RUNNERS_DIR,
        SCRIPTS_DIR,
        EXAMPLES_DIR,
        DOCS_DIR,
        CONFIG_DIR,
        TESTS_DIR,
        DOCS_DIR / "rules"
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        
        # 创建 .gitkeep 文件（如果目录为空）
        gitkeep_file = directory / ".gitkeep"
        if not any(directory.iterdir()):
            gitkeep_file.touch(exist_ok=True)

# 文件路径生成函数
def get_log_file(name: str = None, suffix: str = None) -> Path:
    """
    获取日志文件路径。
    
    Args:
        name: 日志文件名（可选）
        suffix: 文件后缀（可选，默认为 .log）
        
    Returns:
        完整的日志文件路径
    """
    ensure_directories()
    
    if name is None:
        from datetime import datetime
        name = datetime.now().strftime("%Y%m%d")
    
    if suffix is None:
        suffix = ".log"
    elif not suffix.startswith("."):
        suffix = f".{suffix}"
    
    return LOGS_DIR / f"{name}{suffix}"

def get_report_file(name: str = None, suffix: str = None) -> Path:
    """
    获取报告文件路径。
    
    Args:
        name: 报告文件名（可选）
        suffix: 文件后缀（可选，默认为 .json）
        
    Returns:
        完整的报告文件路径
    """
    ensure_directories()
    
    if name is None:
        from datetime import datetime
        name = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if suffix is None:
        suffix = ".json"
    elif not suffix.startswith("."):
        suffix = f".{suffix}"
    
    return REPORTS_DIR / f"{name}{suffix}"

def get_test_runner_path(name: str) -> Path:
    """
    获取测试运行器文件路径。
    
    Args:
        name: 测试运行器文件名（带或不带 .py 后缀）
        
    Returns:
        完整的测试运行器文件路径
    """
    ensure_directories()
    
    if not name.endswith(".py"):
        name = f"{name}.py"
    
    return TEST_RUNNERS_DIR / name

def get_script_path(name: str) -> Path:
    """
    获取脚本文件路径。
    
    Args:
        name: 脚本文件名（带或不带 .py 后缀）
        
    Returns:
        完整的脚本文件路径
    """
    ensure_directories()
    
    if not name.endswith(".py"):
        name = f"{name}.py"
    
    return SCRIPTS_DIR / name

def get_example_path(name: str) -> Path:
    """
    获取示例文件路径。
    
    Args:
        name: 示例文件名（带或不带 .py 后缀）
        
    Returns:
        完整的示例文件路径
    """
    ensure_directories()
    
    if not name.endswith(".py"):
        name = f"{name}.py"
    
    return EXAMPLES_DIR / name

# 常用文件路径
def get_user_tokens_file() -> Path:
    """获取用户token文件路径"""
    return PROJECT_ROOT / "test_users_tokens.json"

def get_user_mapping_file() -> Path:
    """获取用户映射文件路径"""
    return PROJECT_ROOT / "test_users_mapping.json"

def get_main_config_file() -> Path:
    """获取主配置文件路径"""
    return CONFIG_DIR / "settings.py"

def get_logging_config_file() -> Path:
    """获取日志配置文件路径"""
    return CONFIG_DIR / "logging_config.py"

# 路径验证
def validate_paths():
    """验证所有路径是否有效"""
    ensure_directories()
    
    required_files = [
        get_user_tokens_file(),
        get_user_mapping_file()
    ]
    
    missing_files = []
    for file_path in required_files:
        if not file_path.exists():
            missing_files.append(str(file_path))
    
    if missing_files:
        print("⚠️  缺少以下文件:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False
    
    return True

# 初始化时确保目录存在
ensure_directories()

if __name__ == "__main__":
    # 测试路径配置
    print("📁 项目目录结构:")
    print(f"   项目根目录: {PROJECT_ROOT}")
    print(f"   日志目录: {LOGS_DIR}")
    print(f"   报告目录: {REPORTS_DIR}")
    print(f"   测试运行器目录: {TEST_RUNNERS_DIR}")
    print(f"   脚本目录: {SCRIPTS_DIR}")
    print(f"   示例目录: {EXAMPLES_DIR}")
    print(f"   文档目录: {DOCS_DIR}")
    print(f"   配置目录: {CONFIG_DIR}")
    print(f"   测试目录: {TESTS_DIR}")
    
    print("\n📄 示例文件路径:")
    print(f"   日志文件: {get_log_file('test')}")
    print(f"   报告文件: {get_report_file('test')}")
    print(f"   测试运行器: {get_test_runner_path('run_smart_chat_test')}")
    print(f"   脚本文件: {get_script_path('test_api_fix')}")
    
    print("\n✅ 路径配置验证:", "通过" if validate_paths() else "失败")