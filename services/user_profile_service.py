"""
用户画像服务
提供带持久化缓存功能的用户画像数据获取服务

功能：
1. 获取完整的用户画像数据（基础信息 + 问卷回答 + 当前体重 + Agent配置）
2. 缓存管理（数据库持久化缓存，系统重启不丢失）
3. 缓存版本验证（基于依赖表的更新时间戳）
4. 缓存失效机制（供小调查提交后调用）
"""

from typing import Dict, Any, Optional
from datetime import datetime
import json
import time

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from models.database import (
    UserProfile, ProfilingAnswer, WeightRecord, AgentConfig, UserProfileCache
)
from config.assistant_styles import AssistantStyle, get_style_config
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class UserProfileService:
    """用户画像服务（带持久化缓存）"""
    
    @staticmethod
    async def get_complete_profile(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """
        获取完整的用户画像数据（带缓存）
        
        Args:
            user_id: 用户ID
            db: 数据库会话
            
        Returns:
            结构化的用户画像数据字典
        """
        # 1. 检查缓存
        cache_data = await UserProfileService._get_cached_profile(user_id, db)
        
        # 2. 计算当前数据版本（所有依赖表的最大更新时间）
        current_version = await UserProfileService._calculate_data_version(user_id, db)
        
        # 3. 如果缓存有效且版本匹配，直接返回缓存
        if cache_data and cache_data.get("data_version") == current_version.isoformat():
            logger.debug("用户 %s 的画像缓存命中", user_id)
            return cache_data["cached_data"]
        
        # 4. 缓存无效或过期，重新计算并更新缓存
        logger.info("用户 %s 的画像缓存未命中或过期，重新计算", user_id)
        profile_data = await UserProfileService._calculate_profile_data(user_id, db)
        
        # 5. 保存到缓存
        await UserProfileService._save_profile_cache(
            user_id, db, profile_data, current_version
        )
        
        return profile_data
    
    @staticmethod
    async def _get_cached_profile(user_id: int, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """获取缓存的用户画像数据"""
        try:
            result = await db.execute(
                select(UserProfileCache).where(UserProfileCache.user_id == user_id)
            )
            cache = result.scalar_one_or_none()
            if cache:
                return {
                    "cached_data": cache.cached_data,
                    "data_version": cache.data_version.isoformat() if cache.data_version else None
                }
        except Exception as e:
            # 缓存读取失败不影响主功能，继续重新计算
            logger.debug("读取用户 %s 的画像缓存失败: %s", user_id, e)
        return None
    
    @staticmethod
    async def _calculate_data_version(user_id: int, db: AsyncSession) -> datetime:
        """
        计算数据版本时间戳
        
        取以下表的最大更新时间：
        1. UserProfile.updated_at
        2. ProfilingAnswer.created_at（最新回答时间）
        3. WeightRecord.record_time（最新体重记录）
         4. AgentConfig.updated_at
        """
        # 1. UserProfile更新时间
        result = await db.execute(
            select(func.max(UserProfile.updated_at)).where(
                UserProfile.user_id == user_id
            )
        )
        profile_updated = result.scalar()
        
        # 2. 最新ProfilingAnswer创建时间
        result = await db.execute(
            select(func.max(ProfilingAnswer.created_at)).where(
                ProfilingAnswer.user_id == user_id
            )
        )
        answer_created = result.scalar()
        
        # 3. 最新WeightRecord记录时间
        result = await db.execute(
            select(func.max(WeightRecord.record_time)).where(
                WeightRecord.user_id == user_id
            )
        )
        weight_updated = result.scalar()
        
        # 4. AgentConfig更新时间
        result = await db.execute(
            select(func.max(AgentConfig.updated_at)).where(
                AgentConfig.user_id == user_id
            )
        )
        agent_updated = result.scalar()
        
        # 取所有时间戳中的最大值
        timestamps = [ts for ts in [profile_updated, answer_created, weight_updated, agent_updated] if ts]
        if timestamps:
            return max(timestamps)
        else:
            # 如果没有时间戳，返回当前时间
            return datetime.utcnow()
    
    @staticmethod
    async def _calculate_profile_data(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """计算用户画像数据（无缓存）"""
        start_time = time.time()
        logger.debug("开始计算用户 %s 的画像数据", user_id)
        
        # 1. 获取用户画像
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        
        # 2. 获取Agent配置
        result = await db.execute(
            select(AgentConfig).where(AgentConfig.user_id == user_id)
        )
        agent_config = result.scalar_one_or_none()
        
        # 3. 获取最近体重
        result = await db.execute(
            select(WeightRecord)
            .where(WeightRecord.user_id == user_id)
            .order_by(WeightRecord.record_time.desc())
            .limit(1)
        )
        latest_weight = result.scalar_one_or_none()
        
        # 4. 获取用户画像回答
        result = await db.execute(
            select(ProfilingAnswer).where(
                ProfilingAnswer.user_id == user_id
            ).order_by(ProfilingAnswer.created_at)
        )
        answers = result.scalars().all()
        
        # 5. 构建画像描述字典（按问题分类分组）
        profile_desc = {}
        for ans in answers:
            if ans.question_category:
                profile_desc[ans.question_category] = ans.answer_text
        
        # 6. 获取详细风格配置
        personality_type = "warm"  # 默认
        if agent_config and agent_config.personality_type:
            if hasattr(agent_config.personality_type, 'value'):
                personality_type = agent_config.personality_type.value
            else:
                personality_type = agent_config.personality_type
        
        style_addition = ""
        try:
            style = AssistantStyle(personality_type)
            style_config = await get_style_config(style, db)
            style_addition = style_config["system_prompt_addition"]
        except (ValueError, KeyError):
            # 回退到温暖型
            style_config = await get_style_config(AssistantStyle.WARM, db)
            style_addition = style_config["system_prompt_addition"]
        
        # 7. 构建结构化数据（不包含SQLAlchemy模型实例，只包含纯数据）
        profile_data = {
            "user_id": user_id,
            "agent_name": agent_config.agent_name if agent_config else "小助",
            "personality_type": personality_type,
            "style_addition": style_addition,
            "basic_info": {
                "age": profile.age if profile else None,
                "gender": profile.gender if profile else None,
                "height": profile.height if profile else None,
                "bmr": profile.bmr if profile else None,
                "current_weight": latest_weight.weight if latest_weight else None
            },
            "profile_desc": profile_desc
            # 注意：不再包含_raw字段，因为SQLAlchemy模型实例不能安全缓存
        }
        
        elapsed_time = time.time() - start_time
        logger.debug("用户 %s 画像计算完成，耗时 %.3f 秒", user_id, elapsed_time)
        
        return profile_data
    
    @staticmethod
    async def _save_profile_cache(
        user_id: int,
        db: AsyncSession,
        profile_data: Dict[str, Any],
        data_version: datetime
    ) -> None:
        """保存用户画像数据到缓存表"""
        try:
            # 检查是否已存在缓存
            result = await db.execute(
                select(UserProfileCache).where(UserProfileCache.user_id == user_id)
            )
            cache = result.scalar_one_or_none()
            
            if cache:
                # 更新现有缓存
                cache.cached_data = profile_data
                cache.data_version = data_version
                cache.updated_at = datetime.utcnow()
            else:
                # 创建新缓存
                cache = UserProfileCache(
                    user_id=user_id,
                    cached_data=profile_data,
                    data_version=data_version
                )
                db.add(cache)
            
            await db.commit()
        except Exception as e:
            # 缓存保存失败不影响主功能，只记录日志
            logger.warning("保存用户画像缓存失败: %s", e)
            await db.rollback()
    
    @staticmethod
    async def invalidate_cache(user_id: int, db: AsyncSession) -> None:
        """使指定用户的缓存失效（供小调查提交后调用）"""
        try:
            result = await db.execute(
                select(UserProfileCache).where(UserProfileCache.user_id == user_id)
            )
            cache = result.scalar_one_or_none()
            
            if cache:
                # 删除缓存记录，下次会自动重新计算
                await db.delete(cache)
                await db.commit()
                logger.info("用户 %s 的画像缓存已清理", user_id)
        except Exception as e:
            logger.warning("清理用户画像缓存失败: %s", e)
            await db.rollback()
    
    @staticmethod
    async def format_system_prompt(profile_data: Dict[str, Any], conversation_context: str = "") -> str:
        """
        格式化系统提示（用于LangChain Agent）
        
        Args:
            profile_data: 用户画像数据（来自get_complete_profile）
            conversation_context: 对话上下文（内存注入）
            
        Returns:
            完整的系统提示字符串
        """
        prompt_parts = [
            f"你是{profile_data['agent_name']}，用户的专属体重管理伙伴。",
            "",
            "【用户基础信息】",
        ]
        
        # 添加基础信息
        basic_info = profile_data["basic_info"]
        if basic_info["age"] is not None:
            prompt_parts.append(f"- 年龄: {basic_info['age']}岁")
        else:
            prompt_parts.append(f"- 年龄: 未知")
        
        if basic_info["gender"]:
            prompt_parts.append(f"- 性别: {basic_info['gender']}")
        else:
            prompt_parts.append(f"- 性别: 未知")
        
        if basic_info["height"] is not None:
            prompt_parts.append(f"- 身高: {basic_info['height']}cm")
        else:
            prompt_parts.append(f"- 身高: 未知")
        
        if basic_info["bmr"] is not None:
            prompt_parts.append(f"- 基础代谢率(BMR): {basic_info['bmr']}")
        else:
            prompt_parts.append(f"- 基础代谢率(BMR): 未知")
        
        if basic_info["current_weight"] is not None:
            prompt_parts.append(f"- 当前体重: {basic_info['current_weight']}kg")
        
        # 添加用户画像（从画像回答中提取）
        profile_desc = profile_data["profile_desc"]
        if profile_desc:
            prompt_parts.extend(["", "【用户画像】"])
            
            # 基础信息类
            if "basic" in profile_desc:
                prompt_parts.append(f"- 作息/习惯: {profile_desc['basic']}")
            else:
                prompt_parts.append(f"- 作息/习惯: 未知")
            
            # 饮食偏好类
            if "diet" in profile_desc:
                prompt_parts.append(f"- 饮食偏好: {profile_desc['diet']}")
            else:
                prompt_parts.append(f"- 饮食偏好: 未知")
            
            # 运动习惯类
            if "exercise" in profile_desc:
                prompt_parts.append(f"- 运动习惯: {profile_desc['exercise']}")
            else:
                prompt_parts.append(f"- 运动习惯: 未知")
            
            # 睡眠休息类
            if "sleep" in profile_desc:
                prompt_parts.append(f"- 睡眠: {profile_desc['sleep']}")
            else:
                prompt_parts.append(f"- 睡眠: 未知")
            
            # 心理动机类
            if "motivation" in profile_desc:
                prompt_parts.append(f"- 减重动机: {profile_desc['motivation']}")
            else:
                prompt_parts.append(f"- 减重动机: 未知")
        
        # 添加详细风格配置
        prompt_parts.extend(["", profile_data["style_addition"]])
        
        # 添加当前时间
        prompt_parts.extend([
            "",
            f"【当前时间】",
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ])
        
        # 添加对话上下文（内存注入）
        if conversation_context:
            prompt_parts.extend(["", f"【最近对话】", conversation_context])
        
        # 添加通用回复格式
        prompt_parts.extend([
            "",
            "【回复格式】",
            "直接回复用户，不需要解释你使用了什么工具。"
        ])
        
        return "\n".join(prompt_parts)