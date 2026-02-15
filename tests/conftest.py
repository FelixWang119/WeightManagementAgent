"""
测试配置和fixture文件

提供测试所需的全局配置、fixture和工具函数
"""

import os
import sys
import asyncio
import pytest
import pytest_asyncio
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import Mock, patch

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置测试环境变量
os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_weight_management.db"
os.environ["LOG_LEVEL"] = "WARNING"  # 测试时减少日志输出

# 导入项目模块
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from main import app as fastapi_app
from models.database import Base, get_db
from config.settings import fastapi_settings


# ============ 数据库fixture ============


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """创建事件循环fixture"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """创建测试数据库引擎"""
    # 使用测试数据库URL
    test_database_url = "sqlite+aiosqlite:///./test_weight_management.db"
    engine = create_async_engine(
        test_database_url,
        echo=False,  # 测试时不输出SQL日志
        future=True,
    )

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 清理：删除所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """创建测试数据库会话"""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        try:
            yield session
        finally:
            # 每个测试后回滚，确保数据隔离
            await session.rollback()
            await session.close()


@pytest.fixture(scope="function")
def override_get_db(test_session):
    """重写get_db依赖，使用测试会话"""

    async def _override_get_db():
        try:
            yield test_session
        finally:
            pass

    return _override_get_db


# ============ FastAPI应用fixture ============


@pytest.fixture(scope="function")
def app(override_get_db) -> FastAPI:
    """创建测试用的FastAPI应用"""
    # 重写数据库依赖
    fastapi_app.dependency_overrides[get_db] = override_get_db

    # 配置测试设置
    fastapi_settings.ENV = "test"
    fastapi_settings.DATABASE_URL = "sqlite+aiosqlite:///./test_weight_management.db"

    return fastapi_app


@pytest.fixture(scope="function")
def client(app) -> TestClient:
    """创建测试HTTP客户端"""
    return TestClient(app)


# ============ 测试用户fixture ============


@pytest_asyncio.fixture(scope="function")
async def test_user(test_session):
    """创建测试用户"""
    from models.database import User

    user = User(
        username="test_user",
        email="test@example.com",
        hashed_password="hashed_test_password",  # 实际测试中应该使用正确的哈希
        is_active=True,
        is_superuser=False,
    )

    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    return user


@pytest_asyncio.fixture(scope="function")
async def test_user_token(client, test_user):
    """获取测试用户的认证token"""
    # 这里简化处理，实际应该调用登录API
    # 返回一个模拟的token
    return "test_token_123"


# ============ 测试数据清理fixture ============


@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_test_data(test_session):
    """自动清理测试数据（每个测试后执行）"""
    yield

    # 清理所有用户创建的数据
    from models.database import (
        User,
        WeightRecord,
        MealRecord,
        ExerciseRecord,
        WaterRecord,
        SleepRecord,
    )

    tables = [SleepRecord, WaterRecord, ExerciseRecord, MealRecord, WeightRecord, User]

    for table in tables:
        await test_session.execute(table.__table__.delete())

    await test_session.commit()


# ============ 测试配置fixture ============


@pytest.fixture(scope="session")
def test_config():
    """测试配置"""
    return {
        "database_url": "sqlite+aiosqlite:///./test_weight_management.db",
        "api_base_url": "http://localhost:8001",
        "test_timeout": 30.0,  # 测试超时时间（秒）
        "max_api_calls_per_day": 500,  # 千问API每日调用限制
    }


# ============ 测试工具函数 ============


def assert_response_success(response, status_code=200):
    """断言响应成功"""
    assert response.status_code == status_code
    if status_code == 200:
        assert "success" in response.json()
        assert response.json()["success"] is True


def assert_response_error(response, status_code, error_message=None):
    """断言响应错误"""
    assert response.status_code == status_code
    if error_message:
        assert error_message in response.text


def create_auth_headers(token):
    """创建认证头"""
    return {"Authorization": f"Bearer {token}"}


# ============ 测试装饰器 ============


def skip_if_no_qwen_api_key(func):
    """如果没有千问API密钥则跳过测试"""
    qwen_api_key = os.environ.get("QWEN_API_KEY") or fastapi_settings.QWEN_API_KEY

    @pytest.mark.skipif(
        not qwen_api_key or qwen_api_key == "your-qwen-api-key-here",
        reason="需要配置千问API密钥",
    )
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def mock_ai_response(content: str = "测试AI响应", model: str = "qwen-turbo"):
    """创建模拟的AI响应"""

    class MockAIResponse:
        def __init__(self):
            self.choices = [self.MockChoice()]
            self.model = model
            self.usage = {
                "total_tokens": 100,
                "completion_tokens": 50,
                "prompt_tokens": 50,
            }

        class MockChoice:
            def __init__(self):
                self.message = self.MockMessage()

            class MockMessage:
                def __init__(self):
                    self.content = content

    return MockAIResponse()
