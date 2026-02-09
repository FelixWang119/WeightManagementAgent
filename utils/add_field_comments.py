#!/usr/bin/env python3
"""
为数据库字段添加中文注释
"""

import re

# 字段注释映射
field_comments = {
    # users 表
    'openid': '微信用户唯一标识',
    'nickname': '用户昵称',
    'avatar_url': '头像URL',
    'phone': '手机号',
    'is_vip': '是否VIP会员',
    'vip_expire': 'VIP过期时间',
    
    # weight_records 表
    'weight': '体重（kg）',
    'body_fat': '体脂率（%）',
    'record_date': '记录日期',
    'record_time': '记录时间',
    'note': '备注',
    
    # meal_records 表
    'meal_type': '餐食类型（早餐/午餐/晚餐/加餐）',
    'photo_url': '餐食照片URL',
    'food_items': '食物明细（JSON格式）',
    'total_calories': '总热量（千卡）',
    'user_confirmed': '用户是否确认识别结果',
    'ai_confidence': 'AI识别置信度（0-1）',
    
    # exercise_records 表
    'exercise_type': '运动类型',
    'duration_minutes': '运动时长（分钟）',
    'calories_burned': '消耗热量（千卡）',
    'intensity': '运动强度（低/中/高）',
    'photo_evidence': '运动凭证照片',
    
    # water_records 表
    'amount_ml': '饮水量（毫升）',
    
    # sleep_records 表
    'bed_time': '入睡时间',
    'wake_time': '起床时间',
    'total_minutes': '睡眠总时长（分钟）',
    'quality': '睡眠质量评分（1-5星）',
    
    # user_profiles 表
    'age': '年龄',
    'gender': '性别',
    'height': '身高（cm）',
    'bmr': '基础代谢率（BMR）',
    'diet_preferences': '饮食偏好（JSON）',
    'exercise_habits': '运动习惯（JSON）',
    'weight_history': '减重历史记录',
    'body_signals': '身体信号（JSON：疲劳/失眠等）',
    'motivation_type': '动力类型（数据驱动/情感支持/目标导向）',
    'weak_points': '薄弱环节（JSON）',
    'memory_summary': 'AI记忆摘要（自然语言描述）',
    
    # goals 表
    'target_weight': '目标体重（kg）',
    'target_date': '目标达成日期',
    'weekly_plan': '每周减重计划（kg）',
    'daily_calorie_target': '每日热量目标（千卡）',
    'meal_distribution': '三餐热量分配比例（JSON）',
    
    # agent_configs 表
    'agent_name': 'Agent名称',
    'personality_type': '性格类型（专业/温暖/活力）',
    'personality_prompt': '性格Prompt描述',
    
    # chat_history 表
    'role': '消息角色（user/assistant/system）',
    'content': '消息内容',
    'msg_type': '消息类型（text/card/image/form）',
    'metadata': '元数据（JSON）',
    
    # conversation_summaries 表
    'week_start': '周开始日期',
    'summary_text': '对话摘要文本',
    'key_facts': '关键事实（JSON）',
    
    # reminder_settings 表
    'reminder_type': '提醒类型',
    'enabled': '是否启用',
    'reminder_time': '提醒时间',
    'interval_minutes': '间隔分钟数（饮水用）',
    'weekdays_only': '仅工作日提醒',
    'last_triggered': '上次触发时间',
    'skip_count': '连续忽略次数',
    
    # do_not_disturb 表
    'start_time': '开始时间',
    'end_time': '结束时间',
    'except_emergencies': '紧急提醒例外',
    
    # food_items 表
    'name': '食物名称',
    'aliases': '别名列表（JSON）',
    'category': '食物分类',
    'calories_per_100g': '每100克热量（千卡）',
    'protein': '蛋白质含量（g/100g）',
    'fat': '脂肪含量（g/100g）',
    'carbs': '碳水化合物（g/100g）',
    'common_portions': '常见分量（JSON）',
    'is_user_created': '是否用户自定义',
    
    # achievements 表
    'code': '成就代码（唯一标识）',
    'description': '成就描述',
    'icon': '图标URL或代码',
    'condition_type': '达成条件类型',
    'condition_value': '达成条件值',
    
    # user_achievements 表
    'unlocked_at': '解锁时间',
    
    # challenges 表
    'title': '挑战标题',
    'type': '挑战类型（日/周/自定义）',
    'target': '挑战目标（JSON）',
    'reward_points': '奖励积分',
    
    # user_challenges 表
    'progress': '进度（JSON）',
    'status': '状态（进行中/已完成/已失败）',
    'started_at': '开始时间',
    'completed_at': '完成时间',
    
    # user_points 表
    'total_points': '累计积分',
    'current_points': '当前可用积分',
    
    # weekly_reports 表
    'weight_change': '体重变化（kg）',
    'avg_weight': '平均体重（kg）',
    'avg_calories_in': '平均摄入热量（千卡）',
    'avg_calories_out': '平均消耗热量（千卡）',
    'exercise_days': '运动天数',
    'highlights': '本周亮点（JSON）',
    'improvements': '改进建议（JSON）',
    
    # nutritionists 表
    'specialties': '专长领域（JSON）',
    'intro': '个人简介',
    'is_active': '是否在职',
    
    # consultations 表
    'question': '咨询问题',
    'answer': '营养师回答',
    'answered_at': '回答时间',
}

def add_comments_to_md(md_content):
    """为Markdown中的数据库字段添加中文注释"""
    lines = md_content.split('\n')
    result = []
    
    for line in lines:
        # 匹配字段定义行：  - field_name: type
        match = re.match(r'^(\s+-\s+)(\w+)(:\s+\w+.*)', line)
        if match:
            indent = match.group(1)
            field_name = match.group(2)
            type_info = match.group(3)
            
            # 如果已经有中文注释，跳过
            if '（' in type_info or '#' in type_info:
                result.append(line)
                continue
            
            # 添加中文注释
            if field_name in field_comments:
                comment = field_comments[field_name]
                # 检查是否已有括号
                if '(' in type_info:
                    new_line = f"{indent}{field_name}{type_info}  # {comment}"
                else:
                    new_line = f"{indent}{field_name}{type_info}  # {comment}"
                result.append(new_line)
            else:
                result.append(line)
        else:
            result.append(line)
    
    return '\n'.join(result)

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python add_field_comments.py <md_file>")
        sys.exit(1)
    
    md_file = sys.argv[1]
    
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = add_comments_to_md(content)
    
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ 已为字段添加中文注释: {md_file}")
