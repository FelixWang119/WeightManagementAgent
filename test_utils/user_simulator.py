#!/usr/bin/env python3
"""
用户登录模拟器 - 可复用的测试工具
用于端到端测试的认证和数据管理
"""

import requests
import json
import hashlib
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../")


@dataclass
class TestUser:
    """测试用户数据类"""

    id: int
    nickname: str
    token: str
    code: str
    exercise_count: int = 0
    weight_count: int = 0
    has_ai_records: bool = False
    has_manual_checkins: bool = False


class UserSimulator:
    """
    用户登录模拟器
    用于创建、管理和测试用户
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.current_user: Optional[TestUser] = None
        self.users: Dict[str, TestUser] = {}  # code -> TestUser

    def generate_token(
        self, user_id: int, secret_key: str = "test-secret-key-change-in-production"
    ) -> str:
        """生成与后端一致的token"""
        data = f"{user_id}:{secret_key}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    def login(self, code: str = "test_user") -> Optional[TestUser]:
        """
        登录用户

        Args:
            code: 登录code，相同code会登录到同一用户

        Returns:
            TestUser对象或None（如果登录失败）
        """
        print(f"🔐 登录用户 (code: {code})...")

        try:
            response = requests.post(
                f"{self.base_url}/api/user/login", params={"code": code}, timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    user_data = data.get("user", {})

                    user = TestUser(
                        id=user_data.get("id"),
                        nickname=user_data.get("nickname", "未知用户"),
                        token=data.get("token"),
                        code=code,
                        exercise_count=0,
                        weight_count=0,
                    )

                    # 检查用户数据
                    self._check_user_data(user)

                    self.current_user = user
                    self.users[code] = user

                    print(f"✅ 登录成功: {user.nickname} (ID: {user.id})")
                    return user
                else:
                    print(f"❌ 登录失败: {data.get('error', '未知错误')}")
            else:
                print(f"❌ HTTP错误: {response.status_code}")

        except Exception as e:
            print(f"❌ 登录异常: {e}")

        return None

    def _check_user_data(self, user: TestUser):
        """检查用户数据"""
        headers = {"Authorization": f"Bearer {user.token}"}

        # 检查运动数据
        try:
            response = requests.get(
                f"{self.base_url}/api/exercise/checkins?include_all=true&limit=5",
                headers=headers,
                timeout=5,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    records = data.get("data", [])
                    stats = data.get("stats", {})

                    user.exercise_count = len(records)
                    user.has_ai_records = any(not r.get("is_checkin") for r in records)
                    user.has_manual_checkins = any(r.get("is_checkin") for r in records)

                    print(f"   运动记录: {user.exercise_count} 条")
                    print(f"   AI记录: {user.has_ai_records}")
                    print(f"   手动打卡: {user.has_manual_checkins}")
        except:
            pass

        # 检查体重数据
        try:
            response = requests.get(
                f"{self.base_url}/api/weight/records", headers=headers, timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    user.weight_count = len(data)
                    print(f"   体重记录: {user.weight_count} 条")
        except:
            pass

    def get_headers(self, user: Optional[TestUser] = None) -> Dict[str, str]:
        """获取认证headers"""
        target_user = user or self.current_user
        if not target_user:
            raise ValueError("没有登录用户")

        return {"Authorization": f"Bearer {target_user.token}"}

    def create_test_data(
        self,
        exercise_count: int = 3,
        weight_count: int = 5,
        include_ai_records: bool = True,
    ) -> bool:
        """
        为当前用户创建测试数据

        Args:
            exercise_count: 运动记录数量
            weight_count: 体重记录数量
            include_ai_records: 是否包含AI记录

        Returns:
            是否成功
        """
        if not self.current_user:
            print("❌ 请先登录用户")
            return False

        print(f"📊 为用户 {self.current_user.nickname} 创建测试数据...")

        success = True

        # 创建运动数据
        if exercise_count > 0:
            if not self._create_exercise_data(exercise_count, include_ai_records):
                success = False

        # 创建体重数据
        if weight_count > 0:
            if not self._create_weight_data(weight_count):
                success = False

        # 重新检查数据
        if success:
            self._check_user_data(self.current_user)
            print("✅ 测试数据创建完成")
        else:
            print("❌ 测试数据创建失败")

        return success

    def _create_exercise_data(self, count: int, include_ai: bool) -> bool:
        """创建运动数据"""
        headers = self.get_headers()

        exercise_types = [
            "跑步",
            "瑜伽",
            "游泳",
            "慢跑",
            "散步",
            "骑行",
            "跳绳",
            "力量训练",
        ]

        for i in range(count):
            exercise_type = exercise_types[i % len(exercise_types)]
            duration = 30 + (i * 10)  # 30, 40, 50分钟...
            calories = duration * 10  # 简单估算

            # 交替创建手动打卡和AI记录
            is_checkin = not include_ai or (i % 2 == 0)

            exercise_data = {
                "exercise_type": exercise_type,
                "duration_minutes": duration,
                "calories_burned": calories,
                "intensity": "medium",
                "is_checkin": is_checkin,
            }

            try:
                # 注意：这里需要根据实际API调整
                # 如果API需要不同的格式，请修改这里
                response = requests.post(
                    f"{self.base_url}/api/exercise/record",
                    headers=headers,
                    json=exercise_data,
                    timeout=5,
                )

                if response.status_code != 200:
                    print(f"⚠️ 创建运动记录失败: {response.status_code}")
                    # 继续尝试创建其他记录

            except Exception as e:
                print(f"⚠️ 创建运动记录异常: {e}")

        return True

    def _create_weight_data(self, count: int) -> bool:
        """创建体重数据"""
        headers = self.get_headers()

        base_weight = 65.0

        for i in range(count):
            weight = base_weight + (i * 0.5) - (count * 0.25)  # 创建变化趋势
            days_ago = count - i - 1

            weight_data = {
                "weight": weight,
                "record_date": (datetime.now() - timedelta(days=days_ago)).strftime(
                    "%Y-%m-%d"
                ),
            }

            try:
                # 注意：这里需要根据实际API调整
                response = requests.post(
                    f"{self.base_url}/api/weight/record",
                    headers=headers,
                    json=weight_data,
                    timeout=5,
                )

                if response.status_code != 200:
                    print(f"⚠️ 创建体重记录失败: {response.status_code}")
                    # 继续尝试创建其他记录

            except Exception as e:
                print(f"⚠️ 创建体重记录异常: {e}")

        return True

    def test_exercise_api(self) -> Dict[str, Any]:
        """测试运动API"""
        if not self.current_user:
            return {"error": "请先登录用户"}

        headers = self.get_headers()
        results = {}

        print("🧪 测试运动API...")

        # 测试1: 获取打卡记录（包含AI记录）
        try:
            response = requests.get(
                f"{self.base_url}/api/exercise/checkins?include_all=true&limit=10",
                headers=headers,
                timeout=5,
            )

            if response.status_code == 200:
                data = response.json()
                results["checkins"] = {
                    "success": data.get("success", False),
                    "record_count": len(data.get("data", [])),
                    "stats": data.get("stats", {}),
                }
                print(f"✅ 打卡记录: {results['checkins']['record_count']} 条")
            else:
                results["checkins"] = {"error": f"HTTP {response.status_code}"}
                print(f"❌ 打卡记录失败: {response.status_code}")
        except Exception as e:
            results["checkins"] = {"error": str(e)}
            print(f"❌ 打卡记录异常: {e}")

        # 测试2: 获取运动统计
        try:
            response = requests.get(
                f"{self.base_url}/api/exercise/stats", headers=headers, timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                results["stats"] = {
                    "success": data.get("success", False),
                    "data": data.get("data", {}),
                }
                print(f"✅ 运动统计: 获取成功")
            else:
                results["stats"] = {"error": f"HTTP {response.status_code}"}
                print(f"❌ 运动统计失败: {response.status_code}")
        except Exception as e:
            results["stats"] = {"error": str(e)}
            print(f"❌ 运动统计异常: {e}")

        return results

    def test_weight_api(self) -> Dict[str, Any]:
        """测试体重API"""
        if not self.current_user:
            return {"error": "请先登录用户"}

        headers = self.get_headers()
        results = {}

        print("🧪 测试体重API...")

        # 测试1: 获取体重记录
        try:
            response = requests.get(
                f"{self.base_url}/api/weight/records", headers=headers, timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    results["records"] = {"success": True, "record_count": len(data)}
                    print(f"✅ 体重记录: {len(data)} 条")
                else:
                    results["records"] = {
                        "success": data.get("success", False),
                        "record_count": len(data.get("data", []))
                        if isinstance(data.get("data"), list)
                        else 0,
                    }
                    print(f"✅ 体重记录: {results['records']['record_count']} 条")
            else:
                results["records"] = {"error": f"HTTP {response.status_code}"}
                print(f"❌ 体重记录失败: {response.status_code}")
        except Exception as e:
            results["records"] = {"error": str(e)}
            print(f"❌ 体重记录异常: {e}")

        # 测试2: 获取体重统计
        try:
            response = requests.get(
                f"{self.base_url}/api/weight/stats", headers=headers, timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                results["stats"] = {
                    "success": data.get("success", False),
                    "data": data.get("data", data),
                }
                print(f"✅ 体重统计: 获取成功")
            else:
                results["stats"] = {"error": f"HTTP {response.status_code}"}
                print(f"❌ 体重统计失败: {response.status_code}")
        except Exception as e:
            results["stats"] = {"error": str(e)}
            print(f"❌ 体重统计异常: {e}")

        return results

    def test_chat_api(self, message: str = "你好") -> Dict[str, Any]:
        """测试聊天API"""
        if not self.current_user:
            return {"error": "请先登录用户"}

        headers = self.get_headers()

        print(f"💬 测试聊天API: {message[:50]}...")

        try:
            chat_data = {
                "message": message,
                "session_id": f"test_session_{int(time.time())}",
            }

            response = requests.post(
                f"{self.base_url}/api/chat/send",
                headers=headers,
                json=chat_data,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": data.get("success", False),
                    "response": data.get("response", ""),
                    "has_tool_calls": "tool_calls" in data or "tools_used" in data,
                }
            else:
                return {
                    "error": f"HTTP {response.status_code}",
                    "response": response.text,
                }

        except Exception as e:
            return {"error": str(e)}

    def run_full_test(
        self, test_code: str = "full_test_user", create_data: bool = True
    ) -> Dict[str, Any]:
        """
        运行完整测试

        Args:
            test_code: 测试用户code
            create_data: 是否创建测试数据

        Returns:
            测试结果
        """
        print("=" * 60)
        print("运行完整端到端测试")
        print("=" * 60)

        results = {}

        # 1. 登录用户
        user = self.login(test_code)
        if not user:
            return {"error": "登录失败"}

        results["login"] = {
            "success": True,
            "user_id": user.id,
            "nickname": user.nickname,
        }

        # 2. 创建测试数据
        if create_data:
            data_created = self.create_test_data(
                exercise_count=4, weight_count=3, include_ai_records=True
            )
            results["data_creation"] = {"success": data_created}

        # 3. 测试运动API
        exercise_results = self.test_exercise_api()
        results["exercise_api"] = exercise_results

        # 4. 测试体重API
        weight_results = self.test_weight_api()
        results["weight_api"] = weight_results

        # 5. 测试聊天API（基础）
        chat_results = self.test_chat_api("你好，请介绍一下你自己")
        results["chat_api_basic"] = chat_results

        # 6. 测试聊天API（体重记录）
        if "success" in chat_results and chat_results["success"]:
            weight_chat_results = self.test_chat_api("我体重65.5kg")
            results["chat_api_weight"] = weight_chat_results

            # 7. 测试聊天API（运动记录）
            exercise_chat_results = self.test_chat_api("我今天慢跑了5公里，用时50分钟")
            results["chat_api_exercise"] = exercise_chat_results

        print("=" * 60)
        print("测试完成!")
        print("=" * 60)

        return results

    def save_test_report(
        self, results: Dict[str, Any], filename: str = "test_report.json"
    ):
        """保存测试报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "user": {
                "id": self.current_user.id if self.current_user else None,
                "nickname": self.current_user.nickname if self.current_user else None,
                "code": self.current_user.code if self.current_user else None,
            },
            "results": results,
        }

        os.makedirs("test_reports", exist_ok=True)
        filepath = os.path.join("test_reports", filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"📄 测试报告已保存: {filepath}")
        return filepath


# 预定义的测试用户
PREDEFINED_USERS = {
    "exercise_test_user": {
        "description": "运动测试用户（已有数据）",
        "code": "exercise_test_user",
    },
    "weight_test_user": {"description": "体重测试用户", "code": "weight_test_user"},
    "chat_test_user": {"description": "聊天测试用户", "code": "chat_test_user"},
    "full_test_user": {"description": "完整测试用户", "code": "full_test_user"},
}


def quick_test(user_code: str = "quick_test"):
    """快速测试函数"""
    simulator = UserSimulator()

    print(f"🚀 快速测试: {user_code}")

    # 登录
    user = simulator.login(user_code)
    if not user:
        print("❌ 登录失败")
        return

    # 简单测试
    print("\n1. 测试运动API:")
    exercise_results = simulator.test_exercise_api()

    print("\n2. 测试体重API:")
    weight_results = simulator.test_weight_api()

    print("\n3. 测试聊天API:")
    chat_results = simulator.test_chat_api("你好")

    if chat_results.get("success"):
        print(f"   AI回复: {chat_results.get('response', '')[:100]}...")

    return {
        "user": user,
        "exercise": exercise_results,
        "weight": weight_results,
        "chat": chat_results,
    }


if __name__ == "__main__":
    # 示例用法
    import argparse

    parser = argparse.ArgumentParser(description="用户登录模拟器")
    parser.add_argument("--code", default="demo_user", help="登录code")
    parser.add_argument("--create-data", action="store_true", help="创建测试数据")
    parser.add_argument("--full-test", action="store_true", help="运行完整测试")

    args = parser.parse_args()

    simulator = UserSimulator()

    if args.full_test:
        results = simulator.run_full_test(args.code, args.create_data)
        simulator.save_test_report(results, f"full_test_{args.code}.json")
    else:
        user = simulator.login(args.code)
        if user and args.create_data:
            simulator.create_test_data()

        # 简单测试
        simulator.test_exercise_api()
        simulator.test_weight_api()
