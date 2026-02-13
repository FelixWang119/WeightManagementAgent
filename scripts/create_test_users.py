#!/usr/bin/env python3
"""
测试用户创建脚本
通过微信登录API创建4个测试用户并获取认证token
"""

import requests
import json
import hashlib
from typing import Dict, List

def create_test_user(user_index: int, user_data: dict) -> Dict:
    """创建测试用户并获取token"""
    base_url = "http://127.0.0.1:8000"
    
    # 为每个用户生成唯一的微信code
    # 使用固定的salt确保相同用户总是得到相同token
    code_salt = f"test_user_{user_index}_{user_data['name']}"
    code = hashlib.md5(code_salt.encode()).hexdigest()[:16]
    
    print(f"创建用户: {user_data['name']} (code: {code})...")
    
    try:
        # 调用微信登录API
        response = requests.post(
            f"{base_url}/api/user/login?code={code}",
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                result = {
                    "success": True,
                    "user_id": data["user"]["id"],
                    "token": data["token"],
                    "is_new": data["is_new"],
                    "user_info": data["user"],
                    "profile": user_data,
                    "code": code  # 保存code以便后续使用
                }
                
                # 更新用户资料（昵称、年龄等）
                update_profile(base_url, data["token"], user_data)
                
                return result
            else:
                return {
                    "success": False,
                    "error": f"API返回失败: {data}"
                }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def update_profile(base_url: str, token: str, user_data: dict):
    """更新用户资料"""
    try:
        # 构建更新数据
        update_data = {}
        
        # 设置昵称
        if user_data.get("name"):
            update_data["nickname"] = user_data["name"]
        
        # 设置年龄
        if user_data.get("age"):
            update_data["age"] = user_data["age"]
        
        # 设置性别
        if user_data.get("gender"):
            update_data["gender"] = user_data["gender"]
        
        if update_data:
            response = requests.put(
                f"{base_url}/api/user/profile",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=update_data,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"  ✓ 用户资料更新成功")
            else:
                print(f"  ⚠ 用户资料更新失败: HTTP {response.status_code}")
    
    except Exception as e:
        print(f"  ⚠ 用户资料更新异常: {e}")

def main():
    """主函数：创建4个测试用户"""
    print("🚀 开始创建测试用户...")
    print("=" * 60)
    
    # 4个测试用户数据（对应智能聊天测试的4种画像）
    test_users = [
        {
            "name": "王建国",
            "age": 48,
            "gender": "male",
            "health_goal": "控制血压，减重5kg",
            "occupation": "公务员",
            "user_type": "middle_age_official"
        },
        {
            "name": "李思思", 
            "age": 28,
            "gender": "female",
            "health_goal": "塑形减脂，保持身材",
            "occupation": "互联网产品经理",
            "user_type": "female_office_worker"
        },
        {
            "name": "张明",
            "age": 22,
            "gender": "male",
            "health_goal": "改善作息，控制体重",
            "occupation": "大学生",
            "user_type": "college_student"
        },
        {
            "name": "陈奶奶",
            "age": 65,
            "gender": "female",
            "health_goal": "控制血糖，保持活动",
            "occupation": "退休",
            "user_type": "retired_elder"
        }
    ]
    
    results = []
    
    for i, user_data in enumerate(test_users):
        result = create_test_user(i, user_data)
        results.append(result)
        
        if result["success"]:
            print(f"  ✓ 成功创建用户: {user_data['name']}")
            print(f"     用户ID: {result['user_id']}")
            print(f"     令牌: {result['token'][:20]}...")
            print(f"     是否新用户: {result['is_new']}")
        else:
            print(f"  ✗ 创建失败: {result['error']}")
        
        print()  # 空行分隔
    
    # 保存结果到文件
    output_file = "test_users_tokens.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"📁 用户令牌已保存到: {output_file}")
    
    # 统计结果
    successful = sum(1 for r in results if r["success"])
    print(f"📊 创建结果: {successful}/{len(test_users)} 成功")
    
    # 显示token摘要
    print("\n🔑 Token摘要:")
    for result in results:
        if result["success"]:
            user_name = result["profile"]["name"]
            token = result["token"]
            print(f"  {user_name}: {token[:20]}...")
    
    # 创建测试框架可用的映射文件
    create_test_framework_mapping(results)
    
    return results

def create_test_framework_mapping(results: List[Dict]):
    """创建测试框架使用的用户映射文件"""
    mapping = {}
    
    for result in results:
        if result["success"]:
            user_id = result["user_id"]
            profile = result["profile"]
            
            mapping[user_id] = {
                "token": result["token"],
                "name": profile["name"],
                "age": profile["age"],
                "occupation": profile["occupation"],
                "health_goal": profile["health_goal"],
                "user_type": profile["user_type"],
                "code": result.get("code", "")
            }
    
    mapping_file = "test_users_mapping.json"
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    
    print(f"📁 用户映射已保存到: {mapping_file}")
    
    # 创建环境变量文件示例
    env_example = """# 测试用户环境变量示例
# 复制到 .env.test 文件使用

# 王建国 (公务员)
TEST_USER_1_ID={user_id_1}
TEST_USER_1_TOKEN={token_1}
TEST_USER_1_NAME=王建国

# 李思思 (产品经理)
TEST_USER_2_ID={user_id_2}
TEST_USER_2_TOKEN={token_2}
TEST_USER_2_NAME=李思思

# 张明 (大学生)
TEST_USER_3_ID={user_id_3}
TEST_USER_3_TOKEN={token_3}
TEST_USER_3_NAME=张明

# 陈奶奶 (退休)
TEST_USER_4_ID={user_id_4}
TEST_USER_4_TOKEN={token_4}
TEST_USER_4_NAME=陈奶奶
""".format(
        user_id_1=mapping.get(list(mapping.keys())[0], {}).get("token", "") if mapping else "",
        token_1=mapping.get(list(mapping.keys())[0], {}).get("token", "") if mapping else "",
        user_id_2=mapping.get(list(mapping.keys())[1], {}).get("token", "") if len(mapping) > 1 else "",
        token_2=mapping.get(list(mapping.keys())[1], {}).get("token", "") if len(mapping) > 1 else "",
        user_id_3=mapping.get(list(mapping.keys())[2], {}).get("token", "") if len(mapping) > 2 else "",
        token_3=mapping.get(list(mapping.keys())[2], {}).get("token", "") if len(mapping) > 2 else "",
        user_id_4=mapping.get(list(mapping.keys())[3], {}).get("token", "") if len(mapping) > 3 else "",
        token_4=mapping.get(list(mapping.keys())[3], {}).get("token", "") if len(mapping) > 3 else "",
    )
    
    with open(".env.test.example", 'w', encoding='utf-8') as f:
        f.write(env_example)
    
    print(f"📁 环境变量示例已保存到: .env.test.example")

if __name__ == "__main__":
    try:
        results = main()
        
        print("\n" + "=" * 60)
        if any(r["success"] for r in results):
            print("✅ 测试用户创建完成!")
            print("   现在可以运行真实API测试了")
        else:
            print("❌ 测试用户创建失败")
            print("   请检查API服务是否正常运行")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 脚本执行失败: {e}")
        import traceback
        traceback.print_exc()