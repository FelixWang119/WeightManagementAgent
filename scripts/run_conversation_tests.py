#!/usr/bin/env python3
"""
多轮对话测试运行器

运行方式：
1. 快速运行（默认）：python run_conversation_tests.py
2. 详细模式：python run_conversation_tests.py --verbose
3. 运行特定测试类：python run_conversation_tests.py --class TestMultiTurnConversationUnit
4. 运行集成测试：python run_conversation_tests.py --integration
5. 运行端到端测试（需要启动服务器）：python run_conversation_tests.py --e2e

注意：端到端测试需要先启动服务器：
python -m uvicorn main_new:app --host 0.0.0.0 --port 8000 --reload
"""

import sys
import argparse
import subprocess
import time
from pathlib import Path


def run_unit_tests(verbose=False):
    """运行单元测试"""
    print("🧪 运行单元测试 (Mock AI服务)")
    print("=" * 60)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_multi_turn_conversation.py::TestMultiTurnConversationUnit",
        "-v" if verbose else "-q",
        "--tb=short"
    ]
    
    return subprocess.run(cmd, cwd=Path(__file__).parent)


def run_integration_tests(verbose=False):
    """运行集成测试"""
    print("🧪 运行集成测试 (真实数据库 + Mock AI)")
    print("=" * 60)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_multi_turn_conversation.py::TestMultiTurnConversationIntegration",
        "-v" if verbose else "-q",
        "--tb=short"
    ]
    
    return subprocess.run(cmd, cwd=Path(__file__).parent)


def run_e2e_tests(verbose=False):
    """运行端到端测试（需要服务器运行）"""
    print("🧪 运行端到端测试 (真实API调用)")
    print("=" * 60)
    print("⚠️  注意：端到端测试需要服务器正在运行")
    print("    启动服务器: python -m uvicorn main_new:app --host 0.0.0.0 --port 8000 --reload")
    print()
    
    # 检查服务器是否运行
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ 检测到服务器正在运行")
        else:
            print("❌ 服务器响应异常")
            return 1
    except:
        print("❌ 无法连接到服务器，请先启动服务器")
        return 1
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_multi_turn_conversation.py::TestMultiTurnConversationE2E",
        "-v" if verbose else "-q",
        "--tb=short",
        "-k", "not test_weight_tracking_e2e_scenario"  # 跳过需要手动运行的测试
    ]
    
    return subprocess.run(cmd, cwd=Path(__file__).parent)


def run_all_tests(verbose=False):
    """运行所有测试"""
    print("🧪 运行完整的多轮对话测试套件")
    print("=" * 60)
    print("测试策略：70%单元测试 + 20%集成测试 + 10%端到端测试")
    print()
    
    results = []
    
    # 运行单元测试
    print("1. 单元测试 (70%) - Mock AI服务")
    result1 = run_unit_tests(verbose)
    results.append(("单元测试", result1.returncode))
    
    if result1.returncode != 0:
        print("\n⚠️  单元测试失败，跳过后续测试")
        return result1.returncode
    
    print("\n" + "=" * 60)
    
    # 运行集成测试
    print("2. 集成测试 (20%) - 真实数据库 + Mock AI")
    result2 = run_integration_tests(verbose)
    results.append(("集成测试", result2.returncode))
    
    if result2.returncode != 0:
        print("\n⚠️  集成测试失败，跳过端到端测试")
    
    print("\n" + "=" * 60)
    
    # 运行端到端测试
    print("3. 端到端测试 (10%) - 真实API调用")
    result3 = run_e2e_tests(verbose)
    results.append(("端到端测试", result3.returncode))
    
    # 输出总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    
    all_passed = True
    for test_type, returncode in results:
        status = "✅ 通过" if returncode == 0 else "❌ 失败"
        print(f"{test_type:<15} {status}")
        if returncode != 0:
            all_passed = False
    
    if all_passed:
        print("\n🎉 所有测试通过！减重助手的记忆和风格切换功能正常。")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查相关功能。")
        return 1


def run_specific_test(test_class=None, test_method=None, verbose=False):
    """运行特定测试"""
    if test_class:
        test_path = f"tests/test_multi_turn_conversation.py::{test_class}"
        if test_method:
            test_path += f"::{test_method}"
        
        print(f"🧪 运行特定测试: {test_path}")
        print("=" * 60)
        
        cmd = [
            sys.executable, "-m", "pytest",
            test_path,
            "-v" if verbose else "-q",
            "--tb=short"
        ]
        
        return subprocess.run(cmd, cwd=Path(__file__).parent).returncode
    else:
        print("❌ 请指定测试类名")
        return 1


def create_test_data():
    """创建测试数据（用于手动测试）"""
    print("📊 创建测试数据")
    print("=" * 60)
    
    # 创建测试用户画像和Agent配置
    test_script = """
import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from models.database import Base, User, UserProfile, AgentConfig
from services.user_profile_service import UserProfileService

async def create_test_data():
    # 使用内存数据库
    DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    # 创建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建会话
    from sqlalchemy.ext.asyncio import AsyncSession
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        # 创建测试用户
        user = User(
            id=999,
            openid="test_openid_999",
            nickname="测试用户999"
        )
        db.add(user)
        
        # 创建用户画像
        profile = UserProfile(
            user_id=999,
            age=30,
            gender="男性",
            height=175.0,
            bmr=1600
        )
        db.add(profile)
        
        # 创建Agent配置（温暖型）
        agent_config = AgentConfig(
            user_id=999,
            agent_name="小助",
            personality_type="warm",
            personality_prompt="测试提示词"
        )
        db.add(agent_config)
        
        await db.commit()
        print("✅ 测试数据创建完成")
        
        # 测试获取用户画像
        profile_data = await UserProfileService.get_complete_profile(999, db)
        print(f"📋 用户画像数据: {profile_data['personality_type']}风格")

if __name__ == "__main__":
    asyncio.run(create_test_data())
"""
    
    with open("temp/create_test_data.py", "w") as f:
        f.write(test_script)
    
    print("📁 测试数据脚本已创建: temp/create_test_data.py")
    print("🚀 运行: python temp/create_test_data.py")


def main():
    parser = argparse.ArgumentParser(description="多轮对话测试运行器")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--unit", action="store_true", help="只运行单元测试")
    parser.add_argument("--integration", action="store_true", help="只运行集成测试")
    parser.add_argument("--e2e", action="store_true", help="只运行端到端测试")
    parser.add_argument("--class", dest="test_class", help="运行特定测试类")
    parser.add_argument("--method", dest="test_method", help="运行特定测试方法")
    parser.add_argument("--create-data", action="store_true", help="创建测试数据")
    
    args = parser.parse_args()
    
    if args.create_data:
        create_test_data()
        return 0
    
    if args.test_class:
        return run_specific_test(args.test_class, args.test_method, args.verbose)
    elif args.unit:
        return run_unit_tests(args.verbose).returncode
    elif args.integration:
        return run_integration_tests(args.verbose).returncode
    elif args.e2e:
        return run_e2e_tests(args.verbose).returncode
    else:
        return run_all_tests(args.verbose)


if __name__ == "__main__":
    sys.exit(main())