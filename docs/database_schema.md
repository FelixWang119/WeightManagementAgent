# 数据库结构文档

> 📌 **最后更新**: 2026-02-14

## 概述

体重管理助手使用SQLite数据库，通过SQLAlchemy ORM进行数据管理。数据库在应用启动时自动创建。

## 数据库初始化

### 自动初始化
当启动应用时，数据库会自动创建：
```bash
python main.py
```

### 手动初始化
如果需要手动初始化数据库：
```bash
python scripts/init_database.py
```

## 表结构总览

本系统共有 **26个数据表**：

| 序号 | 表名 | 说明 |
|-----|------|------|
| 1 | users | 用户表 |
| 2 | user_profiles | 用户画像表 |
| 3 | weight_records | 体重记录表 |
| 4 | meal_records | 餐食记录表 |
| 5 | exercise_records | 运动记录表 |
| 6 | water_records | 饮水记录表 |
| 7 | sleep_records | 睡眠记录表 |
| 8 | goals | 目标表 |
| 9 | agent_configs | Agent配置表 |
| 10 | chat_history | 聊天历史表 |
| 11 | conversation_summaries | 对话摘要表 |
| 12 | food_items | 食物项目表 |
| 13 | user_foods | 用户食物表 |
| 14 | recipes | 食谱表 |
| 15 | recipe_ingredients | 食谱食材表 |
| 16 | recipe_steps | 食谱步骤表 |
| 17 | user_recipes | 用户食谱表 |
| 18 | weekly_reports | 周报表 |
| 19 | reminder_settings | 提醒设置表 |
| 20 | notification_queue | 通知队列表 |
| 21 | profiling_answers | 用户画像答案表 |
| 22 | user_profile_cache | 用户画像缓存表 |
| 23 | system_prompts | 系统提示词表 |
| 24 | prompt_versions | 提示词版本表 |
| 25 | system_config | 系统配置表 |
| 26 | system_backups | 系统备份表 |

---

## 详细表结构

### 1. 用户表 (users)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| openid | String(100) | Unique, Index | 微信用户唯一标识 |
| nickname | String(100) | | 用户昵称 |
| avatar_url | String(500) | | 头像URL |
| phone | String(20) | Nullable | 手机号 |
| created_at | DateTime | Default | 创建时间 |
| last_login | DateTime | Auto | 最后登录时间 |
| is_vip | Boolean | Default=False | 是否VIP会员 |
| vip_expire | Date | Nullable | VIP过期时间 |
| is_admin | Boolean | Default=False | 是否管理员 |
| admin_role | String(20) | Nullable | 管理员角色: super/admin/viewer |
| admin_permissions | JSON | Nullable | 管理员权限配置 |
| last_admin_login | DateTime | Nullable | 最后管理员登录时间 |

**关系**: 
- `weight_records` → WeightRecord (一对多)
- `meal_records` → MealRecord (一对多)
- `exercise_records` → ExerciseRecord (一对多)
- `water_records` → WaterRecord (一对多)
- `sleep_records` → SleepRecord (一对多)
- `goals` → Goal (一对多)
- `profile` → UserProfile (一对一)
- `agent_config` → AgentConfig (一对一)
- `profile_cache` → UserProfileCache (一对一)
- `chat_history` → ChatHistory (一对多)

---

### 2. 用户画像表 (user_profiles)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | Unique, FK | 关联users.id |
| age | Integer | Nullable | 年龄 |
| gender | String(10) | Nullable | 性别 (male/female) |
| height | Float | Nullable | 身高 (cm) |
| bmr | Integer | Nullable | 基础代谢率 |
| diet_preferences | JSON | Nullable | 饮食偏好 |
| exercise_habits | JSON | Nullable | 运动习惯 |
| weight_history | Text | Nullable | 减重历史记录 |
| body_signals | JSON | Nullable | 身体信号 (疲劳/失眠等) |
| motivation_type | Enum | Nullable | 动力类型 |
| weak_points | JSON | Nullable | 薄弱环节 |
| memory_summary | Text | Nullable | AI记忆摘要 |
| decision_mode | String(20) | Default=balanced | 决策模式 |
| achievements | JSON | Nullable | 已解锁成就列表 |
| points | Integer | Default=0 | 当前积分 |
| total_points_earned | Integer | Default=0 | 累计获得积分 |
| total_points_spent | Integer | Default=0 | 累计消耗积分 |
| communication_style | String(20) | Nullable | 沟通风格 |
| updated_at | DateTime | Auto | 更新时间 |

**关系**: User (一对一)

---

### 3. 体重记录表 (weight_records)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | FK, Index | 关联users.id |
| weight | Float | | 体重 (kg) |
| body_fat | Float | Nullable | 体脂率 (%) |
| record_date | Date | Index | 记录日期 |
| record_time | DateTime | | 记录时间 |
| notes | String(500) | Nullable | 备注 |
| created_at | DateTime | Default | 创建时间 |

**关系**: User (多对一)

---

### 4. 餐食记录表 (meal_records)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | FK, Index | 关联users.id |
| meal_type | Enum | | 餐食类型 |
| content | Text | Nullable | 文字描述 |
| food_items | JSON | Nullable | 食物列表 |
| total_calories | Integer | Nullable | 总热量 |
| photo_url | String(500) | Nullable | 照片URL |
| record_time | DateTime | Index | 记录时间 |
| confirmed | Boolean | Default=False | 是否已确认 |
| confirmed_at | DateTime | Nullable | 确认时间 |
| created_at | DateTime | Default | 创建时间 |

**枚举值 (MealType)**:
- `BREAKFAST` - 早餐
- `LUNCH` - 午餐
- `DINNER` - 晚餐
- `SNACK` - 加餐

**关系**: User (多对一)

---

### 5. 运动记录表 (exercise_records)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | FK, Index | 关联users.id |
| exercise_type | String(50) | | 运动类型 |
| duration_minutes | Integer | | 运动时长 (分钟) |
| calories_burned | Integer | Nullable | 消耗热量 |
| intensity | Enum | | 运动强度 |
| record_time | DateTime | Index | 记录时间 |
| photo_evidence | String(500) | Nullable | 运动凭证照片 |
| is_checkin | Boolean | Default=False | 是否为打卡记录 |
| checkin_date | Date | Nullable | 打卡日期 |
| created_at | DateTime | Default | 创建时间 |

**枚举值 (ExerciseIntensity)**:
- `LOW` - 低强度
- `MEDIUM` - 中强度
- `HIGH` - 高强度

**关系**: User (多对一)

---

### 6. 饮水记录表 (water_records)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | FK, Index | 关联users.id |
| amount_ml | Integer | | 饮水量 (毫升) |
| record_time | DateTime | Index | 记录时间 |
| created_at | DateTime | Default | 创建时间 |

**关系**: User (多对一)

---

### 7. 睡眠记录表 (sleep_records)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | FK, Index | 关联users.id |
| bed_time | DateTime | | 入睡时间 |
| wake_time | DateTime | | 起床时间 |
| total_minutes | Integer | Nullable | 睡眠总时长 (分钟) |
| quality | Integer | Nullable | 睡眠质量 (1-5星) |
| notes | String(500) | Nullable | 备注 |
| created_at | DateTime | Default | 创建时间 |

**关系**: User (多对一)

---

### 8. 目标表 (goals)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | FK, Index | 关联users.id |
| target_weight | Float | | 目标体重 (kg) |
| target_date | Date | | 目标达成日期 |
| weekly_plan | Float | | 每周减重计划 (kg) |
| daily_calorie_target | Integer | Nullable | 每日热量目标 |
| meal_distribution | JSON | Nullable | 三餐热量分配比例 |
| status | Enum | Default=ACTIVE | 目标状态 |
| created_at | DateTime | Default | 创建时间 |

**枚举值 (GoalStatus)**:
- `ACTIVE` - 进行中
- `COMPLETED` - 已完成
- `CANCELLED` - 已取消
- `PAUSED` - 已暂停

**关系**: User (多对一)

---

### 9. Agent配置表 (agent_configs)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | Unique, FK | 关联users.id |
| agent_name | String(50) | Nullable | Agent名称 |
| personality_type | Enum | | 性格类型 |
| personality_prompt | Text | Nullable | 个性化提示词 |
| created_at | DateTime | Default | 创建时间 |
| updated_at | DateTime | Auto | 更新时间 |

**枚举值 (PersonalityType)**:
- `PROFESSIONAL` - 专业型
- `WARM` - 温暖型
- `ENERGETIC` - 活力型

**关系**: User (一对一)

---

### 10. 聊天历史表 (chat_history)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | FK, Index | 关联users.id |
| role | String(20) | | 角色 (user/assistant/system) |
| content | Text | | 消息内容 |
| message_type | String(20) | Default=text | 消息类型 |
| metadata | JSON | Nullable | 附加数据 |
| created_at | DateTime | Default, Index | 创建时间 |

**关系**: User (多对一)

---

### 11. 对话摘要表 (conversation_summaries)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | FK, Index | 关联users.id |
| summary | Text | | 对话摘要内容 |
| keywords | JSON | Nullable | 关键词列表 |
| sentiment | String(20) | Nullable | 情感分析结果 |
| created_at | DateTime | Default | 创建时间 |

**关系**: User (多对一)

---

### 12. 食物项目表 (food_items)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| name | String(100) | Unique | 食物名称 |
| calories_per_100g | Integer | | 每100g热量 |
| category | String(50) | | 分类 |
| unit | String(20) | Default=g | 计量单位 |
| is_system | Boolean | Default=False | 是否系统内置 |
| created_at | DateTime | Default | 创建时间 |

---

### 13. 用户食物表 (user_foods)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | FK, Index | 关联users.id |
| food_id | Integer | FK | 关联food_items.id |
| created_at | DateTime | Default | 创建时间 |

**关系**: User (多对一), FoodItem (多对一)

---

### 14. 食谱表 (recipes)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| title | String(100) | | 食谱标题 |
| description | Text | Nullable | 食谱描述 |
| cuisine | String(50) | Nullable | 菜系 |
| difficulty | String(20) | Nullable | 难度 |
| prep_time | Integer | Nullable | 准备时间 (分钟) |
| cook_time | Integer | Nullable | 烹饪时间 (分钟) |
| servings | Integer | Default=1 | 份数 |
| calories_per_serving | Integer | Nullable | 每份热量 |
| image_url | String(500) | Nullable | 图片URL |
| is_system | Boolean | Default=False | 是否系统内置 |
| created_at | DateTime | Default | 创建时间 |
| updated_at | DateTime | Auto | 更新时间 |

---

### 15. 食谱食材表 (recipe_ingredients)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| recipe_id | Integer | FK, Index | 关联recipes.id |
| food_name | String(100) | | 食材名称 |
| amount | Float | | 用量 |
| unit | String(20) | | 单位 |
| calories | Integer | Nullable | 热量 |

**关系**: Recipe (多对一)

---

### 16. 食谱步骤表 (recipe_steps)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| recipe_id | Integer | FK, Index | 关联recipes.id |
| step_number | Integer | | 步骤序号 |
| description | Text | | 步骤描述 |
| image_url | String(500) | Nullable | 步骤图片 |
| duration_minutes | Integer | Nullable | 步骤耗时 |

**关系**: Recipe (多对一)

---

### 17. 用户食谱表 (user_recipes)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | FK, Index | 关联users.id |
| recipe_id | Integer | FK, Index | 关联recipes.id |
| is_favorite | Boolean | Default=False | 是否收藏 |
| last_cooked | DateTime | Nullable | 最后烹饪时间 |
| cooked_count | Integer | Default=0 | 烹饪次数 |
| rating | Integer | Nullable | 评分 (1-5星) |
| notes | Text | Nullable | 备注 |
| created_at | DateTime | Default | 创建时间 |
| updated_at | DateTime | Auto | 更新时间 |

**关系**: User (多对一), Recipe (多对一)

---

### 18. 周报表 (weekly_reports)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | FK, Index | 关联users.id |
| week_start | Date | Index | 周开始日期 |
| summary_text | Text | Nullable | 周报摘要 |
| weight_change | Float | Nullable | 体重变化 |
| avg_weight | Float | Nullable | 平均体重 |
| avg_calories_in | Float | Nullable | 平均摄入热量 |
| avg_calories_out | Float | Nullable | 平均消耗热量 |
| exercise_days | Integer | Nullable | 运动天数 |
| highlights | JSON | Nullable | 亮点 |
| improvements | JSON | Nullable | 改进点 |
| created_at | DateTime | Default | 创建时间 |

**关系**: User (多对一)

---

### 19. 提醒设置表 (reminder_settings)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | FK, Index | 关联users.id |
| reminder_type | String(20) | | 提醒类型 |
| enabled | Boolean | Default=True | 是否启用 |
| time | String(10) | Nullable | 提醒时间 (HH:MM) |
| days_of_week | JSON | Nullable | 周几提醒 |
| interval_minutes | Integer | Nullable | 间隔分钟数 |
| created_at | DateTime | Default | 创建时间 |
| updated_at | DateTime | Auto | 更新时间 |

**关系**: User (多对一)

---

### 20. 通知队列表 (notification_queue)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | FK, Index | 关联users.id |
| notification_type | String(20) | | 通知类型 |
| title | String(100) | | 标题 |
| content | Text | | 内容 |
| channel | String(20) | Default=in_app | 通知渠道 |
| status | Enum | Default=pending | 状态 |
| scheduled_at | DateTime | Nullable | 计划发送时间 |
| sent_at | DateTime | Nullable | 实际发送时间 |
| created_at | DateTime | Default | 创建时间 |

**枚举值 (NotificationStatus)**:
- `PENDING` - 待发送
- `SENT` - 已发送
- `FAILED` - 发送失败
- `CANCELLED` - 已取消

**关系**: User (多对一)

---

### 21. 用户画像答案表 (profiling_answers)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | FK, Index | 关联users.id |
| question_id | String(50) | | 问题ID |
| question_category | String(20) | | 问题类别 |
| answer | Text | | 答案 |
| created_at | DateTime | Default | 创建时间 |

**关系**: User (多对一)

---

### 22. 用户画像缓存表 (user_profile_cache)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| user_id | Integer | Unique, FK | 关联users.id |
| cached_data | JSON | | 缓存的画像数据 |
| data_version | Integer | Default=1 | 数据版本 |
| created_at | DateTime | Default | 创建时间 |
| updated_at | DateTime | Auto | 更新时间 |

**关系**: User (一对一)

---

### 23. 系统提示词表 (system_prompts)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| name | String(100) | Unique | 提示词名称 |
| prompt_type | String(20) | | 提示词类型 |
| content | Text | | 提示词内容 |
| description | String(500) | Nullable | 描述 |
| is_active | Boolean | Default=True | 是否激活 |
| created_at | DateTime | Default | 创建时间 |
| updated_at | DateTime | Auto | 更新时间 |

---

### 24. 提示词版本表 (prompt_versions)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| prompt_id | Integer | FK, Index | 关联system_prompts.id |
| version | Integer | | 版本号 |
| content | Text | | 版本内容 |
| changelog | Text | Nullable | 变更说明 |
| created_at | DateTime | Default | 创建时间 |

**关系**: SystemPrompt (多对一)

---

### 25. 系统配置表 (system_config)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| config_key | String(100) | Unique | 配置键 |
| config_value | JSON | | 配置值 |
| config_type | String(20) | Default=string | 配置类型 |
| description | String(500) | Nullable | 描述 |
| is_public | Boolean | Default=False | 是否公开 |
| created_at | DateTime | Default | 创建时间 |
| updated_at | DateTime | Auto | 更新时间 |

---

### 26. 系统备份表 (system_backups)
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | PK | 主键，自增 |
| backup_type | String(20) | | 备份类型 |
| file_path | String(500) | | 文件路径 |
| file_size | Integer | Nullable | 文件大小 |
| status | Enum | Default=pending | 状态 |
| notes | Text | Nullable | 备注 |
| created_at | DateTime | Default | 创建时间 |

---

## 枚举类型汇总

### MotivationType (动力类型)
- `DATA_DRIVEN` - 数据驱动：关注数字和进度
- `EMOTIONAL_SUPPORT` - 情感支持：需要鼓励和陪伴
- `GOAL_ORIENTED` - 目标导向：关注目标和成就

### PersonalityType (Agent性格)
- `PROFESSIONAL` - 专业型：专业严谨，数据导向
- `WARM` - 温暖型：温情关怀，情感丰富
- `ENERGETIC` - 活力型：积极鼓励，充满动力

### GoalStatus (目标状态)
- `ACTIVE` - 进行中
- `COMPLETED` - 已完成
- `CANCELLED` - 已取消
- `PAUSED` - 已暂停

### MealType (餐食类型)
- `BREAKFAST` - 早餐
- `LUNCH` - 午餐
- `DINNER` - 晚餐
- `SNACK` - 加餐

### ExerciseIntensity (运动强度)
- `LOW` - 低强度
- `MEDIUM` - 中强度
- `HIGH` - 高强度

### NotificationStatus (通知状态)
- `PENDING` - 待发送
- `SENT` - 已发送
- `FAILED` - 发送失败
- `CANCELLED` - 已取消
