#!/usr/bin/env python3
"""
Day 1 Test Infrastructure Verification Script
Verifies that the test infrastructure created on Day 1 works correctly.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from test_utils import UserDataFactory, WeightDataFactory
from ai_test_utils import QwenAPIMonitor, MockQwenClient


async def verify_test_utilities():
    """Verify test utility functions work correctly."""
    print("🔍 Verifying test utilities...")

    # Test data factory functions
    user_data = UserDataFactory.create_user_data()
    weight_data = WeightDataFactory.create_weight_data(user_id=1)

    assert "username" in user_data
    assert "email" in user_data
    assert "password" in user_data
    assert "weight" in weight_data
    assert "user_id" in weight_data

    print("✅ Test utilities verified successfully")
    return True


async def verify_qwen_monitor():
    """Verify Qwen API monitoring works correctly."""
    print("🔍 Verifying Qwen API monitoring...")

    monitor = QwenAPIMonitor()

    # Test mock client
    mock_client = MockQwenClient()
    assert mock_client is not None

    # Test API call tracking
    from datetime import datetime
    from ai_test_utils import QwenAPICall

    test_call = QwenAPICall(
        timestamp=datetime.now(),
        endpoint="test",
        model="qwen-turbo",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        response_time=0.5,
        success=True,
    )
    monitor.record_call(test_call)

    calls_today = len(monitor.calls_today)
    assert calls_today >= 1

    print(f"✅ Qwen API monitoring verified (calls today: {calls_today})")
    return True


async def verify_test_database():
    """Verify test database configuration."""
    print("🔍 Verifying test database configuration...")

    # Check if test database file exists
    test_db_path = project_root / "test_weight_management.db"
    assert test_db_path.exists(), f"Test database not found at {test_db_path}"

    # Check if .env.test exists
    env_test_path = project_root / ".env.test"
    assert env_test_path.exists(), f".env.test not found at {env_test_path}"

    # Check environment variables (some may not be set yet)
    print(f"  Test database: {test_db_path}")
    print(f"  Environment file: {env_test_path}")

    # Check if we can load the environment
    from dotenv import load_dotenv

    load_dotenv(env_test_path, override=True)

    # Now check for required variables
    assert "QWEN_API_KEY" in os.environ, "QWEN_API_KEY not set in environment"
    assert "DATABASE_URL" in os.environ, "DATABASE_URL not set in environment"

    print("✅ Test database configuration verified")
    return True


async def verify_fixtures():
    """Verify test fixtures can be imported."""
    print("🔍 Verifying test fixtures...")

    try:
        # Try to import fixtures from conftest
        from conftest import app, client

        print("✅ Test fixtures imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import fixtures: {e}")
        return False


async def main():
    """Run all verification checks."""
    print("🚀 Starting Day 1 Test Infrastructure Verification")
    print("=" * 50)

    results = []

    # Run verification checks
    results.append(await verify_test_database())
    results.append(await verify_test_utilities())
    results.append(await verify_qwen_monitor())
    results.append(await verify_fixtures())

    # Summary
    print("\n" + "=" * 50)
    print("📊 Verification Summary:")
    print(f"  Test Database: {'✅' if results[0] else '❌'}")
    print(f"  Test Utilities: {'✅' if results[1] else '❌'}")
    print(f"  Qwen Monitoring: {'✅' if results[2] else '❌'}")
    print(f"  Test Fixtures: {'✅' if results[3] else '❌'}")

    success_count = sum(results)
    total_count = len(results)

    if success_count == total_count:
        print(f"\n🎉 All {total_count} checks passed! Test infrastructure is ready.")
        return True
    else:
        print(
            f"\n⚠️  {success_count}/{total_count} checks passed. Some issues need attention."
        )
        return False


if __name__ == "__main__":
    # Load test environment
    from dotenv import load_dotenv

    env_test_path = project_root / ".env.test"
    load_dotenv(env_test_path, override=True)

    success = asyncio.run(main())
    sys.exit(0 if success else 1)
