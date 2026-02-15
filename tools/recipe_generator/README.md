# 食谱生成工具

使用通义千问API自动生成减脂餐食谱并导入数据库的工具。

## 功能特点

- ✅ **AI生成食谱**：使用通义千问API生成减脂、轻食、快手、健康的食谱
- ✅ **自动导入数据库**：将生成的食谱自动导入到应用数据库
- ✅ **数据验证**：完整的食谱数据验证和标准化
- ✅ **多种操作模式**：支持生成、导入、检查、完整流程等多种操作
- ✅ **代理处理**：自动处理代理环境变量问题
- ✅ **错误恢复**：JSON解析失败时的修复机制
- ✅ **统计检查**：详细的数据库食谱统计信息

## 安装要求

1. **Python环境**：Python 3.8+
2. **依赖包**：已在项目requirements.txt中
3. **API密钥**：需要在`.env`文件中配置通义千问API密钥

### 配置API密钥

在项目根目录的`.env`文件中添加：

```bash
# 通义千问(Qwen)配置
QWEN_API_KEY=sk-your-api-key-here
QWEN_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-turbo
```

## 使用方法

### 基本命令

```bash
# 查看帮助
python -m tools.recipe_generator.main --help

# 生成食谱（默认10个）
python -m tools.recipe_generator.main generate

# 生成指定数量的食谱
python -m tools.recipe_generator.main generate -c 20

# 生成食谱并保存到文件
python -m tools.recipe_generator.main generate -c 15 -o recipes.json

# 从JSON文件导入食谱
python -m tools.recipe_generator.main import -f recipes.json

# 检查数据库中的食谱
python -m tools.recipe_generator.main check

# 完整流程：生成、保存、导入、检查
python -m tools.recipe_generator.main pipeline -c 10
```

### 命令行参数

| 参数 | 缩写 | 说明 | 默认值 |
|------|------|------|--------|
| `action` | - | 执行的操作：`generate`(生成), `import`(导入), `check`(检查), `pipeline`(完整流程) | 必填 |
| `--count` | `-c` | 生成食谱的数量 | 10 |
| `--file` | `-f` | JSON文件路径（用于导入） | - |
| `--output` | `-o` | 输出JSON文件路径（用于生成） | - |

## 食谱数据格式

生成的食谱使用以下JSON格式：

```json
[
  {
    "name": "鸡胸肉沙拉",
    "description": "高蛋白低脂肪，适合减脂期",
    "prep_time": 10,
    "cook_time": 5,
    "servings": 1,
    "difficulty": "easy",
    "category": "lunch",
    "cuisine": "chinese",
    "calories_per_serving": 220,
    "protein_per_serving": 30.0,
    "fat_per_serving": 5.0,
    "carbs_per_serving": 15.0,
    "image_url": null,
    "is_public": true,
    "ingredients": [
      {
        "ingredient_name": "鸡胸肉",
        "quantity": 150,
        "unit": "克"
      }
    ],
    "steps": [
      {
        "description": "鸡胸肉洗净，用厨房纸吸干水分"
      }
    ]
  }
]
```

### 字段说明

| 字段 | 类型 | 说明 | 取值范围 |
|------|------|------|----------|
| `name` | string | 食谱名称 | 中文 |
| `description` | string | 食谱描述 | 20字以内 |
| `prep_time` | int | 准备时间 | 5-15分钟 |
| `cook_time` | int | 烹饪时间 | 5-25分钟 |
| `servings` | int | 份量 | 1-2人份 |
| `difficulty` | string | 难度 | easy/medium/hard |
| `category` | string | 分类 | breakfast/lunch/dinner/snack/dessert/soup |
| `cuisine` | string | 菜系 | chinese/western/japanese/korean/vegetarian/low_calorie/high_protein |
| `calories_per_serving` | int | 每份热量 | 150-350大卡 |
| `protein_per_serving` | float | 每份蛋白质 | 10-25克 |
| `fat_per_serving` | float | 每份脂肪 | 3-12克 |
| `carbs_per_serving` | float | 每份碳水化合物 | 15-35克 |
| `image_url` | string/null | 图片URL | 可选 |
| `is_public` | boolean | 是否公开 | true/false |
| `ingredients` | array | 食材列表 | 3-6种食材 |
| `steps` | array | 步骤列表 | 3-5个步骤 |

## 减脂餐设计原则

工具生成的食谱遵循以下减脂餐设计原则：

1. **低热量**：每份150-350大卡
2. **高蛋白**：每份10-25克蛋白质
3. **低脂肪**：使用健康油脂，少油烹饪
4. **高纤维**：多蔬菜，全谷物
5. **少加工**：使用天然食材，避免精加工食品
6. **快手**：总时间不超过40分钟
7. **简单**：步骤清晰，适合厨房新手
8. **清淡**：少油少盐，健康调味

## 食谱主题

工具会生成多种主题的减脂餐：

1. **中式减脂餐**：蒸、煮、凉拌等中式烹饪方法
2. **西式轻食沙拉**：新鲜蔬菜搭配优质蛋白质
3. **高蛋白健身餐**：适合运动前后的高蛋白餐
4. **快手减脂早餐**：10分钟内完成的健康早餐
5. **低卡晚餐**：清淡易消化的晚餐选择
6. **办公室健康便当**：方便携带的午餐便当
7. **素食减脂餐**：植物蛋白为主的健康餐
8. **日韩低卡料理**：少油健康的日韩风味

## 程序模块

### 1. 食谱生成器 (`generator.py`)

- 调用通义千问API生成食谱
- 解析和验证API响应
- 标准化食谱数据格式
- 保存食谱到JSON文件

### 2. 食谱导入器 (`importer.py`)

- 将食谱导入到数据库
- 检查重复食谱
- 支持从JSON文件导入
- 提供示例食谱数据

### 3. 食谱检查器 (`checker.py`)

- 检查数据库中的食谱统计
- 按分类、菜系、难度统计
- 查找低热量、快手食谱
- 显示食谱详细信息

### 4. 主程序 (`main.py`)

- 命令行接口
- 参数解析
- 操作调度
- 完整流程控制

## 开发指南

### 添加新的食谱主题

在 `generator.py` 中修改 `recipe_themes` 列表：

```python
self.recipe_themes = [
    {
        "name": "新主题名称",
        "description": "主题描述",
        "category": ["lunch", "dinner"],
        "cuisine": ["chinese", "low_calorie"]
    }
]
```

### 修改食谱生成提示词

在 `generator.py` 的 `_build_generation_prompt` 方法中修改提示词模板。

### 扩展食谱检查功能

在 `checker.py` 中添加新的检查方法。

## 常见问题

### Q: API调用失败怎么办？
A: 检查以下问题：
1. API密钥是否正确配置
2. 网络连接是否正常
3. 代理设置是否正确（工具会自动禁用代理）

### Q: JSON解析失败怎么办？
A: 工具会自动尝试修复JSON格式，如果仍然失败：
1. 检查API响应是否完整
2. 减少生成数量（-c 参数）
3. 查看日志中的错误信息

### Q: 导入时跳过太多食谱？
A: 这是因为数据库已存在同名食谱，可以：
1. 修改食谱名称
2. 删除数据库中的重复食谱
3. 使用不同的食谱主题

### Q: 代理环境问题？
A: 工具会自动禁用代理环境变量，如果仍有问题：
1. 手动设置环境变量：`export http_proxy=`
2. 检查网络代理配置

## 性能优化

1. **批量生成**：建议每次生成10-20个食谱
2. **延迟处理**：API调用间有3秒延迟，避免限制
3. **错误重试**：API调用失败时会自动重试
4. **数据缓存**：生成的食谱会保存到JSON文件

## 版本历史

### v1.0.0 (2024-02-15)
- 初始版本发布
- 支持食谱生成、导入、检查功能
- 完整的命令行接口
- 通义千问API集成

## 许可证

本项目遵循体重管理助手的许可证协议。