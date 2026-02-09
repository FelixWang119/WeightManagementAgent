"""
提示词管理路由
提供提示词的CRUD、版本控制和测试功能
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, or_, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import asyncio

from models.database import get_db, SystemPrompt, PromptVersion, User, PromptCategory, PromptStatus
from api.dependencies.auth_v2 import get_current_admin
from config.settings import get_fastapi_settings

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)
settings = get_fastapi_settings()


# ============ 请求/响应模型 ============

class PromptBase(BaseModel):
    """提示词基础模型"""
    name: str = Field(..., min_length=1, max_length=100, description="提示词名称")
    description: Optional[str] = Field(None, max_length=500, description="描述")
    content: str = Field(..., min_length=1, description="提示词内容")
    category: PromptCategory = Field(default=PromptCategory.SYSTEM, description="分类")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    meta_data: Optional[Dict[str, Any]] = Field(None, description="元数据")


class PromptCreate(PromptBase):
    """创建提示词请求"""
    change_log: Optional[str] = Field(None, description="变更说明（用于版本记录）")


class PromptUpdate(BaseModel):
    """更新提示词请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="提示词名称")
    description: Optional[str] = Field(None, max_length=500, description="描述")
    content: Optional[str] = Field(None, min_length=1, description="提示词内容")
    category: Optional[PromptCategory] = Field(None, description="分类")
    status: Optional[PromptStatus] = Field(None, description="状态")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    meta_data: Optional[Dict[str, Any]] = Field(None, description="元数据")
    change_log: Optional[str] = Field(None, description="变更说明")


class PromptResponse(PromptBase):
    """提示词响应"""
    id: int
    status: PromptStatus
    version: int
    is_current: bool
    created_by: Optional[int]
    creator_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime]
    usage_count: int
    
    class Config:
        from_attributes = True


class PromptVersionResponse(BaseModel):
    """提示词版本响应"""
    id: int
    prompt_id: int
    version: int
    content: str
    change_log: Optional[str]
    created_by: Optional[int]
    creator_name: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class PromptListResponse(BaseModel):
    """提示词列表响应"""
    total: int
    page: int
    page_size: int
    items: List[PromptResponse]


class PromptTestRequest(BaseModel):
    """提示词测试请求"""
    test_input: str = Field(..., description="测试输入")
    max_tokens: Optional[int] = Field(200, description="最大输出tokens")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="温度参数")


class PromptTestResponse(BaseModel):
    """提示词测试响应"""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    tokens_used: Optional[int] = None
    processing_time_ms: Optional[int] = None


# ============ 辅助函数 ============

async def save_prompt_version(
    db: AsyncSession,
    prompt_id: int,
    version: int,
    content: str,
    change_log: Optional[str],
    created_by: Optional[int]
):
    """保存提示词版本历史"""
    version_record = PromptVersion(
        prompt_id=prompt_id,
        version=version,
        content=content,
        change_log=change_log,
        created_by=created_by
    )
    db.add(version_record)
    await db.commit()


async def get_prompt_with_creator(db: AsyncSession, prompt_id: int) -> Optional[SystemPrompt]:
    """获取提示词及其创建者信息"""
    result = await db.execute(
        select(SystemPrompt)
        .options(selectinload(SystemPrompt.creator))
        .where(SystemPrompt.id == prompt_id)
    )
    return result.scalar_one_or_none()


async def get_prompt_version_with_creator(db: AsyncSession, version_id: int) -> Optional[PromptVersion]:
    """获取提示词版本及其创建者信息"""
    result = await db.execute(
        select(PromptVersion)
        .options(selectinload(PromptVersion.creator))
        .where(PromptVersion.id == version_id)
    )
    return result.scalar_one_or_none()


# ============ API 路由 ============

@router.get("", response_model=PromptListResponse)
async def list_prompts(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    category: Optional[PromptCategory] = Query(None, description="按分类筛选"),
    status: Optional[PromptStatus] = Query(None, description="按状态筛选"),
    search: Optional[str] = Query(None, description="搜索名称或描述"),
    tags: Optional[str] = Query(None, description="按标签筛选（逗号分隔）"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取提示词列表（支持分页和筛选）
    
    需要管理员权限
    """
    # 构建查询条件
    conditions = []
    
    if category:
        conditions.append(SystemPrompt.category == category)
    
    if status:
        conditions.append(SystemPrompt.status == status)
    
    if search:
        search_condition = or_(
            SystemPrompt.name.ilike(f"%{search}%"),
            SystemPrompt.description.ilike(f"%{search}%")
        )
        conditions.append(search_condition)
    
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        # 简单标签搜索（JSON数组包含）
        # 实际生产环境可能需要更复杂的JSON查询
        pass  # 暂时跳过标签搜索
    
    # 只显示当前版本
    conditions.append(SystemPrompt.is_current == True)
    
    # 计算总数
    count_query = select(SystemPrompt).where(*conditions) if conditions else select(SystemPrompt)
    total_result = await db.execute(select(func.count()).select_from(count_query))
    total = total_result.scalar_one()
    
    # 获取数据
    query = (
        select(SystemPrompt)
        .options(selectinload(SystemPrompt.creator))
        .where(*conditions if conditions else True)
        .order_by(desc(SystemPrompt.updated_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    
    result = await db.execute(query)
    prompts = result.scalars().all()
    
    # 转换为响应模型
    prompt_responses = []
    for prompt in prompts:
        creator_name = prompt.creator.nickname if prompt.creator else None
        prompt_responses.append(
            PromptResponse(
                id=prompt.id,
                name=prompt.name,
                description=prompt.description,
                content=prompt.content,
                category=prompt.category,
                status=prompt.status,
                version=prompt.version,
                is_current=prompt.is_current,
                tags=prompt.tags,
                meta_data=prompt.meta_data,
                created_by=prompt.created_by,
                creator_name=creator_name,
                created_at=prompt.created_at,
                updated_at=prompt.updated_at,
                last_used_at=prompt.last_used_at,
                usage_count=prompt.usage_count
            )
        )
    
    return PromptListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=prompt_responses
    )


@router.post("", response_model=PromptResponse)
async def create_prompt(
    prompt_data: PromptCreate,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    创建新提示词
    
    需要管理员权限
    """
    # 检查名称是否已存在（当前版本）
    existing_query = select(SystemPrompt).where(
        and_(
            SystemPrompt.name == prompt_data.name,
            SystemPrompt.is_current == True
        )
    )
    existing_result = await db.execute(existing_query)
    existing_prompt = existing_result.scalar_one_or_none()
    
    if existing_prompt:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"提示词名称 '{prompt_data.name}' 已存在"
        )
    
    # 创建新提示词
    new_prompt = SystemPrompt(
        name=prompt_data.name,
        description=prompt_data.description,
        content=prompt_data.content,
        category=prompt_data.category,
        tags=prompt_data.tags,
        meta_data=prompt_data.meta_data,
        status=PromptStatus.DRAFT,
        version=1,
        is_current=True,
        created_by=user.id
    )
    
    db.add(new_prompt)
    await db.commit()
    await db.refresh(new_prompt)
    
    # 保存版本历史
    await save_prompt_version(
        db=db,
        prompt_id=new_prompt.id,
        version=1,
        content=prompt_data.content,
        change_log=prompt_data.change_log or "初始版本",
        created_by=user.id
    )
    
    logger.info(f"管理员 {user.id} 创建提示词: {prompt_data.name} (ID: {new_prompt.id})")
    
    # 获取创建者信息
    await db.refresh(new_prompt, ["creator"])
    creator_name = new_prompt.creator.nickname if new_prompt.creator else None
    
    return PromptResponse(
        id=new_prompt.id,
        name=new_prompt.name,
        description=new_prompt.description,
        content=new_prompt.content,
        category=new_prompt.category,
        status=new_prompt.status,
        version=new_prompt.version,
        is_current=new_prompt.is_current,
        tags=new_prompt.tags,
        meta_data=new_prompt.meta_data,
        created_by=new_prompt.created_by,
        creator_name=creator_name,
        created_at=new_prompt.created_at,
        updated_at=new_prompt.updated_at,
        last_used_at=new_prompt.last_used_at,
        usage_count=new_prompt.usage_count
    )


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(
    prompt_id: int,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取提示词详情
    
    需要管理员权限
    """
    prompt = await get_prompt_with_creator(db, prompt_id)
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="提示词不存在"
        )
    
    creator_name = prompt.creator.nickname if prompt.creator else None
    
    return PromptResponse(
        id=prompt.id,
        name=prompt.name,
        description=prompt.description,
        content=prompt.content,
        category=prompt.category,
        status=prompt.status,
        version=prompt.version,
        is_current=prompt.is_current,
        tags=prompt.tags,
        meta_data=prompt.meta_data,
        created_by=prompt.created_by,
        creator_name=creator_name,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
        last_used_at=prompt.last_used_at,
        usage_count=prompt.usage_count
    )


@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: int,
    update_data: PromptUpdate,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    更新提示词（创建新版本）
    
    需要管理员权限
    """
    # 获取原提示词
    prompt = await get_prompt_with_creator(db, prompt_id)
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="提示词不存在"
        )
    
    # 检查是否可以更新
    if prompt.status == PromptStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="归档的提示词不能修改"
        )
    
    # 如果内容有变化，创建新版本
    content_changed = update_data.content is not None and update_data.content != prompt.content
    version_increment = 1 if content_changed else 0
    
    # 更新字段
    update_dict = {}
    for field, value in update_data.dict(exclude_unset=True).items():
        if field != "change_log" and value is not None:
            update_dict[field] = value
    
    # 如果有内容变化，设置新版本号
    if content_changed:
        # 标记旧版本为非当前版本
        prompt.is_current = False
        await db.commit()
        
        # 创建新版本记录
        new_version = prompt.version + 1
        new_prompt = SystemPrompt(
            name=update_dict.get("name", prompt.name),
            description=update_dict.get("description", prompt.description),
            content=update_data.content,
            category=update_dict.get("category", prompt.category),
            status=update_dict.get("status", prompt.status),
            tags=update_dict.get("tags", prompt.tags),
            meta_data=update_dict.get("meta_data", prompt.meta_data),
            version=new_version,
            is_current=True,
            created_by=prompt.created_by
        )
        
        db.add(new_prompt)
        await db.commit()
        await db.refresh(new_prompt)
        
        # 保存版本历史
        await save_prompt_version(
            db=db,
            prompt_id=prompt_id,  # 使用原ID（版本表关联原ID）
            version=new_version,
            content=update_data.content,
            change_log=update_data.change_log or "内容更新",
            created_by=user.id
        )
        
        updated_prompt = new_prompt
        logger.info(f"管理员 {user.id} 更新提示词 {prompt_id} 到版本 {new_version}")
        
    else:
        # 仅更新元数据，不创建新版本
        for key, value in update_dict.items():
            setattr(prompt, key, value)
        
        prompt.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(prompt)
        
        updated_prompt = prompt
        logger.info(f"管理员 {user.id} 更新提示词 {prompt_id} 元数据")
    
    # 获取创建者信息
    await db.refresh(updated_prompt, ["creator"])
    creator_name = updated_prompt.creator.nickname if updated_prompt.creator else None
    
    return PromptResponse(
        id=updated_prompt.id,
        name=updated_prompt.name,
        description=updated_prompt.description,
        content=updated_prompt.content,
        category=updated_prompt.category,
        status=updated_prompt.status,
        version=updated_prompt.version,
        is_current=updated_prompt.is_current,
        tags=updated_prompt.tags,
        meta_data=updated_prompt.meta_data,
        created_by=updated_prompt.created_by,
        creator_name=creator_name,
        created_at=updated_prompt.created_at,
        updated_at=updated_prompt.updated_at,
        last_used_at=updated_prompt.last_used_at,
        usage_count=updated_prompt.usage_count
    )


@router.delete("/{prompt_id}")
async def delete_prompt(
    prompt_id: int,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    删除提示词（软删除，标记为归档）
    
    需要管理员权限
    """
    prompt = await get_prompt_with_creator(db, prompt_id)
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="提示词不存在"
        )
    
    # 标记为归档（软删除）
    prompt.status = PromptStatus.ARCHIVED
    prompt.is_current = False
    await db.commit()
    
    logger.info(f"管理员 {user.id} 归档提示词: {prompt.name} (ID: {prompt_id})")
    
    return {"message": "提示词已归档"}


@router.get("/{prompt_id}/versions", response_model=List[PromptVersionResponse])
async def get_prompt_versions(
    prompt_id: int,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取提示词版本历史
    
    需要管理员权限
    """
    result = await db.execute(
        select(PromptVersion)
        .options(selectinload(PromptVersion.creator))
        .where(PromptVersion.prompt_id == prompt_id)
        .order_by(desc(PromptVersion.version))
    )
    versions = result.scalars().all()
    
    version_responses = []
    for version in versions:
        creator_name = version.creator.nickname if version.creator else None
        version_responses.append(
            PromptVersionResponse(
                id=version.id,
                prompt_id=version.prompt_id,
                version=version.version,
                content=version.content,
                change_log=version.change_log,
                created_by=version.created_by,
                creator_name=creator_name,
                created_at=version.created_at
            )
        )
    
    return version_responses


@router.post("/{prompt_id}/publish")
async def publish_prompt(
    prompt_id: int,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    发布/激活提示词
    
    需要管理员权限
    """
    prompt = await get_prompt_with_creator(db, prompt_id)
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="提示词不存在"
        )
    
    if prompt.status == PromptStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="提示词已是活跃状态"
        )
    
    prompt.status = PromptStatus.ACTIVE
    await db.commit()
    
    logger.info(f"管理员 {user.id} 发布提示词: {prompt.name} (ID: {prompt_id})")
    
    return {"message": "提示词已发布"}


@router.post("/{prompt_id}/rollback/{version}")
async def rollback_prompt_version(
    prompt_id: int,
    version: int,
    change_log: str = Body(None, description="回滚说明"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    回滚到指定版本
    
    需要管理员权限
    """
    # 获取原提示词
    prompt = await get_prompt_with_creator(db, prompt_id)
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="提示词不存在"
        )
    
    # 查找指定版本
    version_result = await db.execute(
        select(PromptVersion)
        .where(PromptVersion.prompt_id == prompt_id, PromptVersion.version == version)
    )
    target_version = version_result.scalar_one_or_none()
    
    if not target_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"版本 {version} 不存在"
        )
    
    # 标记当前版本为非当前版本
    prompt.is_current = False
    
    # 创建回滚版本
    new_version = prompt.version + 1
    new_prompt = SystemPrompt(
        name=prompt.name,
        description=prompt.description,
        content=target_version.content,
        category=prompt.category,
        status=prompt.status,
        tags=prompt.tags,
        meta_data=prompt.meta_data,
        version=new_version,
        is_current=True,
        created_by=prompt.created_by
    )
    
    db.add(new_prompt)
    await db.commit()
    
    # 保存版本历史
    await save_prompt_version(
        db=db,
        prompt_id=prompt_id,
        version=new_version,
        content=target_version.content,
        change_log=change_log or f"回滚到版本 {version}",
        created_by=user.id
    )
    
    logger.info(f"管理员 {user.id} 回滚提示词 {prompt_id} 到版本 {version}")
    
    return {"message": f"已回滚到版本 {version}", "new_version": new_version}


@router.post("/{prompt_id}/test", response_model=PromptTestResponse)
async def test_prompt(
    prompt_id: int,
    test_data: PromptTestRequest,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    测试提示词
    
    需要管理员权限
    """
    import time
    
    prompt = await get_prompt_with_creator(db, prompt_id)
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="提示词不存在"
        )
    
    try:
        # 构建测试消息
        test_start_time = time.time()
        
        # 这里应该调用AI服务测试提示词
        # 暂时模拟响应
        import random
        
        # 模拟AI处理延迟
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # 模拟AI响应
        mock_responses = [
            "这是一个测试响应，模拟AI对提示词的处理结果。",
            f"根据您的提示词，我分析了输入：'{test_data.test_input}'。这是一个很好的测试用例。",
            "提示词测试成功！AI能够正确理解并处理这个提示词。",
            f"温度参数设置为 {test_data.temperature}，最大tokens为 {test_data.max_tokens}。"
        ]
        
        output = random.choice(mock_responses)
        
        processing_time_ms = int((time.time() - test_start_time) * 1000)
        tokens_used = random.randint(50, 200)
        
        # 更新使用统计
        prompt.last_used_at = datetime.utcnow()
        prompt.usage_count += 1
        await db.commit()
        
        logger.info(f"管理员 {user.id} 测试提示词: {prompt.name} (ID: {prompt_id})")
        
        return PromptTestResponse(
            success=True,
            output=output,
            tokens_used=tokens_used,
            processing_time_ms=processing_time_ms
        )
        
    except Exception as e:
        logger.exception(f"测试提示词失败: {prompt_id}")
        return PromptTestResponse(
            success=False,
            error=str(e)
        )


# ============ 风格助手管理接口 ============

@router.get("/styles/personality")
async def list_personality_styles(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_admin)
):
    """
    获取所有风格助手配置
    用于管理后台和前端风格选择
    
    需要管理员权限
    """
    from config.assistant_styles import get_all_styles
    
    styles = await get_all_styles(db)
    return {
        "items": styles,
        "total": len(styles)
    }


@router.get("/styles/personality/{style_value}")
async def get_personality_style(
    style_value: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_admin)
):
    """
    获取单个风格配置详情
    
    需要管理员权限
    """
    from config.assistant_styles import AssistantStyle, get_style_config
    
    try:
        style = AssistantStyle(style_value)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的风格类型")
    
    config = await get_style_config(style, db)
    return config