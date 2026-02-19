# 教练主动提示 - SSE后端实现方案

**文档版本**: 1.0  
**创建日期**: 2026-02-17  
**状态**: 技术设计文档  
**关联文档**: [教练主动提示技术方案](coaching-active-prompt-technical.md), [SSE前端实现架构](coaching-sse-frontend-architecture.md)

## 一、概述

### 1.1 目标
实现基于SSE（Server-Sent Events）的后端服务，支持教练主动提示的实时推送，为前端提供稳定、可靠的实时消息通道。

### 1.2 核心需求
1. **高并发连接**: 支持大量用户同时连接
2. **消息可靠性**: 确保消息不丢失、不重复
3. **连接管理**: 高效管理SSE连接生命周期
4. **认证授权**: 安全的用户认证机制
5. **性能监控**: 实时监控连接状态和性能

### 1.3 技术选型
- **框架**: FastAPI + Starlette (支持SSE原生)
- **消息队列**: Redis Pub/Sub (用于消息分发)
- **连接管理**: 内存连接池 + Redis状态存储
- **认证**: JWT Token + 用户会话管理
- **监控**: Prometheus + Grafana

## 二、系统架构

### 2.1 整体架构图
```
┌─────────────────────────────────────────────────────────────────┐
│                        教练提示生成系统                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  时机检测器   │  │  提示生成器   │  │  渠道选择器   │            │
│  │ - 规则检测   │  │ - AI生成     │  │ - 渠道优先级 │            │
│  │ - AI检测     │  │ - 模板匹配   │  │ - 用户偏好   │            │
│  │ - 事件检测   │  │ - 个性化     │  │ - 免打扰设置 │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        SSE消息分发服务                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  SSE路由     │  │  连接管理器   │  │  消息分发器   │            │
│  │ - 认证鉴权   │  │ - 连接池     │  │ - 消息路由   │            │
│  │ - 事件流     │  │ - 心跳检测   │  │ - 广播推送   │            │
│  │ - CORS配置   │  │ - 清理机制   │  │ - 优先级队列 │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  响应处理器   │  │  状态管理器   │  │  监控告警器   │            │
│  │ - 用户响应   │  │ - 连接状态   │  │ - 性能监控   │            │
│  │ - 后续动作   │  │ - 消息状态   │  │ - 错误告警   │            │
│  │ - 数据记录   │  │ - 会话管理   │  │ - 日志记录   │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流
```
教练提示生成 → Redis Pub/Sub → SSE消息分发 → 前端SSE客户端
    ↓                ↓                ↓                ↓
检测时机 → 序列化消息 → 订阅消息 → 建立连接 → 接收消息
    ↓                ↓                ↓                ↓
响应处理 ← 记录响应 ← 处理响应 ← 用户响应 ← 发送响应
```

## 三、核心组件设计

### 3.1 SSE路由 (SSERouter)

#### **3.1.1 路由设计**
```python
# api/routes/sse.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
import json
import asyncio

router = APIRouter()

@router.get("/coaching/sse")
async def coaching_sse_stream(
    token: str = Depends(verify_sse_token),
    user_id: int = Depends(get_current_user_id)
):
    """SSE事件流端点"""
    
    # 验证用户权限
    if not await has_coaching_access(user_id):
        raise HTTPException(status_code=403, detail="无教练访问权限")
    
    # 创建SSE响应
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # 1. 建立SSE连接
            connection_id = await sse_manager.create_connection(user_id)
            
            # 2. 发送连接确认
            yield f"event: connection_established\ndata: {json.dumps({'connection_id': connection_id})}\n\n"
            
            # 3. 发送待处理提示
            pending_prompts = await get_pending_prompts(user_id)
            for prompt in pending_prompts:
                yield format_sse_event("coaching_prompt", prompt)
            
            # 4. 持续监听新消息
            async for message in sse_manager.listen_messages(connection_id):
                yield message
        
        except asyncio.CancelledError:
            # 连接被客户端取消
            await sse_manager.remove_connection(user_id, connection_id)
            raise
        
        except Exception as e:
            # 处理其他错误
            error_event = format_sse_event("error", {"message": str(e)})
            yield error_event
            await sse_manager.remove_connection(user_id, connection_id)
    
    # 返回SSE响应
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用Nginx缓冲
        }
    )
```

#### **3.1.2 认证机制**
```python
async def verify_sse_token(token: str) -> dict:
    """验证SSE连接token"""
    try:
        # 解码JWT token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        # 验证token类型
        if payload.get("type") != "sse":
            raise HTTPException(status_code=401, detail="无效的token类型")
        
        # 验证token有效期
        if payload.get("exp") < datetime.utcnow().timestamp():
            raise HTTPException(status_code=401, detail="token已过期")
        
        return payload
    
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="无效的token")

async def get_current_user_id(payload: dict = Depends(verify_sse_token)) -> int:
    """从token中获取用户ID"""
    return payload.get("user_id")
```

### 3.2 SSE连接管理器 (SSEConnectionManager)

#### **3.2.1 连接管理实现**
```python
# services/sse_connection_manager.py
import asyncio
from typing import Dict, Set, Optional
from collections import defaultdict
import redis.asyncio as redis
import json

class SSEConnectionManager:
    """SSE连接管理器"""
    
    def __init__(self):
        # 内存中的连接映射
        self.user_connections: Dict[int, Set[str]] = defaultdict(set)
        self.connection_users: Dict[str, int] = {}
        
        # Redis连接（用于分布式部署）
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.redis_pubsub = self.redis_client.pubsub()
        
        # 连接锁
        self._lock = asyncio.Lock()
    
    async def create_connection(self, user_id: int) -> str:
        """创建新的SSE连接"""
        connection_id = self._generate_connection_id()
        
        async with self._lock:
            # 存储连接信息
            self.user_connections[user_id].add(connection_id)
            self.connection_users[connection_id] = user_id
            
            # 在Redis中记录连接状态
            await self.redis_client.hset(
                f"sse:connections:{user_id}",
                connection_id,
                json.dumps({
                    "created_at": datetime.utcnow().isoformat(),
                    "last_activity": datetime.utcnow().isoformat()
                })
            )
            
            # 订阅用户专属频道
            await self.redis_pubsub.subscribe(f"sse:user:{user_id}")
        
        logger.info(f"用户 {user_id} 创建SSE连接: {connection_id}")
        return connection_id
    
    async def remove_connection(self, user_id: int, connection_id: str):
        """移除SSE连接"""
        async with self._lock:
            # 从内存中移除
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            if connection_id in self.connection_users:
                del self.connection_users[connection_id]
            
            # 从Redis中移除
            await self.redis_client.hdel(f"sse:connections:{user_id}", connection_id)
            
            # 如果用户没有其他连接，取消订阅
            remaining_connections = await self.redis_client.hlen(f"sse:connections:{user_id}")
            if remaining_connections == 0:
                await self.redis_pubsub.unsubscribe(f"sse:user:{user_id}")
        
        logger.info(f"用户 {user_id} 移除SSE连接: {connection_id}")
    
    async def send_to_user(self, user_id: int, event_type: str, data: dict):
        """向指定用户发送SSE消息"""
        connections = self.user_connections.get(user_id, set())
        
        if not connections:
            logger.warning(f"用户 {user_id} 没有活跃的SSE连接")
            return False
        
        # 格式化SSE消息
        sse_message = self._format_sse_message(event_type, data)
        
        # 发送到Redis频道（分布式部署时使用）
        await self.redis_client.publish(
            f"sse:user:{user_id}",
            json.dumps({
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            })
        )
        
        logger.info(f"向用户 {user_id} 发送 {event_type} 消息")
        return True
    
    async def broadcast(self, event_type: str, data: dict, user_ids: Optional[list] = None):
        """广播消息给多个用户"""
        if user_ids is None:
            # 广播给所有用户
            user_ids = list(self.user_connections.keys())
        
        success_count = 0
        for user_id in user_ids:
            if await self.send_to_user(user_id, event_type, data):
                success_count += 1
        
        logger.info(f"广播 {event_type} 消息给 {success_count}/{len(user_ids)} 个用户")
        return success_count
    
    async def listen_messages(self, connection_id: str) -> AsyncGenerator[str, None]:
        """监听指定连接的消息"""
        user_id = self.connection_users.get(connection_id)
        if not user_id:
            raise ValueError(f"连接 {connection_id} 不存在")
        
        # 监听Redis频道
        async for message in self.redis_pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    
                    # 检查消息是否属于当前用户
                    if data.get("user_id") == user_id:
                        sse_message = self._format_sse_message(
                            data["event_type"],
                            data["data"]
                        )
                        yield sse_message
                
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"解析Redis消息失败: {e}")
    
    def _generate_connection_id(self) -> str:
        """生成唯一的连接ID"""
        import uuid
        return f"conn_{uuid.uuid4().hex[:16]}"
    
    def _format_sse_message(self, event_type: str, data: dict) -> str:
        """格式化SSE消息"""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
```

### 3.3 消息分发器 (MessageDispatcher)

#### **3.3.1 消息分发实现**
```python
# services/coaching_message_dispatcher.py
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

class CoachingMessageDispatcher:
    """教练消息分发器"""
    
    def __init__(self, sse_manager: SSEConnectionManager):
        self.sse_manager = sse_manager
        self.priority_queue = asyncio.PriorityQueue(maxsize=1000)
        self.message_cache = {}  # 消息缓存，避免重复发送
        
    async def dispatch_prompt(self, prompt: CoachingPrompt):
        """分发教练提示"""
        
        # 1. 检查消息是否已发送（去重）
        if self._is_duplicate_message(prompt):
            logger.warning(f"重复消息，跳过发送: {prompt.id}")
            return False
        
        # 2. 检查用户连接状态
        if not await self._check_user_connection(prompt.user_id):
            logger.warning(f"用户 {prompt.user_id} 无活跃连接，消息入队")
            await self._queue_message(prompt)
            return False
        
        # 3. 检查免打扰设置
        if await self._should_mute_prompt(prompt):
            logger.info(f"用户 {prompt.user_id} 处于免打扰时段，消息入队")
            await self._queue_message(prompt, delay=True)
            return False
        
        # 4. 发送消息
        success = await self.sse_manager.send_to_user(
            prompt.user_id,
            "coaching_prompt",
            self._format_prompt_message(prompt)
        )
        
        # 5. 更新消息状态
        if success:
            await self._update_prompt_status(prompt.id, "delivered")
            self._cache_message(prompt)
            logger.info(f"教练提示 {prompt.id} 已发送给用户 {prompt.user_id}")
        else:
            await self._queue_message(prompt)
            logger.warning(f"发送失败，消息入队: {prompt.id}")
        
        return success
    
    async def dispatch_batch(self, prompts: List[CoachingPrompt]) -> Dict:
        """批量分发消息"""
        results = {
            "success": 0,
            "failed": 0,
            "queued": 0,
            "muted": 0
        }
        
        for prompt in prompts:
            try:
                result = await self.dispatch_prompt(prompt)
                
                if result:
                    results["success"] += 1
                else:
                    # 检查具体原因
                    if await self._should_mute_prompt(prompt):
                        results["muted"] += 1
                    elif not await self._check_user_connection(prompt.user_id):
                        results["queued"] += 1
                    else:
                        results["failed"] += 1
            
            except Exception as e:
                logger.error(f"分发消息 {prompt.id} 时出错: {e}")
                results["failed"] += 1
        
        return results
    
    async def process_queue(self):
        """处理队列中的消息"""
        while not self.priority_queue.empty():
            try:
                # 获取优先级最高的消息
                priority, prompt = await self.priority_queue.get()
                
                # 尝试发送
                success = await self.dispatch_prompt(prompt)
                
                if not success:
                    # 发送失败，重新入队（降低优先级）
                    new_priority = priority + 1
                    if new_priority <= 5:  # 最大重试5次
                        await self.priority_queue.put((new_priority, prompt))
                        logger.info(f"消息 {prompt.id} 重新入队，优先级: {new_priority}")
                
                # 标记任务完成
                self.priority_queue.task_done()
                
                # 短暂延迟，避免过载
                await asyncio.sleep(0.1)
            
            except Exception as e:
                logger.error(f"处理队列消息时出错: {e}")
    
    def _format_prompt_message(self, prompt: CoachingPrompt) -> dict:
        """格式化教练提示消息"""
        return {
            "id": prompt.id,
            "type": "coaching_prompt",
            "timing_type": prompt.timing_type.value,
            "priority": prompt.priority.value,
            "title": prompt.title,
            "message": prompt.message,
            "quick_replies": [
                {
                    "text": reply.text,
                    "value": reply.value,
                    "action_type": reply.action_type.value,
                    "next_step": reply.next_step
                }
                for reply in prompt.quick_replies
            ] if prompt.quick_replies else [],
            "card_data": prompt.card_data,
            "media_url": prompt.media_url,
            "timestamp": prompt.created_at.isoformat(),
            "metadata": prompt.metadata
        }
```

### 3.4 响应处理器 (ResponseHandler)

#### **3.4.1 响应处理实现**
```python
# services/coaching_response_handler.py
from typing import Dict, Optional
from datetime import datetime

class CoachingResponseHandler:
    """教练响应处理器"""
    
    def __init__(self, sse_manager: SSEConnectionManager):
        self.sse_manager = sse_manager
        self.db_session = get_async_session()
    
    async def handle_user_response(self, response_data: dict) -> Dict:
        """处理用户响应"""
        
        try:
            prompt_id = response_data.get("prompt_id")
            user_id = response_data.get("user_id")
            response_value = response_data.get("value")
            action = response_data.get("action")
            
            # 1. 验证响应
            if not await self._validate_response(prompt_id, user_id):
                return {"success": False, "error": "无效的响应"}
            
            # 2. 获取原始提示
            prompt = await self._get_prompt(prompt_id)
            if not prompt:
                return {"success": False, "error": "提示不存在"}
            
            # 3. 更新提示状态
            await self._update_prompt_response(prompt_id, response_value, action)
            
            # 4. 根据响应类型处理
            result = await self._process_response(prompt, response_value, action)
            
            # 5. 发送处理结果
            await self.sse_manager.send_to_user(
                user_id,
                "response_result",
                {
                    "prompt_id": prompt_id,
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            # 6. 生成后续提示（如果需要）
            follow_up = await self._generate_follow_up(prompt, response_value, result)
            if follow_up:
                # 延迟发送后续提示
                asyncio.create_task(self._send_follow_up_delayed(user_id, follow_up))
            
            # 7. 记录交互历史
            await self._log_interaction(prompt_id, user_id, response_value, result)
            
            return {
                "success": True,
                "result": result,
                "follow_up_scheduled": bool(follow_up)
            }
        
        except Exception as e:
            logger.error(f"处理用户响应时出错: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def _process_response(self, prompt: CoachingPrompt, response_value: str, action: str) -> Dict:
        """根据响应类型处理"""
        
        if response_value == "complete_now":
            # 完成习惯
            habit_id = prompt.metadata.get("habit_id")
            if habit_id:
                completion = await self._record_habit_completion(
                    prompt.user_id, habit_id
                )
                return {
                    "action": "habit_completed",
                    "message": "习惯已完成记录！",
                    "habit_id": habit_id,
                    "next_step": "celebrate_completion"
                }
        
        elif response_value == "skip_today":
            # 跳过今天
            return {
                "action": "day_skipped",
                "message": "好的，今天先休息一下。明天继续加油！",
                "next_step": "recovery_plan"
            }
        
        elif response_value == "adjust_habit":
            # 调整习惯
            return {
                "action": "habit_adjustment_started",
                "message": "让我们一起来调整这个习惯，让它更适合你。",
                "next_step": "habit_adjustment_flow"
            }
        
        elif response_value == "talk_about_challenge":
            # 讨论挑战
            return {
                "action": "challenge_conversation_started",
                "message": "我很乐意听听你遇到的挑战，我们一起想办法解决。",
                "next_step": "coaching_dialogue"
            }
        
        # 默认处理
        return {
            "action": "response_acknowledged",
            "message": "已收到您的响应。",
            "next_step": "continue_coaching"
        }
```

## 四、API设计

### 4.1 SSE相关API
```
# SSE连接
GET    /api/v2/coaching/sse          # SSE事件流端点

# 用户响应
POST   /api/v2/coaching/prompts/{id}/respond  # 响应教练提示

# 连接状态
GET    /api/v2/coaching/connections/status    # 获取连接状态
DELETE /api/v2/coaching/connections/{id}      # 关闭指定连接

# 管理接口
POST   /api/v2/admin/coaching/broadcast       # 广播消息
GET    /api/v2/admin/coaching/connections     # 查看所有连接
GET    /api/v2/admin/coaching/stats           # 获取统计信息
```

### 4.2 消息格式规范

#### **4.2.1 SSE事件格式**
```
event: coaching_prompt
data: {"id": "prompt_123", "title": "早上好", ...}

event: response_result  
data: {"prompt_id": "prompt_123", "result": {...}}

event: heartbeat
data: {"timestamp": "2026-02-17T09:00:00Z"}

event: error
data: {"message": "连接超时", "code": "timeout"}
```

#### **4.2.2 用户响应格式**
```json
{
  "prompt_id": "prompt_123456",
  "user_id": 1,
  "value": "complete_now",
  "action": "complete_habit",
  "timestamp": "2026-02-17T09:01:00Z",
  "metadata": {
    "device": "web",
    "location": "home"
  }
}
```

## 五、部署和运维

### 5.1 部署架构
```
负载均衡器 (Nginx)
    ↓
应用服务器 (FastAPI + Gunicorn/Uvicorn)
    ↓
SSE连接管理器 + 消息分发器
    ↓
Redis (Pub/Sub + 状态存储)
    ↓
数据库 (PostgreSQL)
```

### 5.2 配置参数
```python
# config/sse_settings.py
SSE_CONFIG = {
    "max_connections_per_user": 3,      # 每个用户最大连接数
    "heartbeat_interval": 30,           # 心跳间隔(秒)
    "connection_timeout": 300,          # 连接超时时间(秒)
    "max_retry_attempts": 5,            # 最大重试次数
    "queue_size": 1000,                 # 消息队列大小
    "batch_size": 50,                   # 批量处理大小
    "redis_channel_prefix": "sse:",     # Redis频道前缀
}
```

### 5.3 监控指标
```python
# 连接监控
sse_connections_total = Gauge("sse_connections_total", "Total SSE connections")
sse_connections_active = Gauge("sse_connections_active", "Active SSE connections")
sse_connection_duration = Histogram("sse_connection_duration_seconds", "SSE connection duration")

# 消息监控
sse_messages_sent_total = Counter("sse_messages_sent_total", "Total SSE messages sent")
sse_messages_received_total = Counter("sse_messages_received_total", "Total SSE messages received")
sse_message_delivery_latency = Histogram("sse_message_delivery_latency_seconds", "Message delivery latency")

# 错误监控
sse_errors_total = Counter("sse_errors_total", "Total SSE errors", ["error_type"])
sse_connection_errors = Counter("sse_connection_errors", "SSE connection errors")
```

### 5.4 健康检查
```python
@router.get("/health")
async def health_check():
    """健康检查端点"""
    checks = {
        "redis": await check_redis_connection(),
        "database": await check_database_connection(),
        "sse_connections": len(sse_manager.connection_users),
        "message_queue": sse_dispatcher.priority_queue.qsize()
    }
    
    status = "healthy" if all(checks.values()) else "unhealthy"
    
    return {
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
    }
```

## 六、安全考虑

### 6.1 认证和授权
- **JWT Token认证**: 每个SSE连接需要有效的JWT token
- **Token刷新机制**: 支持token过期前自动刷新
- **权限验证**: 验证用户是否有教练访问权限
- **连接限制**: 限制每个用户的并发连接数

### 6.2 数据安全
- **HTTPS强制**: 所有SSE连接必须使用HTTPS
- **消息加密**: 敏感消息内容加密传输
- **输入验证**: 严格验证所有用户输入
- **SQL注入防护**: 使用参数化查询

### 6.3 防攻击措施
- **DDoS防护**: 连接频率限制、IP黑名单
- **消息洪水防护**: 消息发送频率限制
- **连接滥用检测**: 异常连接模式检测
- **资源限制**: 限制单个连接资源使用

## 七、性能优化

### 7.1 连接优化
- **连接池管理**: 高效管理SSE连接
- **心跳优化**: 自适应心跳间隔
- **压缩传输**: 支持消息压缩
- **连接复用**: 支持连接复用

### 7.2 消息优化
- **批量处理**: 支持消息批量发送
- **优先级队列**: 基于优先级的消息处理
- **消息缓存**: 避免重复消息发送
- **延迟发送**: 支持消息延迟发送

### 7.3 资源优化
- **内存管理**: 定期清理无效连接
- **数据库优化**: 读写分离、索引优化
- **Redis优化**: 连接池、数据分片
- **异步处理**: 使用异步IO提高并发

## 八、总结

SSE后端实现方案提供了完整的实时消息推送解决方案，具有以下特点：

1. **高可用性**: 支持分布式部署，故障自动转移
2. **高性能**: 支持高并发连接，低延迟消息推送
3. **高可靠性**: 消息不丢失，连接自动重连
4. **易扩展**: 模块化设计，易于扩展新功能
5. **易维护**: 完善的监控、日志、健康检查

该方案与前端SSE实现无缝集成，为教练主动提示系统提供了稳定可靠的后端支持。