"""
体重管理助手 - 主程序入口
FastAPI 应用
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from config.settings import fastapi_settings
from models.database import init_db


# ============ 生命周期管理 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    print("🚀 正在启动应用...")
    await init_db()
    print(f"✅ 应用已启动：{fastapi_settings.APP_NAME} v{fastapi_settings.APP_VERSION}")
    print(f"📍 访问地址：http://{fastapi_settings.HOST}:{fastapi_settings.PORT}")
    
    yield
    
    # 关闭时执行
    print("🛑 应用正在关闭...")


# ============ FastAPI 应用实例 ============

app = FastAPI(
    title=fastapi_settings.APP_NAME,
    version=fastapi_settings.APP_VERSION,
    description="AI驱动的个性化体重管理助手",
    lifespan=lifespan,
    docs_url="/docs" if fastapi_settings.DEBUG else None,
    redoc_url="/redoc" if fastapi_settings.DEBUG else None,
)

# ============ 中间件配置 ============

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ 静态文件 ============

# 上传文件目录
import os
os.makedirs(fastapi_settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=fastapi_settings.UPLOAD_DIR), name="uploads")

# 静态文件目录（前端页面）
static_dir = project_root / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    print(f"📁 静态文件目录: {static_dir}")

# 管理后台快捷访问 - 重定向到静态文件
@app.get("/admin")
async def admin_redirect():
    """重定向到管理后台登录页"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/admin/login.html")

@app.get("/admin/login.html")
async def admin_login_page():
    """重定向到登录页"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/admin/login.html")

@app.get("/admin/index.html")
async def admin_index_page():
    """重定向到管理后台首页"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/admin/index.html")

# 用户端页面路由
@app.get("/goals.html")
async def goals_page():
    """目标管理页面"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/goals.html")

@app.get("/reminders.html")
async def reminders_page():
    """提醒设置页面"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/reminders.html")

@app.get("/calculator.html")
async def calculator_page():
    """热量计算器页面"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/calculator.html")

@app.get("/favicon.ico")
async def favicon():
    """favicon"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/favicon.svg")

@app.get("/favicon.svg")
async def favicon_svg():
    """favicon svg"""
    from fastapi.responses import FileResponse
    from pathlib import Path
    favicon_path = Path(__file__).parent / "static" / "favicon.svg"
    return FileResponse(favicon_path, media_type="image/svg+xml")

@app.get("/login.html")
async def login_page():
    """用户登录页"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/login.html")

# ============ API 路由 ============

@app.get("/")
async def root():
    """根路径 - API 信息"""
    return {
        "name": fastapi_settings.APP_NAME,
        "version": fastapi_settings.APP_VERSION,
        "status": "running",
        "docs": "/docs" if fastapi_settings.DEBUG else None
    }


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00",  # 实际应该返回当前时间
        "version": fastapi_settings.APP_VERSION
    }


# 导入并注册 API 路由
from api.routes import chat, weight, user, meal, exercise, water, sleep, report, reminder, profiling, config, calories, goals
from api.routes.admin import auth as admin_auth
from api.routes.admin import prompts as admin_prompts
from api.routes.admin import users as admin_users
from api.routes.admin import chat_records_v2 as admin_chat_records  # 使用V2版本
from api.routes.admin import system as admin_system

app.include_router(user.router, prefix="/api/user", tags=["用户"])
app.include_router(chat.router, prefix="/api/chat", tags=["对话"])
app.include_router(weight.router, prefix="/api/weight", tags=["体重"])
app.include_router(meal.router, prefix="/api/meal", tags=["餐食"])
app.include_router(exercise.router, prefix="/api/exercise", tags=["运动"])
app.include_router(water.router, prefix="/api/water", tags=["饮水"])
app.include_router(sleep.router, prefix="/api/sleep", tags=["睡眠"])
app.include_router(report.router, prefix="/api/report", tags=["周报"])
app.include_router(reminder.router, prefix="/api/reminder", tags=["提醒"])
app.include_router(profiling.router, prefix="/api/profiling", tags=["用户画像"])
app.include_router(config.router, prefix="/api/config", tags=["配置"])
app.include_router(calories.router, prefix="/api/calories", tags=["热量计算"])
app.include_router(goals.router, prefix="/api/goals", tags=["目标管理"])

# 管理员路由
app.include_router(admin_auth.router, prefix="/admin/auth", tags=["管理员认证"])
app.include_router(admin_prompts.router, prefix="/admin/prompts", tags=["提示词管理"])
app.include_router(admin_users.router, prefix="/admin/users", tags=["用户管理"])
app.include_router(admin_chat_records.router, prefix="/admin/chat-records", tags=["聊天记录管理"])
app.include_router(admin_system.router, prefix="/admin/system", tags=["系统管理"])


# ============ 错误处理 ============

from fastapi.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP 异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


# ============ 启动入口 ============

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main_new:app",
        host=fastapi_settings.HOST,
        port=fastapi_settings.PORT,
        reload=fastapi_settings.DEBUG,
        log_level=fastapi_settings.LOG_LEVEL.lower()
    )
