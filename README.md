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

### 3. 数据库初始化

应用使用SQLite数据库，首次运行时会自动创建数据库文件。

#### 自动初始化（推荐）
直接启动应用，数据库会自动创建：
```bash
python main_new.py
```

#### 手动初始化
如果需要手动初始化数据库：
```bash
python scripts/init_database.py
```

### 4. 启动应用

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
- [数据库结构文档](./docs/database_schema.md)
- [食谱生成工具文档](./tools/recipe_generator/README.md)

## ❓ 常见问题

### 数据库相关问题

**Q: 数据库文件在哪里？**
A: 数据库文件 `weight_management.db` 在项目根目录下创建。该文件在 `.gitignore` 中排除，不会提交到版本控制。

**Q: 如何重置数据库？**
A: 删除 `weight_management.db` 文件，然后重新启动应用或运行 `python scripts/init_database.py`。

**Q: 数据库会自动备份吗？**
A: 目前需要手动备份。建议定期备份数据库文件：
```bash
cp weight_management.db weight_management_backup_$(date +%Y%m%d).db
```

**Q: 如何查看数据库内容？**
A: 可以使用SQLite命令行工具或SQLite浏览器：
```bash
sqlite3 weight_management.db
.tables  # 查看所有表
.schema users  # 查看用户表结构
SELECT * FROM users LIMIT 5;  # 查看前5条用户数据
```

**Q: 数据库迁移如何处理？**
A: 目前使用SQLAlchemy的自动建表功能。如需迁移，可以：
1. 备份当前数据库
2. 修改模型定义
3. 删除旧数据库文件
4. 重新启动应用创建新数据库

## 🍽️ 食谱生成工具

项目包含一个强大的食谱生成工具，可以使用通义千问API自动生成减脂餐食谱。

### 快速使用

```bash
# 查看帮助
python -m tools.recipe_generator.main --help

# 生成10个减脂餐食谱
python -m tools.recipe_generator.main generate

# 完整流程：生成、导入、检查
python -m tools.recipe_generator.main pipeline -c 20
```

### 主要功能

- **AI生成食谱**：使用通义千问API生成减脂、轻食、快手食谱
- **自动导入**：将生成的食谱自动导入数据库
- **数据检查**：查看数据库中的食谱统计信息
- **多种主题**：支持中式、西式、高蛋白、素食等多种减脂餐主题

### 配置要求

在 `.env` 文件中配置通义千问API密钥：
```bash
QWEN_API_KEY=sk-your-api-key-here
```

详细文档请查看：[食谱生成工具文档](./tools/recipe_generator/README.md)

## 📄 许可证

MIT License
