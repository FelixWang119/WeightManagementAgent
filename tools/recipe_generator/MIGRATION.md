# 食谱生成工具迁移说明

## 从旧脚本迁移到新工具

原来的食谱生成脚本已经整合到新的工具包中。以下是迁移指南：

### 旧脚本 vs 新工具

| 旧脚本文件 | 新工具模块 | 说明 |
|------------|------------|------|
| `scripts/generate_diet_recipes.py` | `tools.recipe_generator.main generate` | 生成食谱 |
| `scripts/create_diet_recipes.py` | `tools.recipe_generator.main pipeline` | 完整流程 |
| `scripts/create_recipes_noninteractive.py` | `tools.recipe_generator.main generate` + `import` | 非交互式生成导入 |
| `scripts/check_recipes.py` | `tools.recipe_generator.main check` | 检查数据库 |
| `scripts/generate_recipes_simple.py` | `tools.recipe_generator.main generate -c 5` | 简单生成 |

### 命令对照表

#### 1. 生成食谱
```bash
# 旧命令
python scripts/generate_diet_recipes.py
python scripts/generate_recipes_simple.py

# 新命令
python -m tools.recipe_generator.main generate
python -m tools.recipe_generator.main generate -c 5
```

#### 2. 导入食谱
```bash
# 旧命令
python scripts/create_recipes_noninteractive.py

# 新命令
python -m tools.recipe_generator.main pipeline -c 10
```

#### 3. 检查数据库
```bash
# 旧命令
python scripts/check_recipes.py

# 新命令
python -m tools.recipe_generator.main check
```

#### 4. 完整流程
```bash
# 旧命令
python scripts/create_diet_recipes.py

# 新命令
python -m tools.recipe_generator.main pipeline -c 20
```

### 功能改进

新工具相比旧脚本有以下改进：

1. **模块化设计**：分离生成器、导入器、检查器
2. **更好的错误处理**：更完善的API错误处理和重试机制
3. **命令行接口**：统一的命令行参数解析
4. **配置管理**：更好的环境变量处理
5. **代理支持**：自动处理代理环境变量问题
6. **文档完善**：完整的README和使用说明

### 数据迁移

如果已经有生成的JSON文件，可以使用新工具导入：

```bash
# 导入旧的JSON文件
python -m tools.recipe_generator.main import -f scripts/generated_recipes.json
python -m tools.recipe_generator.main import -f scripts/diet_recipes_complete.json
```

### 清理旧文件

建议清理旧的脚本文件：

```bash
# 删除旧的食谱生成脚本
rm scripts/generate_diet_recipes.py
rm scripts/create_diet_recipes.py
rm scripts/create_recipes_noninteractive.py
rm scripts/generate_recipes_simple.py
rm scripts/check_recipes.py

# 删除旧的JSON文件（可选）
rm scripts/*.json
```

### 保留的文件

以下文件应该保留：
- `scripts/init_sample_recipes.py` - 示例食谱初始化
- `scripts/init_database.py` - 数据库初始化
- `scripts/create_admin.py` - 管理员创建
- 其他项目相关脚本

### 更新项目文档

已更新主项目的README.md，添加了食谱生成工具的说明。请确保团队成员了解新的使用方法。

## 新工具优势

1. **统一接口**：所有功能通过一个命令访问
2. **易于扩展**：模块化设计便于添加新功能
3. **更好的维护**：代码结构清晰，易于维护
4. **完整文档**：详细的README和使用说明
5. **错误恢复**：更好的错误处理和恢复机制

## 后续开发

如需扩展功能，可以参考以下方向：

1. **添加更多食谱主题**：修改 `generator.py` 中的 `recipe_themes`
2. **支持其他AI模型**：扩展 `generator.py` 支持OpenAI等
3. **批量处理优化**：改进批量生成和导入的性能
4. **食谱编辑功能**：添加食谱编辑和更新功能
5. **图片生成**：集成图片生成API为食谱添加图片