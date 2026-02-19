"""
时间旅行测试框架使用示例

演示如何在测试中使用 TimeTravelClock 控制服务端时间
"""

import pytest
import asyncio
from datetime import date

# 导入时间旅行工具
from tests.framework.time_travel import (
    TimeTravelClock,
    travel_to,
    travel_days,
)


# ============ 配置 ============

@pytest.fixture(scope="session", autouse=True)
def configure_time_travel():
    """测试会话开始前配置时间旅行服务"""
    TimeTravelClock.configure(
        base_url="http://localhost:8000",
        secret="test-secret-123"  # 应与.env中的TEST_SECRET一致
    )


@pytest.fixture(autouse=True)
def reset_time_after_test():
    """每个测试结束后重置时间"""
    yield
    TimeTravelClock.reset()


# ============ 测试示例 ============

class TestDailyReportWithTimeTravel:
    """使用时间旅行的日报测试"""
    
    async def test_report_on_specific_date(self, client):
        """测试特定日期的日报生成"""
        # 冻结到2024年1月15日
        with travel_to("2024-01-15"):
            # 此时服务端认为今天是2024-01-15
            response = await client.get("/api/report/daily")
            
            assert response.status_code == 200
            data = response.json()
            
            # 验证日报日期
            assert data["date"] == "2024-01-15"
            
            # 验证"今天"的记录查询
            assert data["is_today"] is True
    
    async def test_weekly_streak_calculation(self, client):
        """测试连续打卡计算（跨日期）"""
        # 场景：用户在1月8日-14日连续打卡
        # 今天设为1月15日，检查连续7天
        
        with travel_to("2024-01-15"):
            response = await client.get("/api/habit/streak")
            
            data = response.json()
            # 验证连续7天
            assert data["current_streak"] == 7
            assert data["streak_dates"] == [
                "2024-01-08", "2024-01-09", "2024-01-10",
                "2024-01-11", "2024-01-12", "2024-01-13", "2024-01-14"
            ]
    
    async def test_achievement_unlock(self, client):
        """测试成就解锁时间判定"""
        # 场景：用户连续30天打卡，应该在第30天解锁成就
        
        with travel_to("2024-02-14"):  # 第30天
            response = await client.post("/api/habit/complete", json={
                "habit_id": "exercise",
                "date": "2024-02-14"
            })
            
            # 验证是否触发30天成就
            achievements = response.json().get("new_achievements", [])
            assert any(a["type"] == "STREAK_30" for a in achievements)
    
    async def test_time_offset(self, client):
        """测试时间偏移"""
        # 前进7天
        with travel_days(7):
            response = await client.get("/api/dashboard/today")
            
            data = response.json()
            # 验证日期是7天后
            expected_date = date.today() + __import__('datetime').timedelta(days=7)
            assert data["date"] == expected_date.isoformat()


class TestNotificationWithTimeTravel:
    """使用时间旅行的通知测试"""
    
    async def test_evening_reminder_at_specific_time(self, client):
        """测试晚间提醒在特定日期触发"""
        # 设定为晚上8点，应该触发晚间提醒
        with travel_to("2024-01-15T20:00:00"):
            response = await client.get("/api/reminder/check")
            
            reminders = response.json()["reminders"]
            # 验证有晚间总结提醒
            assert any(r["type"] == "evening_summary" for r in reminders)
    
    async def test_morning_reminder_at_specific_time(self, client):
        """测试晨间提醒在特定时间触发"""
        # 设定为早上8点，应该触发晨间提醒
        with travel_to("2024-01-15T08:00:00"):
            response = await client.get("/api/reminder/check")
            
            reminders = response.json()["reminders"]
            assert any(r["type"] == "morning_plan" for r in reminders)


class TestHabitWithTimeTravel:
    """使用时间旅行的习惯测试"""
    
    async def test_habit_completion_today(self, client):
        """测试今日习惯打卡"""
        with travel_to("2024-03-01"):
            # 打卡
            response = await client.post("/api/habit/complete", json={
                "habit_id": "morning_exercise"
            })
            
            assert response.status_code == 200
            
            # 查询今日打卡状态
            status_response = await client.get("/api/habit/today")
            status_data = status_response.json()
            
            # 验证今日已打卡
            exercise_habit = next(
                h for h in status_data["habits"] 
                if h["id"] == "morning_exercise"
            )
            assert exercise_habit["completed_today"] is True
            assert exercise_habit["completion_date"] == "2024-03-01"
    
    async def test_habit_streak_recovery(self, client):
        """测试习惯连续中断后恢复"""
        # 场景：用户1-5日打卡，6-7日中断，8日恢复
        
        with travel_to("2024-01-08"):
            # 查询连续记录
            response = await client.get("/api/habit/continuity")
            data = response.json()
            
            # 验证中断标记
            assert data["interrupted"] is True
            assert data["interruption_days"] == 2
            
            # 恢复打卡
            await client.post("/api/habit/complete", json={
                "habit_id": "daily_reading",
                "date": "2024-01-08"
            })
            
            # 验证恢复状态
            recovery_response = await client.get("/api/habit/continuity")
            recovery_data = recovery_response.json()
            
            assert recovery_data["recovering"] is True
            assert recovery_data["recovery_day"] == 1


# ============ 直接API调用示例 ============

def demo_api_calls():
    """演示直接API调用"""
    
    # 1. 冻结时间
    TimeTravelClock.freeze("2024-06-01")
    print("时间已冻结到2024-06-01")
    
    # 2. 获取服务端状态
    status = TimeTravelClock.get_status()
    print(f"服务端状态: {status}")
    
    # 3. 偏移时间（前进10天）
    TimeTravelClock.offset(days=10)
    print("时间前进10天")
    
    # 4. 重置时间
    TimeTravelClock.reset()
    print("时间已重置")


if __name__ == "__main__":
    print("时间旅行测试示例")
    print("=" * 50)
    print("\n运行方式:")
    print("1. 确保服务端启动: python main.py")
    print("2. 确保 .env 中 TEST_TIME_ENABLED=true")
    print("3. 运行测试: pytest docs/time_travel_test_example.py -v")
    print("\n或者直接调用API:")
    # demo_api_calls()  # 取消注释以运行
