"""快速测试统一Agent"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.database import AsyncSessionLocal, User
from services.langchain.unified_agent import run_unified_agent

async def test():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.openid == 'test_user'))
        user = result.scalar_one_or_none()
        if not user:
            user = User(openid='test_user', nickname='测试')
            db.add(user)
            await db.commit()
            await db.refresh(user)
        
        print(f'用户ID: {user.id}')
        print('用户: 我想养成喝水习惯\n')
        
        result = await run_unified_agent(
            user_id=user.id,
            db=db,
            user_input='我想养成喝水习惯'
        )
        
        print(f'AI: {result["response"][:150]}...')
        print(f'\n工具: {result["tools_used"]}')

if __name__ == "__main__":
    asyncio.run(test())
