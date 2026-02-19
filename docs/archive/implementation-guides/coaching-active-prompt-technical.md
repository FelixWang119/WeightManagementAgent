# 教练主动提示与引导 - 技术实现方案

**文档版本**: 1.0  
**创建日期**: 2026-02-17  
**状态**: 技术设计文档  
**关联文档**: [PRD v1.5](PRD.md), [行为教练技术架构](behavior-coach-architecture.md)

## 一、概述

### 1.1 问题定义
教练系统需要能够**主动**发起对话和提示，而不是被动等待用户输入。这需要：
1. **时机检测**: 识别何时需要教练介入
2. **内容生成**: 生成恰当的教练提示内容
3. **渠道选择**: 选择合适的通知渠道
4. **用户响应处理**: 处理用户的响应和后续对话

### 1.2 技术挑战
1. **时机判断准确性**: 避免过度打扰用户
2. **个性化程度**: 提示内容需要高度个性化
3. **实时性要求**: 需要在合适的时间及时触发
4. **状态管理**: 跟踪主动提示的状态和用户响应

## 二、系统架构

### 2.1 整体架构图
```
┌─────────────────────────────────────────────────────────┐
│                   教练主动提示系统                         │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  时机检测器   │  │  提示生成器   │  │  渠道分发器   │    │
│  │ - 规则检测   │  │ - AI生成     │  │ - 推送通知   │    │
│  │ - AI检测     │  │ - 模板匹配   │  │ - 聊天消息   │    │
│  │ - 事件检测   │  │ - 个性化调整 │  │ - 邮件通知   │    │
│  └─────────────┘  └─────────────┘  └─────────────┘    │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  状态管理器   │  │  响应处理器   │  │  效果评估器   │    │
│  │ - 提示状态   │  │ - 用户响应   │  │ - 效果跟踪   │    │
│  │ - 会话管理   │  │ - 后续对话   │  │ - 优化反馈   │    │
│  │ - 频率控制   │  │ - 行动触发   │  │ - A/B测试    │    │
│  └─────────────┘  └─────────────┘  └─────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### 2.2 与现有系统集成
```
现有通知系统 → 扩展为教练提示系统
├── NotificationScheduler → CoachingPromptScheduler (扩展)
├── IntelligentDecisionEngine → CoachingPromptDecisionEngine (扩展)
├── NotificationQueue → CoachingPromptQueue (新增)
└── 新增: CoachingPromptGenerator, CoachingResponseHandler
```

## 三、核心组件设计

### 3.1 时机检测器 (TimingDetector)

#### **3.1.1 检测规则类型**
```python
class PromptTimingType(Enum):
    """提示时机类型"""
    # 基于时间的提示
    DAILY_CHECKIN = "daily_checkin"           # 每日检查
    WEEKLY_REVIEW = "weekly_review"           # 每周回顾
    MILESTONE_REACHED = "milestone_reached"   # 里程碑达成
    
    # 基于行为的提示  
    HABIT_MISSED = "habit_missed"             # 习惯未完成
    PATTERN_CHANGE = "pattern_change"         # 行为模式变化
    PROGRESS_STALLED = "progress_stalled"     # 进展停滞
    
    # 基于情境的提示
    CONTEXT_CHANGE = "context_change"         # 情境变化（旅行、生病等）
    EMOTIONAL_STATE = "emotional_state"       # 情绪状态检测
    OPPORTUNITY_DETECTED = "opportunity_detected"  # 机会识别
    
    # 基于关系的提示
    RELATIONSHIP_MAINTENANCE = "relationship_maintenance"  # 关系维护
    SILENT_PERIOD = "silent_period"           # 沉默期检测
```

#### **3.1.2 检测算法实现**
```python
class CoachingTimingDetector:
    """教练时机检测器"""
    
    def __init__(self):
        self.rule_detectors = self._initialize_rule_detectors()
        self.ai_detector = AITimingDetector()
        self.event_detector = ContextEventDetector()
    
    async def detect_prompt_timing(self, user_id: int) -> List[PromptTiming]:
        """检测需要教练提示的时机"""
        timings = []
        
        # 1. 规则检测（快速、确定性的检测）
        rule_based = await self._detect_rule_based_timings(user_id)
        timings.extend(rule_based)
        
        # 2. AI检测（复杂、需要推理的检测）
        ai_based = await self.ai_detector.detect_timings(user_id)
        timings.extend(ai_based)
        
        # 3. 事件检测（外部事件触发）
        event_based = await self.event_detector.detect_timings(user_id)
        timings.extend(event_based)
        
        # 4. 频率控制和优先级排序
        filtered_timings = await self._apply_frequency_control(user_id, timings)
        sorted_timings = self._prioritize_timings(filtered_timings)
        
        return sorted_timings[:3]  # 返回前3个最高优先级的时机
    
    async def _detect_rule_based_timings(self, user_id: int) -> List[PromptTiming]:
        """基于规则的时机检测"""
        timings = []
        
        # 每日检查（如果用户今天还没和教练对话）
        if await self._should_do_daily_checkin(user_id):
            timings.append(PromptTiming(
                type=PromptTimingType.DAILY_CHECKIN,
                priority=Priority.HIGH,
                confidence=0.9,
                metadata={"last_conversation": last_convo_time}
            ))
        
        # 习惯未完成检测
        missed_habits = await self._detect_missed_habits(user_id)
        for habit in missed_habits:
            if habit["missed_days"] >= 2:  # 连续2天未完成
                timings.append(PromptTiming(
                    type=PromptTimingType.HABIT_MISSED,
                    priority=Priority.MEDIUM,
                    confidence=0.8,
                    metadata={
                        "habit_id": habit["id"],
                        "habit_name": habit["name"],
                        "missed_days": habit["missed_days"],
                        "streak_before": habit["streak_before"]
                    }
                ))
        
        # 进展停滞检测（连续3天无进展）
        if await self._detect_progress_stall(user_id, days=3):
            timings.append(PromptTiming(
                type=PromptTimingType.PROGRESS_STALLED,
                priority=Priority.MEDIUM,
                confidence=0.7,
                metadata={"stall_days": 3, "last_progress": last_progress_date}
            ))
        
        return timings
    
    async def _should_do_daily_checkin(self, user_id: int) -> bool:
        """判断是否需要每日检查"""
        # 获取用户最后对话时间
        last_convo = await self._get_last_conversation_time(user_id)
        if not last_convo:
            return True  # 从未对话过
        
        # 检查是否今天已经对话过
        today = datetime.now().date()
        last_convo_date = last_convo.date()
        
        # 如果今天还没对话，且用户通常在此时段活跃
        if last_convo_date < today:
            user_activity = await self._get_user_activity_pattern(user_id)
            current_hour = datetime.now().hour
            
            # 检查当前是否在用户活跃时段
            if self._is_active_time(current_hour, user_activity):
                return True
        
        return False
```

### 3.2 提示生成器 (PromptGenerator)

#### **3.2.1 提示内容结构**
```python
@dataclass
class CoachingPrompt:
    """教练提示数据结构"""
    id: str
    user_id: int
    timing_type: PromptTimingType
    priority: Priority
    content: PromptContent
    delivery_config: DeliveryConfig
    state: PromptState = PromptState.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_for: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PromptContent:
    """提示内容"""
    # 文本内容
    title: str
    message: str
    quick_replies: List[QuickReply]  # 快速回复选项
    
    # 富媒体内容
    media_type: MediaType = MediaType.TEXT
    media_url: Optional[str] = None
    card_data: Optional[Dict[str, Any]] = None
    
    # 交互元素
    actions: List[Action] = field(default_factory=list)
    follow_up_plan: Optional[FollowUpPlan] = None

@dataclass  
class QuickReply:
    """快速回复选项"""
    text: str
    value: str
    action_type: ActionType
    next_step: Optional[str] = None  # 选择后的下一步

@dataclass
class DeliveryConfig:
    """发送配置"""
    channel: DeliveryChannel  # 推送/聊天/邮件
    timing: DeliveryTiming   # 立即/定时/智能
    retry_policy: RetryPolicy
    expiration: Optional[datetime] = None  # 过期时间
```

#### **3.2.2 生成算法实现**
```python
class CoachingPromptGenerator:
    """教练提示生成器"""
    
    def __init__(self):
        self.template_engine = PromptTemplateEngine()
        self.ai_generator = AIPromptGenerator()
        self.personalizer = PromptPersonalizer()
    
    async def generate_prompt(self, timing: PromptTiming, user_context: Dict) -> CoachingPrompt:
        """生成教练提示"""
        
        # 1. 选择生成策略
        strategy = self._select_generation_strategy(timing, user_context)
        
        # 2. 生成基础内容
        if strategy == GenerationStrategy.TEMPLATE:
            content = await self.template_engine.generate(timing, user_context)
        elif strategy == GenerationStrategy.AI:
            content = await self.ai_generator.generate(timing, user_context)
        else:  # HYBRID
            template_content = await self.template_engine.generate(timing, user_context)
            ai_enhanced = await self.ai_generator.enhance(template_content, user_context)
            content = ai_enhanced
        
        # 3. 个性化调整
        personalized = await self.personalizer.personalize(content, user_context)
        
        # 4. 添加交互元素
        with_interactions = self._add_interactions(personalized, timing)
        
        # 5. 构建完整提示
        prompt = CoachingPrompt(
            id=self._generate_prompt_id(),
            user_id=user_context["user_id"],
            timing_type=timing.type,
            priority=timing.priority,
            content=with_interactions,
            delivery_config=self._create_delivery_config(timing, user_context),
            metadata={
                "generation_strategy": strategy.value,
                "confidence": timing.confidence,
                **timing.metadata
            }
        )
        
        return prompt
    
    def _add_interactions(self, content: PromptContent, timing: PromptTiming) -> PromptContent:
        """添加交互元素"""
        
        # 根据时机类型添加不同的快速回复
        quick_replies = []
        
        if timing.type == PromptTimingType.HABIT_MISSED:
            habit_name = timing.metadata.get("habit_name", "这个习惯")
            
            quick_replies = [
                QuickReply(
                    text=f"现在完成{habit_name}",
                    value="complete_now",
                    action_type=ActionType.COMPLETE_HABIT,
                    next_step="habit_completion"
                ),
                QuickReply(
                    text="今天跳过，明天再继续",
                    value="skip_today",
                    action_type=ActionType.REPORT_INTERRUPTION,
                    next_step="interruption_report"
                ),
                QuickReply(
                    text="需要调整这个习惯",
                    value="adjust_habit",
                    action_type=ActionType.ADJUST_HABIT,
                    next_step="habit_adjustment"
                ),
                QuickReply(
                    text="和我聊聊为什么难坚持",
                    value="talk_about_challenge",
                    action_type=ActionType.START_CONVERSATION,
                    next_step="challenge_conversation"
                )
            ]
        
        elif timing.type == PromptTimingType.DAILY_CHECKIN:
            quick_replies = [
                QuickReply(
                    text="分享今日计划",
                    value="share_plan",
                    action_type=ActionType.SHARE_PLAN,
                    next_step="plan_sharing"
                ),
                QuickReply(
                    text="回顾昨日进展",
                    value="review_yesterday",
                    action_type=ActionType.REVIEW_PROGRESS,
                    next_step="progress_review"
                ),
                QuickReply(
                    text="需要一些鼓励",
                    value="need_encouragement",
                    action_type=ActionType.PROVIDE_ENCOURAGEMENT,
                    next_step="encouragement"
                ),
                QuickReply(
                    text="今天晚点再聊",
                    value="later",
                    action_type=ActionType.DEFER,
                    next_step="deferred"
                )
            ]
        
        # 更新内容中的快速回复
        content.quick_replies = quick_replies
        
        return content
```

### 3.3 渠道分发器 (ChannelDispatcher)

#### **3.3.1 分发策略**
```python
class DeliveryChannel(Enum):
    """发送渠道"""
    IN_APP_CHAT = "in_app_chat"      # 应用内聊天（最高优先级）
    PUSH_NOTIFICATION = "push"       # 推送通知（中等优先级）
    EMAIL = "email"                  # 邮件（低优先级，用于摘要）
    SMS = "sms"                      # 短信（紧急情况）
    
class DeliveryTiming(Enum):
    """发送时机"""
    IMMEDIATE = "immediate"          # 立即发送
    SCHEDULED = "scheduled"          # 定时发送
    INTELLIGENT = "intelligent"      # 智能选择时机
    USER_PREFERRED = "user_preferred"  # 用户偏好时间
```

#### **3.3.2 分发实现**
```python
class CoachingChannelDispatcher:
    """教练渠道分发器"""
    
    def __init__(self):
        self.channels = {
            DeliveryChannel.IN_APP_CHAT: InAppChatChannel(),
            DeliveryChannel.PUSH_NOTIFICATION: PushNotificationChannel(),
            DeliveryChannel.EMAIL: EmailChannel(),
            DeliveryChannel.SMS: SmsChannel()
        }
        self.user_preference_service = UserPreferenceService()
    
    async def dispatch_prompt(self, prompt: CoachingPrompt) -> bool:
        """分发教练提示"""
        
        # 1. 选择渠道（基于优先级和用户偏好）
        channel = await self._select_channel(prompt)
        
        # 2. 选择时机
        delivery_time = await self._select_delivery_time(prompt, channel)
        
        # 3. 准备发送
        prepared_prompt = await self._prepare_for_channel(prompt, channel)
        
        # 4. 发送（立即或定时）
        if delivery_time <= datetime.now():
            success = await self._send_immediately(prepared_prompt, channel)
        else:
            success = await self._schedule_delivery(prepared_prompt, channel, delivery_time)
        
        # 5. 更新状态
        if success:
            await self._update_prompt_state(prompt.id, PromptState.DELIVERED)
            logger.info(f"提示 {prompt.id} 已通过 {channel.value} 发送")
        else:
            await self._handle_delivery_failure(prompt, channel)
        
        return success
    
    async def _select_channel(self, prompt: CoachingPrompt) -> DeliveryChannel:
        """选择发送渠道"""
        
        # 获取用户偏好
        user_prefs = await self.user_preference_service.get_notification_preferences(
            prompt.user_id
        )
        
        # 基于优先级选择渠道
        if prompt.priority == Priority.HIGH:
            # 高优先级：应用内聊天 + 推送通知
            if user_prefs.get("allow_in_app_chat", True):
                return DeliveryChannel.IN_APP_CHAT
            elif user_prefs.get("allow_push", True):
                return DeliveryChannel.PUSH_NOTIFICATION
            else:
                return DeliveryChannel.EMAIL
        
        elif prompt.priority == Priority.MEDIUM:
            # 中优先级：推送通知
            if user_prefs.get("allow_push", True):
                return DeliveryChannel.PUSH_NOTIFICATION
            else:
                return DeliveryChannel.IN_APP_CHAT
        
        else:  # LOW
            # 低优先级：邮件或应用内消息
            if user_prefs.get("allow_email", True):
                return DeliveryChannel.EMAIL
            else:
                return DeliveryChannel.IN_APP_CHAT
    
    async def _select_delivery_time(self, prompt: CoachingPrompt, channel: DeliveryChannel) -> datetime:
        """选择发送时机"""
        
        config = prompt.delivery_config
        
        if config.timing == DeliveryTiming.IMMEDIATE:
            return datetime.now()
        
        elif config.timing == DeliveryTiming.SCHEDULED:
            return config.scheduled_for or datetime.now()
        
        elif config.timing == DeliveryTiming.INTELLIGENT:
            # 智能选择用户最可能响应的时机
            return await self._predict_best_time(prompt.user_id, channel)
        
        elif config.timing == DeliveryTiming.USER_PREFERRED:
            # 用户偏好时间
            prefs = await self.user_preference_service.get_notification_preferences(
                prompt.user_id
            )
            preferred_time = prefs.get("preferred_notification_time", "09:00")
            return self._parse_preferred_time(preferred_time)
        
        return datetime.now()
```

### 3.4 响应处理器 (ResponseHandler)

#### **3.4.1 响应处理流程**
```python
class CoachingResponseHandler:
    """教练响应处理器"""
    
    async def handle_user_response(self, prompt_id: str, response: UserResponse) -> Dict:
        """处理用户对教练提示的响应"""
        
        # 1. 获取原始提示
        prompt = await self._get_prompt(prompt_id)
        if not prompt:
            return {"success": False, "error": "提示不存在"}
        
        # 2. 验证响应有效性
        if not await self._validate_response(prompt, response):
            return {"success": False, "error": "无效响应"}
        
        # 3. 更新提示状态
        await self._update_prompt_state(prompt_id, PromptState.RESPONDED)
        
        # 4. 根据响应类型处理
        result = await self._process_response_by_type(prompt, response)
        
        # 5. 生成后续行动
        follow_up = await self._generate_follow_up(prompt, response, result)
        
        # 6. 记录交互历史
        await self._log_interaction(prompt, response, result)
        
        return {
            "success": True,
            "result": result,
            "follow_up": follow_up,
            "next_step": result.get("next_step")
        }
    
    async def _process_response_by_type(self, prompt: CoachingPrompt, response: UserResponse) -> Dict:
        """根据响应类型处理"""
        
        response_value = response.value
        
        if response_value == "complete_now":
            # 立即完成习惯
            habit_id = prompt.metadata.get("habit_id")
            if habit_id:
                completion = await self._record_habit_completion(
                    prompt.user_id, habit_id
                )
                return {
                    "action": "habit_completed",
                    "habit_id": habit_id,
                    "completion_id": completion.id,
                    "next_step": "celebrate_completion"
                }
        
        elif response_value == "skip_today":
            # 报告中断
            interruption = await self._report_interruption(
                prompt.user_id,
                prompt.metadata.get("habit_id"),
                reason="user_skipped"
            )
            return {
                "action": "interruption_reported",
                "interruption_id": interruption.id,
                "next_step": "recovery_plan"
            }
        
        elif response_value == "adjust_habit":
            # 开始习惯调整对话
            conversation = await self._start_habit_adjustment_conversation(
                prompt.user_id,
                prompt.metadata.get("habit_id")
            )
            return {
                "action": "adjustment_conversation_started",
                "conversation_id": conversation.id,
                "next_step": "habit_adjustment_flow"
            }
        
        elif response_value == "talk_about_challenge":
            # 开始挑战讨论对话
            conversation = await self._start_challenge_conversation(
                prompt.user_id,
                prompt.metadata.get("habit_id")
            )
            return {
                "action": "challenge_conversation_started",
                "conversation_id": conversation.id,
                "next_step": "coaching_dialogue"
            }
        
        # 默认处理
        return {
            "action": "response_acknowledged",
            "next_step": "continue_coaching"
        }
```

## 四、调度系统设计

### 4.1 扩展现有通知调度器

```python
class CoachingPromptScheduler(NotificationScheduler):
    """教练提示调度器（扩展自现有通知调度器）"""
    
    def __init__(self):
        super().__init__()
        self.timing_detector = CoachingTimingDetector()
        self.prompt_generator = CoachingPromptGenerator()
        self.dispatcher = CoachingChannelDispatcher()
        self.response_handler = CoachingResponseHandler()
        self.prompt_queue = CoachingPromptQueue()
    
    async def _check_and_schedule_prompts(self):
        """检查并调度教练提示"""
        try:
            # 1. 获取活跃用户列表
            active_users = await self._get_active_users()
            
            for user_id in active_users:
                try:
                    # 2. 检测提示时机
                    timings = await self.timing_detector.detect_prompt_timing(user_id)
                    
                    for timing in timings:
                        # 3. 生成提示
                        user_context = await self._get_user_context(user_id)
                        prompt = await self.prompt_generator.generate_prompt(timing, user_context)
                        
                        # 4. 加入队列
                        await self.prompt_queue.add(prompt)
                        
                        logger.info(f"为用户 {user_id} 生成提示: {timing.type.value}")
                
                except Exception as e:
                    logger.error(f"处理用户 {user_id} 时出错: {e}", exc_info=True)
            
            # 5. 处理队列中的提示
            await self._process_prompt_queue()
            
        except Exception as e:
            logger.error(f"调度教练提示时出错: {e}", exc_info=True)
    
    async def _process_prompt_queue(self):
        """处理提示队列"""
        # 获取待发送的提示（按优先级排序）
        pending_prompts = await self.prompt_queue.get_pending(limit=50)
        
        for prompt in pending_prompts:
            try:
                # 检查是否应该发送（频率控制、免打扰时段等）
                if await self._should_send_prompt(prompt):
                    # 发送提示
                    success = await self.dispatcher.dispatch_prompt(prompt)
                    
                    if success:
                        await self.prompt_queue.mark_as_sent(prompt.id)
                    else:
                        await self.prompt_queue.mark_as_failed(prompt.id)
                        
            except Exception as e:
                logger.error(f"发送提示 {prompt.id} 时出错: {e}")
                await self.prompt_queue.mark_as_failed(prompt.id)
```

### 4.2 频率控制和免打扰

```python
class PromptFrequencyController:
    """提示频率控制器"""
    
    def __init__(self):
        self.user_limits = {
            "daily_max": 5,      # 每日最大提示数
            "hourly_max": 2,     # 每小时最大提示数
            "min_interval_minutes": 30  # 最小间隔分钟数
        }
    
    async def should_send_prompt(self, user_id: int, prompt: CoachingPrompt) -> bool:
        """判断是否应该发送提示"""
        
        # 1. 检查免打扰时段
        if await self._is_quiet_hours(user_id):
            logger.info(f"用户 {user_id} 处于免打扰时段，跳过提示")
            return False
        
        # 2. 检查今日提示数量
        today_count = await self._get_today_prompt_count(user_id)
        if today_count >= self.user_limits["daily_max"]:
            logger.info(f"用户 {user_id} 今日提示已达上限 ({today_count})")
            return False
        
        # 3. 检查最近提示间隔
        last_prompt_time = await self._get_last_prompt_time(user_id)
        if last_prompt_time:
            minutes_since_last = (datetime.now() - last_prompt_time).total_seconds() / 60
            if minutes_since_last < self.user_limits["min_interval_minutes"]:
                logger.info(f"用户 {user_id} 提示间隔太短 ({minutes_since_last:.1f}分钟)")
                return False
        
        # 4. 检查用户响应率（如果响应率低，减少提示频率）
        response_rate = await self._get_user_response_rate(user_id)
        if response_rate < 0.3:  # 响应率低于30%
            # 降低频率：只发送高优先级提示
            if prompt.priority != Priority.HIGH:
                logger.info(f"用户 {user_id} 响应率低 ({response_rate:.0%})，跳过中低优先级提示")
                return False
        
        # 5. 检查提示类型频率限制
        if not await self._check_type_frequency(user_id, prompt.timing_type):
            return False
        
        return True
    
    async def _is_quiet_hours(self, user_id: int) -> bool:
        """检查是否免打扰时段"""
        user_prefs = await self._get_user_preferences(user_id)
        
        if not user_prefs.get("do_not_disturb_enabled", False):
            return False
        
        quiet_start = user_prefs.get("quiet_hours_start", "22:00")
        quiet_end = user_prefs.get("quiet_hours_end", "08:00")
        
        current_time = datetime.now().time()
        start_time = self._parse_time(quiet_start)
        end_time = self._parse_time(quiet_end)
        
        # 处理跨天的免打扰时段
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:
            return current_time >= start_time or current_time <= end_time
```

## 五、数据库设计

### 5.1 新增数据表

```sql
-- 教练提示表
CREATE TABLE coaching_prompts (
    id VARCHAR(64) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    timing_type VARCHAR(50) NOT NULL,  -- daily_checkin, habit_missed, etc.
    priority VARCHAR(20) NOT NULL,     -- high, medium, low
    state VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, delivered, responded, expired
    
    -- 内容
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    quick_replies JSONB,               -- 快速回复选项
    media_type VARCHAR(20),
    media_url TEXT,
    card_data JSONB,
    
    -- 发送配置
    delivery_channel VARCHAR(20) NOT NULL,
    scheduled_for TIMESTAMP,
    sent_at TIMESTAMP,
    
    -- 响应信息
    responded_at TIMESTAMP,
    response_value TEXT,
    response_action VARCHAR(50),
    
    -- 元数据
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 索引
    INDEX idx_coaching_prompts_user_state (user_id, state),
    INDEX idx_coaching_prompts_scheduled (scheduled_for) WHERE state = 'pending',
    INDEX idx_coaching_prompts_created (created_at)
);

-- 用户提示偏好表
CREATE TABLE user_prompt_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    
    -- 频率限制
    daily_max_prompts INTEGER DEFAULT 5,
    min_interval_minutes INTEGER DEFAULT 30,
    
    -- 渠道偏好
    preferred_channels JSONB NOT NULL DEFAULT '["in_app_chat", "push"]',
    channel_priorities JSONB NOT NULL DEFAULT '{"in_app_chat": 1, "push": 2, "email": 3}',
    
    -- 免打扰设置
    do_not_disturb_enabled BOOLEAN DEFAULT FALSE,
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    
    -- 提示类型偏好
    enabled_prompt_types JSONB NOT NULL DEFAULT '["daily_checkin", "habit_missed", "weekly_review"]',
    type_sensitivities JSONB NOT NULL DEFAULT '{}',  -- 各类型敏感度设置
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 提示交互历史表
CREATE TABLE prompt_interaction_history (
    id SERIAL PRIMARY KEY,
    prompt_id VARCHAR(64) NOT NULL REFERENCES coaching_prompts(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    
    -- 交互信息
    action_type VARCHAR(50) NOT NULL,  -- prompt_sent, user_responded, follow_up_sent, etc.
    action_value TEXT,
    
    -- 效果数据
    response_time_seconds INTEGER,     -- 响应时间（秒）
    engagement_score FLOAT,            -- 互动评分
    effectiveness_score FLOAT,         -- 效果评分
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 索引
    INDEX idx_prompt_interactions_prompt (prompt_id),
    INDEX idx_prompt_interactions_user (user_id, created_at)
);
```

## 六、API设计

### 6.1 新增API端点

```
# 提示管理API
GET    /api/v2/coaching/prompts          # 获取用户的教练提示列表
GET    /api/v2/coaching/prompts/{id}     # 获取特定提示详情
POST   /api/v2/coaching/prompts/{id}/respond  # 响应教练提示
DELETE /api/v2/coaching/prompts/{id}     # 删除/取消提示

# 用户偏好API
GET    /api/v2/coaching/preferences      # 获取用户提示偏好
PUT    /api/v2/coaching/preferences      # 更新用户提示偏好

# 管理API（后台）
POST   /api/v2/admin/coaching/prompts/generate  # 手动生成提示（测试用）
GET    /api/v2/admin/coaching/prompts/stats     # 提示统计信息
POST   /api/v2/admin/coaching/prompts/test      # 测试提示生成和发送
```

### 6.2 WebSocket实时通知

```python
# WebSocket连接处理教练提示
@router.websocket("/ws/coaching")
async def coaching_websocket(websocket: WebSocket, user_id: int = Depends(get_current_user)):
    await websocket.accept()
    
    try:
        # 发送待处理的提示
        pending_prompts = await get_pending_prompts(user_id)
        for prompt in pending_prompts:
            await websocket.send_json({
                "type": "coaching_prompt",
                "data": prompt.to_dict()
            })
        
        # 监听用户响应
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "prompt_response":
                # 处理用户响应
                result = await handle_prompt_response(
                    prompt_id=data["prompt_id"],
                    response=data["response"]
                )
                
                # 发送处理结果
                await websocket.send_json({
                    "type": "response_result",
                    "data": result
                })
                
                # 如果有后续行动，发送后续提示
                if result.get("follow_up"):
                    await websocket.send_json({
                        "type": "follow_up_prompt",
                        "data": result["follow_up"]
                    })
    
    except WebSocketDisconnect:
        logger.info(f"用户 {user_id} 的教练WebSocket连接断开")
```

## 七、部署和监控

### 7.1 部署配置

```yaml
# docker-compose.yml 新增服务
coaching-scheduler:
  build: .
  command: python -m services.coaching_scheduler
  environment:
    - REDIS_HOST=redis
    - DATABASE_URL=postgresql://user:pass@db:5432/coaching
  depends_on:
    - redis
    - db
  restart: unless-stopped

# 环境变量配置
COACHING_PROMPT_ENABLED=true
COACHING_SCHEDULER_INTERVAL=300  # 5分钟
COACHING_MAX_DAILY_PROMPTS=5
COACHING_MIN_INTERVAL_MINUTES=30
```

### 7.2 监控指标

```python
# Prometheus监控指标
coaching_prompts_total = Counter(
    'coaching_prompts_total',
    'Total coaching prompts generated',
    ['timing_type', 'priority']
)

coaching_prompts_delivered = Counter(
    'coaching_prompts_delivered',
    'Coaching prompts delivered',
    ['channel', 'timing_type']
)

coaching_response_rate = Gauge(
    'coaching_response_rate',
    'User response rate to coaching prompts',
    ['user_segment']
)

coaching_response_time = Histogram(
    'coaching_response_time_seconds',
    'Time users take to respond to prompts',
    buckets=[10, 30, 60, 300, 600, 1800]  # 10秒到30分钟
)

coaching_engagement_score = Gauge(
    'coaching_engagement_score',
    'Average engagement score for coaching prompts',
    ['prompt_type']
)
```

## 八、实施计划

### 8.1 第一阶段：基础框架（1-2周）
1. 数据库表创建和迁移
2. 基础提示生成和发送框架
3. 简单的规则检测器
4. 应用内聊天渠道集成

### 8.2 第二阶段：智能检测（2-3周）
1. AI时机检测器实现
2. 个性化提示生成
3. 频率控制和免打扰机制
4. 响应处理框架

### 8.3 第三阶段：高级功能（2-3周）
1. 多渠道分发（推送、邮件）
2. WebSocket实时通知
3. A/B测试框架
4. 效果评估和优化

### 8.4 第四阶段：优化和扩展（1-2周）
1. 性能优化
2. 监控和告警
3. 用户偏好管理界面
4. 管理员控制台

---

**总结**: 教练主动提示系统通过**时机检测 → 内容生成 → 渠道分发 → 响应处理**的完整流程，实现了智能、个性化、非侵入式的教练引导。系统建立在现有通知架构之上，确保了技术可行性和可维护性。
