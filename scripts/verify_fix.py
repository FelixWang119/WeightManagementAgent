#!/usr/bin/env python3
"""
验证运动记录修复效果
"""

import asyncio
import sys
import os
import aiohttp
import json

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def verify_fix():
    """验证修复效果"""
    print("🔍 验证运动记录修复效果...\n")
    
    async with aiohttp.ClientSession() as session:
        try:
            # 登录获取token
            test_code = "test_code_123456"
            async with session.post(f"http://localhost:8000/api/user/login?code={test_code}") as response:
                if response.status == 200:
                    login_data = await response.json()
                    token = login_data.get('token')
                    user_id = login_data.get('user', {}).get('id')
                    print(f"✅ 登录成功")
                    print(f"   用户ID: {user_id}")
                    print(f"   Token: {token[:10]}...")
                else:
                    print(f"❌ 登录失败: {response.status}")
                    return
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # 测试1：获取打卡历史
            print("\n📊 测试1：获取打卡历史")
            async with session.get("http://localhost:8000/api/exercise/checkins?limit=10", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    records = data.get('data', [])
                    
                    print(f"   返回记录数: {len(records)}")
                    
                    if records:
                        print("   记录详情：")
                        for i, record in enumerate(records, 1):
                            print(f"   #{i}: {record.get('exercise_type')} {record.get('duration_minutes')}分钟 {record.get('intensity')}")
                            print(f"       消耗热量: {record.get('calories_burned')}千卡")
                            print(f"       打卡日期: {record.get('checkin_date')}")
                        
                        # 检查是否有相同数据
                        unique_data = set()
                        duplicate_count = 0
                        
                        for record in records:
                            key = (record.get('exercise_type'), record.get('duration_minutes'), record.get('intensity'))
                            if key in unique_data:
                                duplicate_count += 1
                            else:
                                unique_data.add(key)
                        
                        if duplicate_count > 0:
                            print(f"   ⚠️  发现 {duplicate_count} 条重复记录")
                        else:
                            print("   ✅ 所有记录数据都不同")
                    else:
                        print("   ⚠️  没有返回数据")
                else:
                    error_text = await response.text()
                    print(f"   ❌ API请求失败: {error_text}")
            
            # 测试2：创建多样化打卡记录
            print("\n🏃 测试2：创建多样化打卡记录")
            
            exercise_types = ["跑步", "游泳", "瑜伽", "力量训练"]
            durations = [30, 45, 60, 90]
            intensities = ["low", "medium", "high"]
            
            for i, exercise_type in enumerate(exercise_types[:2]):  # 创建2条新记录
                checkin_data = {
                    "exercise_type": exercise_type,
                    "duration_minutes": durations[i],
                    "intensity": intensities[i % 3]
                }
                
                async with session.post("http://localhost:8000/api/exercise/checkin", 
                                       headers=headers, 
                                       json=checkin_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        print(f"   ✅ 创建记录: {exercise_type} {durations[i]}分钟 {intensities[i % 3]}")
                    else:
                        print(f"   ❌ 创建失败: {exercise_type}")
            
            # 测试3：重新检查记录
            print("\n📊 测试3：重新检查记录")
            async with session.get("http://localhost:8000/api/exercise/checkins?limit=10", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    records = data.get('data', [])
                    
                    print(f"   总记录数: {len(records)}")
                    print("   最终记录详情：")
                    
                    for i, record in enumerate(records[:5], 1):  # 显示前5条
                        print(f"   #{i}: {record.get('exercise_type')} {record.get('duration_minutes')}分钟 {record.get('intensity')}")
            
        except Exception as e:
            print(f"❌ 验证过程中出错: {e}")
            import traceback
            traceback.print_exc()

async def main():
    """主函数"""
    await verify_fix()
    print("\n✅ 验证完成")

if __name__ == "__main__":
    asyncio.run(main())