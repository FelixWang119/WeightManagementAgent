"""
数据库模型定义
使用 SQLAlchemy 2.0 异步 ORM
"""

from datetime import datetime
from typing import Optional, List, AsyncGenerator
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Date,
    Time,
    Text,
    JSON,
    ForeignKey,
    Enum,
    create_engine,
    Index,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


# ============ 枚举类型定义 ============


class MealType(str, enum.Enum):
    """餐食类型"""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class ExerciseIntensity(str, enum.Enum):
    """运动强度"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PersonalityType(str, enum.Enum):
    """Agent性格类型"""

    PROFESSIONAL = "professional"
    WARM = "warm"
    ENERGETIC = "energetic"


class MotivationType(str, enum.Enum):
    """用户动力类型"""

    DATA_DRIVEN = "data_driven"
    EMOTIONAL_SUPPORT = "emotional_support"
    GOAL_ORIENTED = "goal_oriented"


class GoalStatus(str, enum.Enum):
    """目标状态"""

    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class MessageRole(str, enum.Enum):
    """消息角色"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageType(str, enum.Enum):
    """消息类型"""

    TEXT = "text"
    CARD = "card"
    IMAGE = "image"
    FORM = "form"
    QUICK_ACTIONS = "quick_actions"


class ReminderType(str, enum.Enum):
    """提醒类型"""

    WEIGHT = "weight"
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    EXERCISE = "exercise"
    WATER = "water"
    SLEEP = "sleep"
    WEEKLY = "weekly"


class FoodCategory(str, enum.Enum):
    """食物分类"""

    STAPLE = "staple"
    MEAT = "meat"
    VEGETABLE = "vegetable"
    FRUIT = "fruit"
    SNACK = "snack"
    DRINK = "drink"


class AchievementConditionType(str, enum.Enum):
    """成就条件类型"""

    FIRST_RECORD = "first_record"
    STREAK_DAYS = "streak_days"
    WEIGHT_LOSS = "weight_loss"
    CALORIE_CONTROL = "calorie_control"
    EXERCISE_COUNT = "exercise_count"


class ChallengeType(str, enum.Enum):
    """挑战类型"""

    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"


class ChallengeStatus(str, enum.Enum):
    """挑战状态"""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class ConsultationStatus(str, enum.Enum):
    """咨询状态"""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


# ============ 数据库模型 ============


class User(Base):
    """用户表"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    openid = Column(String(100), unique=True, index=True, comment="微信用户唯一标识")
    nickname = Column(String(100), comment="用户昵称")
    avatar_url = Column(String(500), comment="头像URL")
    phone = Column(String(20), nullable=True, comment="手机号")
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_vip = Column(Boolean, default=False, comment="是否VIP会员")
    vip_expire = Column(Date, nullable=True, comment="VIP过期时间")
    is_admin = Column(Boolean, default=False, comment="是否管理员")
    admin_role = Column(
        String(20), nullable=True, comment="管理员角色: super/admin/viewer"
    )
    admin_permissions = Column(JSON, nullable=True, comment="管理员权限配置(JSON)")
    last_admin_login = Column(DateTime, nullable=True, comment="最后管理员登录时间")

    # 类型安全的属性（解决LSP类型检查问题）
    @property
    def user_id(self) -> int:
        """返回用户ID（int类型）"""
        return self.id

    # 关系
    weight_records = relationship("WeightRecord", back_populates="user")
    meal_records = relationship("MealRecord", back_populates="user")
    exercise_records = relationship("ExerciseRecord", back_populates="user")
    water_records = relationship("WaterRecord", back_populates="user")
    sleep_records = relationship("SleepRecord", back_populates="user")
    goals = relationship("Goal", back_populates="user")
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    agent_config = relationship("AgentConfig", back_populates="user", uselist=False)
    profile_cache = relationship(
        "UserProfileCache", back_populates="user", uselist=False
    )
    chat_history = relationship("ChatHistory", back_populates="user")


class WeightRecord(Base):
    """体重记录表"""

    __tablename__ = "weight_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    weight = Column(Float, comment="体重（kg）")
    body_fat = Column(Float, nullable=True, comment="体脂率（%）")
    record_date = Column(Date, comment="记录日期")
    record_time = Column(DateTime, comment="记录时间")
    note = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="weight_records")

    __table_args__ = (Index("idx_weight_record_user_time", "user_id", "record_time"),)


class MealRecord(Base):
    """餐食记录表"""

    __tablename__ = "meal_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    meal_type = Column(Enum(MealType), comment="餐食类型（早餐/午餐/晚餐/加餐）")
    record_time = Column(DateTime, comment="记录时间")
    photo_url = Column(String(500), nullable=True, comment="餐食照片URL")
    food_items = Column(JSON, comment="食物明细（JSON格式）")
    total_calories = Column(Integer, comment="总热量（千卡）")
    user_confirmed = Column(Boolean, default=False, comment="用户是否确认识别结果")
    ai_confidence = Column(Float, nullable=True, comment="AI识别置信度（0-1）")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="meal_records")


class ExerciseRecord(Base):
    """运动记录表"""

    __tablename__ = "exercise_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    exercise_type = Column(String(50), comment="运动类型")
    duration_minutes = Column(Integer, comment="运动时长（分钟）")
    calories_burned = Column(Integer, comment="消耗热量（千卡）")
    intensity = Column(Enum(ExerciseIntensity), comment="运动强度（低/中/高）")
    record_time = Column(DateTime, comment="记录时间")
    photo_evidence = Column(String(500), nullable=True, comment="运动凭证照片")
    is_checkin = Column(
        Boolean, default=False, comment="是否为打卡记录（区别于详细运动记录）"
    )
    checkin_date = Column(Date, nullable=True, comment="打卡日期（用于快速打卡）")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="exercise_records")


class WaterRecord(Base):
    """饮水记录表"""

    __tablename__ = "water_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    amount_ml = Column(Integer, comment="饮水量（毫升）")
    record_time = Column(DateTime, comment="记录时间")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="water_records")


class SleepRecord(Base):
    """睡眠记录表"""

    __tablename__ = "sleep_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    bed_time = Column(DateTime, comment="入睡时间")
    wake_time = Column(DateTime, comment="起床时间")
    total_minutes = Column(Integer, comment="睡眠总时长（分钟）")
    quality = Column(Integer, nullable=True, comment="睡眠质量评分（1-5星）")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sleep_records")


class UserProfile(Base):
    """用户画像表（长期记忆）"""

    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    age = Column(Integer, nullable=True, comment="年龄")
    gender = Column(String(10), nullable=True, comment="性别")
    height = Column(Float, nullable=True, comment="身高（cm）")
    bmr = Column(Integer, nullable=True, comment="基础代谢率（BMR）")
    diet_preferences = Column(JSON, nullable=True, comment="饮食偏好（JSON）")
    exercise_habits = Column(JSON, nullable=True, comment="运动习惯（JSON）")
    weight_history = Column(Text, nullable=True, comment="减重历史记录")
    body_signals = Column(JSON, nullable=True, comment="身体信号（JSON：疲劳/失眠等）")
    motivation_type = Column(
        Enum(MotivationType),
        nullable=True,
        comment="动力类型（数据驱动/情感支持/目标导向）",
    )
    weak_points = Column(JSON, nullable=True, comment="薄弱环节（JSON）")
    memory_summary = Column(Text, nullable=True, comment="AI记忆摘要（自然语言描述）")
    decision_mode = Column(
        String(20),
        default="balanced",
        comment="决策模式: conservative/balanced/intelligent",
    )
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profile")


class Goal(Base):
    """目标表"""

    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    target_weight = Column(Float, comment="目标体重（kg）")
    target_date = Column(Date, comment="目标达成日期")
    weekly_plan = Column(Float, comment="每周减重计划（kg）")
    daily_calorie_target = Column(Integer, comment="每日热量目标（千卡）")
    meal_distribution = Column(JSON, comment="三餐热量分配比例（JSON）")
    status = Column(Enum(GoalStatus), default=GoalStatus.ACTIVE, comment="目标状态")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="goals")


class AgentConfig(Base):
    """Agent配置表"""

    __tablename__ = "agent_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    agent_name = Column(String(50), default="小助", comment="Agent名称")
    personality_type = Column(
        Enum(PersonalityType), comment="性格类型（专业/温暖/活力）"
    )
    personality_prompt = Column(Text, comment="性格Prompt描述")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="agent_config")


class ChatHistory(Base):
    """对话历史表"""

    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    role = Column(Enum(MessageRole), comment="消息角色（user/assistant/system）")
    content = Column(Text, comment="消息内容")
    msg_type = Column(Enum(MessageType), default=MessageType.TEXT, comment="消息类型")
    meta_data = Column(JSON, nullable=True, comment="元数据（JSON）")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="chat_history")


class ConversationSummary(Base):
    """对话摘要表"""

    __tablename__ = "conversation_summaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    week_start = Column(Date, comment="周开始日期")
    summary_text = Column(Text, comment="对话摘要文本")
    key_facts = Column(JSON, comment="关键事实（JSON）")
    created_at = Column(DateTime, default=datetime.utcnow)


class FoodItem(Base):
    """食物数据库表"""

    __tablename__ = "food_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), comment="食物名称")
    aliases = Column(JSON, nullable=True, comment="别名列表（JSON）")
    category = Column(Enum(FoodCategory), comment="食物分类")
    calories_per_100g = Column(Float, comment="每100克热量（千卡）")
    protein = Column(Float, nullable=True, comment="蛋白质（g/100g）")
    fat = Column(Float, nullable=True, comment="脂肪含量（g/100g）")
    carbs = Column(Float, nullable=True, comment="碳水化合物（g/100g）")
    common_portions = Column(JSON, nullable=True, comment="常见分量（JSON）")
    is_user_created = Column(Boolean, default=False, comment="是否用户自定义")


class UserFood(Base):
    """用户自定义食物表"""

    __tablename__ = "user_foods"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    food_name = Column(String(100), comment="食物名称")
    calories = Column(Integer, comment="热量（千卡）")
    created_at = Column(DateTime, default=datetime.utcnow)


class WeeklyReport(Base):
    """每周报告表"""

    __tablename__ = "weekly_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    week_start = Column(Date, comment="周开始日期")
    summary_text = Column(Text, comment="AI生成的周报总结")
    weight_change = Column(Float, comment="体重变化（kg）")
    avg_weight = Column(Float, comment="平均体重（kg）")
    avg_calories_in = Column(Integer, comment="平均摄入热量（千卡/天）")
    avg_calories_out = Column(Integer, comment="平均消耗热量（千卡/天）")
    exercise_days = Column(Integer, comment="运动天数")
    highlights = Column(JSON, comment="本周亮点（JSON）")
    improvements = Column(JSON, comment="改进建议（JSON）")
    created_at = Column(DateTime, default=datetime.utcnow)


class ReminderSetting(Base):
    """提醒设置表"""

    __tablename__ = "reminder_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    reminder_type = Column(Enum(ReminderType), comment="提醒类型")
    enabled = Column(Boolean, default=True, comment="是否启用")
    reminder_time = Column(Time, nullable=True, comment="提醒时间")
    interval_minutes = Column(Integer, nullable=True, comment="间隔分钟数（饮水用）")
    weekdays_only = Column(Boolean, default=False, comment="仅工作日提醒")
    last_triggered = Column(DateTime, nullable=True, comment="上次触发时间")
    skip_count = Column(Integer, default=0, comment="连续忽略次数")


class NotificationQueue(Base):
    """通知队列表"""

    __tablename__ = "notification_queue"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    reminder_type = Column(String(20), nullable=False)
    message = Column(Text, nullable=True)
    scheduled_at = Column(DateTime, nullable=False, default=datetime.now)
    sent_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(Text, nullable=True)
    channel = Column(String(20), default="chat")
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    def __repr__(self):
        return f"<NotificationQueue {self.id} user={self.user_id} type={self.reminder_type} status={self.status}>"


class ProfilingAnswer(Base):
    """用户画像问题回答表"""

    __tablename__ = "profiling_answers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    question_id = Column(String(50), comment="问题ID")
    question_category = Column(String(20), comment="问题分类")
    answer_value = Column(String(100), comment="回答值")
    answer_text = Column(String(200), comment="回答文本")
    question_tags = Column(JSON, nullable=True, comment="问题标签（JSON）")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_profiling_answer_user_created", "user_id", "created_at"),
    )


class UserProfileCache(Base):
    """用户画像缓存表（带持久化能力）"""

    __tablename__ = "user_profile_cache"

    user_id = Column(
        Integer, ForeignKey("users.id"), primary_key=True, comment="用户ID"
    )
    cached_data = Column(JSON, nullable=False, comment="结构化画像数据（JSON格式）")
    data_version = Column(
        DateTime, nullable=False, comment="数据版本时间戳（依赖表的最大更新时间）"
    )
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    user = relationship("User", back_populates="profile_cache")


# ============ 系统提示词管理 ============


class PromptCategory(str, enum.Enum):
    """提示词分类"""

    SYSTEM = "system"  # 系统级提示词
    TASK = "task"  # 任务特定提示词
    TEMPLATE = "template"  # 模板提示词
    CUSTOM = "custom"  # 自定义提示词
    PERSONALITY = "personality"  # 助手性格风格提示词


class PromptStatus(str, enum.Enum):
    """提示词状态"""

    DRAFT = "draft"  # 草稿
    ACTIVE = "active"  # 活跃/启用
    INACTIVE = "inactive"  # 停用
    ARCHIVED = "archived"  # 归档


class SystemPrompt(Base):
    """系统提示词表"""

    __tablename__ = "system_prompts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="提示词名称")
    description = Column(Text, nullable=True, comment="描述")
    content = Column(Text, nullable=False, comment="提示词内容")
    category = Column(
        Enum(PromptCategory), default=PromptCategory.SYSTEM, comment="分类"
    )
    status = Column(Enum(PromptStatus), default=PromptStatus.DRAFT, comment="状态")
    version = Column(Integer, default=1, comment="版本号")
    is_current = Column(Boolean, default=True, comment="是否当前版本")
    tags = Column(JSON, nullable=True, comment="标签列表（JSON数组）")
    meta_data = Column(JSON, nullable=True, comment="元数据（JSON格式）")
    created_by = Column(
        Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID"
    )
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )
    last_used_at = Column(DateTime, nullable=True, comment="最后使用时间")
    usage_count = Column(Integer, default=0, comment="使用次数")

    # 关系
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_prompt_category_status", "category", "status"),
        Index("idx_prompt_name_version", "name", "version"),
    )


class PromptVersion(Base):
    """提示词版本历史表"""

    __tablename__ = "prompt_versions"

    id = Column(Integer, primary_key=True, index=True)
    prompt_id = Column(
        Integer, ForeignKey("system_prompts.id"), nullable=False, comment="提示词ID"
    )
    version = Column(Integer, nullable=False, comment="版本号")
    content = Column(Text, nullable=False, comment="提示词内容")
    change_log = Column(Text, nullable=True, comment="变更说明")
    created_by = Column(
        Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID"
    )
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 关系
    prompt = relationship("SystemPrompt", foreign_keys=[prompt_id])
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (Index("idx_prompt_version", "prompt_id", "version", unique=True),)


# ============ 系统配置和备份管理 ============


class SystemConfig(Base):
    """系统配置表"""

    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True, comment="配置键")
    value = Column(JSON, nullable=True, comment="配置值（JSON格式）")
    description = Column(Text, nullable=True, comment="配置说明")
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )
    updated_by = Column(String(100), nullable=True, comment="更新者")

    __table_args__ = (Index("idx_config_key", "key"),)


class SystemBackup(Base):
    """系统备份表"""

    __tablename__ = "system_backups"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False, comment="备份文件名")
    size_mb = Column(Float, nullable=False, comment="备份文件大小(MB)")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    created_by = Column(String(100), nullable=True, comment="创建者")
    backup_type = Column(String(50), default="manual", comment="备份类型: manual, auto")
    status = Column(
        String(50), default="completed", comment="状态: pending, completed, failed"
    )
    file_path = Column(String(500), nullable=True, comment="备份文件完整路径")

    __table_args__ = (
        Index("idx_backup_created", "created_at"),
        Index("idx_backup_type", "backup_type"),
    )


# ============ 数据库连接 ============

# 从配置文件获取数据库URL
from config.settings import fastapi_settings

# 创建异步引擎（带连接池配置）
engine = create_async_engine(
    fastapi_settings.DATABASE_URL,
    echo=fastapi_settings.DEBUG,  # 调试模式下打印SQL
    future=True,
    pool_size=10,  # 连接池大小
    max_overflow=20,  # 最大溢出连接数
    pool_pre_ping=True,  # 连接前先ping检测有效性
    pool_recycle=3600,  # 连接回收时间（1小时）
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（用于 FastAPI Depends）"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库（创建所有表）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 数据库初始化完成")
