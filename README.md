# 体重管理助手

AI驱动的个性化体重管理伙伴 - 后端服务

## 🚀 快速开始

### 1. 环境准备

确保已安装：
- Python 3.9+
- pip

### 2. 配置项目

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑 .env 文件，填入必要配置
# 特别是 OPENAI_API_KEY（从 https://platform.openai.com/api-keys 获取）
```

### 3. 启动应用

#### 方法一：使用启动脚本（推荐）

```bash
chmod +x start.sh
./start.sh
```

#### 方法二：手动启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动应用
python main_new.py
```

### 4. 访问服务

- 主服务：http://localhost:8000
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 📁 项目结构

```
weight-management/
├── main_new.py              # FastAPI 主程序
├── requirements.txt         # 依赖列表
├── .env.example            # 环境变量示例
├── start.sh                # 启动脚本
├── config/                 # 配置文件
│   ├── settings.py         # 应用配置
│   └── logging_config.py   # 日志配置
├── api/                    # API 路由
│   ├── routes/            # 路由处理
│   └── dependencies.py    # 依赖注入
├── models/                 # 数据库模型
│   └── database.py        # SQLAlchemy 模型
├── services/              # 业务逻辑服务
├── schemas/               # Pydantic 模型
├── utils/                 # 工具函数
├── static/                # 静态文件
├── uploads/               # 上传文件存储
├── logs/                  # 日志文件
└── docs/                  # 文档
    └── plans/             # 设计文档
        ├── 2025-02-07-weight-management-design.md
        └── 2025-02-07-weight-management-design.pdf
```

## ⚙️ 环境变量配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DEBUG` | 调试模式 | `true` |
| `DATABASE_URL` | 数据库连接 | SQLite |
| `OPENAI_API_KEY` | OpenAI API 密钥 | 必填 |
| `OPENAI_MODEL` | AI 模型 | `gpt-4` |
| `WECHAT_APPID` | 微信小程序 AppID | 可选 |
| `WECHAT_SECRET` | 微信小程序 Secret | 可选 |
| `SECRET_KEY` | 应用密钥 | 请修改 |

## 🛠️ 开发

### 代码格式化

```bash
# 使用 black 格式化
black .

# 使用 isort 排序导入
isort .

# 代码检查
flake8
mypy
```

### 运行测试

```bash
pytest
```

## 📚 文档

- [完整设计文档](./docs/plans/2025-02-07-weight-management-design.md)
- [PDF 版本](./docs/plans/2025-02-07-weight-management-design.pdf)

## 📄 许可证

MIT License
