# API参数绑定规范指南

## 📋 规范概述

基于锻炼打卡功能API参数绑定问题的调试经验，制定本规范以确保前后端API契约的一致性。

## 🎯 适用范围

适用于所有FastAPI后端接口的参数绑定设计。

## 🔧 参数绑定类型

### 1. 路径参数（Path Parameters）

**适用场景**：标识资源的唯一键
```python
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """获取指定用户信息"""
```

**规范要求**：
- 必须使用类型提示（int, str等）
- 参数名与路径中的变量名保持一致

### 2. 查询参数（Query Parameters）

**适用场景**：可选参数、筛选条件、分页参数
```python
@app.get("/users")
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页大小"),
    name: Optional[str] = Query(None, description="姓名筛选")
):
    """用户列表查询"""
```

**规范要求**：
- 必须使用`Query()`显式声明
- 提供默认值和验证规则
- 添加描述信息便于文档生成

### 3. 请求体参数（Body Parameters）

#### 3.1 Pydantic模型（推荐）

**适用场景**：复杂数据结构、创建/更新操作
```python
class UserCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    age: Optional[int] = Field(None, ge=0, le=150)

@app.post("/users")
async def create_user(user_data: UserCreateRequest):
    """创建新用户"""
```

#### 3.2 单参数Body

**适用场景**：单个简单参数
```python
@app.post("/exercise/checkin")
async def checkin_exercise(exercise_type: Optional[str] = Body(None)):
    """锻炼打卡"""
```

**规范要求**：
- 优先使用Pydantic模型
- 单个参数必须使用`Body()`显式声明
- 避免混合使用查询参数和Body参数

### 4. 表单参数（Form Data）

**适用场景**：文件上传、传统表单提交
```python
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None)
):
    """文件上传"""
```

## 📝 设计原则

### 1. 一致性原则

**禁止**混合使用不同参数类型：
```python
# ❌ 错误示例：混合参数类型
@app.post("/api/endpoint")
async def bad_example(
    path_param: str,           # 路径参数
    query_param: str = None,   # 查询参数
    body_data: dict = Body(...) # Body参数
):
    pass

# ✅ 正确示例：统一参数类型
@app.post("/api/endpoint/{path_param}")
async def good_example(
    path_param: str,
    data: RequestModel  # 统一使用Pydantic模型
):
    pass
```

### 2. 类型安全原则

所有参数必须提供类型提示和验证：
```python
# ✅ 推荐：完整类型安全
class ExerciseRequest(BaseModel):
    exercise_type: str = Field(..., min_length=1)
    duration: int = Field(..., ge=1, le=1440)
    calories: Optional[float] = Field(None, ge=0)

# ❌ 避免：类型不安全
@app.post("/exercise")
async def unsafe_example(data: dict):
    pass
```

### 3. 文档化原则

所有API必须生成清晰的文档：
```python
@app.post("/users", 
    summary="创建用户",
    description="创建新用户账户",
    response_model=UserResponse
)
async def create_user(user_data: UserCreateRequest):
    """
    创建新用户
    
    - **user_data**: 用户创建信息
    - **返回**: 创建成功的用户信息
    """
```

## 🔍 代码审查清单

### 新增API审查要点

1. **参数绑定方式检查**
   - [ ] 是否使用了正确的参数类型（Path/Query/Body/Form）
   - [ ] 是否避免了混合参数类型
   - [ ] 复杂数据结构是否使用Pydantic模型

2. **类型安全检查**
   - [ ] 所有参数都有类型提示
   - [ ] 提供了合理的验证规则
   - [ ] 可选参数有默认值

3. **文档完整性检查**
   - [ ] API有清晰的summary和description
   - [ ] 参数有描述信息
   - [ ] 响应模型定义正确

### 修改API审查要点

1. **向后兼容性**
   - [ ] 参数修改是否影响现有客户端
   - [ ] 是否提供了适当的弃用周期
   - [ ] 文档是否同步更新

## 🧪 测试规范

### 单元测试模板

```python
import pytest
from fastapi.testclient import TestClient

class TestExerciseAPI:
    
    def test_checkin_exercise_with_valid_data(self, client: TestClient):
        """测试有效的锻炼打卡数据"""
        data = {"exercise_type": "dance"}
        response = client.post("/api/exercise/checkin", json=data)
        assert response.status_code == 200
        assert response.json()["success"] is True
    
    def test_checkin_exercise_with_invalid_parameter(self, client: TestClient):
        """测试参数绑定错误场景"""
        # 错误：使用查询参数而非JSON体
        response = client.post("/api/exercise/checkin?exercise_type=dance")
        # 应该正确处理或返回明确错误
        assert response.status_code in [200, 400]
    
    def test_api_contract_consistency(self):
        """测试API契约一致性"""
        # 验证前端请求格式与后端期望一致
        frontend_format = {"exercise_type": "dance"}  # JSON体
        backend_expectation = "Body parameter"  # 后端期望Body参数
        # 这里应该有断言验证两者一致
```

### 集成测试要点

```python
def test_full_parameter_flow():
    """全链路参数传递测试"""
    # 1. 前端构造请求
    frontend_request = prepare_frontend_request()
    
    # 2. 网络传输验证
    network_payload = serialize_request(frontend_request)
    assert network_payload["Content-Type"] == "application/json"
    
    # 3. 后端参数绑定验证
    backend_params = parse_backend_parameters(network_payload)
    assert backend_params.exercise_type == "dance"
    
    # 4. 数据库持久化验证
    db_record = save_to_database(backend_params)
    assert db_record.exercise_type == "dance"
```

## 🚨 常见错误及修复

### 错误1：参数绑定方式错误

**症状**：前端发送JSON体，后端期望查询参数

**修复**：
```python
# 错误代码
async def checkin_exercise(exercise_type: Optional[str] = None)

# 修复代码
async def checkin_exercise(exercise_type: Optional[str] = Body(None))
# 或更好的方式
async def checkin_exercise(data: CheckinRequest)  # 使用Pydantic模型
```

### 错误2：混合参数类型

**症状**：同一个端点使用多种参数传递方式

**修复**：统一使用Pydantic模型

### 错误3：缺少参数验证

**症状**：参数没有类型验证，容易导致运行时错误

**修复**：添加完整的验证规则

## 📊 监控和告警

### 参数绑定错误监控

建议在API网关或中间件中添加监控：
- 参数解析失败率
- 请求体格式错误统计
- 参数验证失败详情

### 健康检查

定期运行API契约测试：
```bash
# 自动化API测试
pytest tests/api_contract/ -v

# 生成API文档并验证
python -m scripts.validate_api_docs
```

## 🔄 持续改进

### 版本管理

API变更必须遵循语义化版本：
- **主要版本**：不兼容的API变更
- **次要版本**：向后兼容的功能新增
- **修订版本**：向后兼容的问题修复

### 反馈机制

建立API使用反馈渠道：
- 客户端错误报告
- 使用统计和分析
- 定期API评审会议

## 📋 快速参考

### 参数绑定速查表

| 参数类型 | 声明方式 | 适用场景 | 示例 |
|---------|---------|---------|------|
| 路径参数 | `param: type` | 资源标识 | `/users/{id}` |
| 查询参数 | `param: type = Query(...)` | 筛选条件 | `?page=1&size=20` |
| Body参数 | `data: Model` | 复杂数据 | JSON请求体 |
| 单Body参数 | `param: type = Body(...)` | 简单数据 | 单个JSON字段 |
| 表单参数 | `param: type = Form(...)` | 文件上传 | multipart/form-data |

### 紧急修复流程

遇到参数绑定问题时：
1. **确认问题**：浏览器Network面板检查请求格式
2. **定位原因**：对比前后端参数绑定方式
3. **快速修复**：使用`Body()`或Pydantic模型统一参数传递
4. **验证修复**：全链路测试确保问题解决
5. **更新文档**：同步API文档和规范

---

*制定时间：2026年2月10日*  
*基于：锻炼打卡功能API参数绑定调试经验*  
*版本：v1.0*