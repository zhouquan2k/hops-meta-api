启动 
python api/run.py


# Oracle表结构查询API - 快速启动

## 重构后的项目结构

```
api/
├── app.py              # Flask应用定义（使用应用工厂模式）
├── run.py              # 启动脚本（解决导入问题）
├── database.py         # 数据库连接配置
├── models.py           # 数据模型和查询逻辑
├── requirements.txt    # API依赖包
└── __init__.py         # 包初始化文件

temp/
├── api_test.py         # API测试脚本
├── api_example.md      # 详细使用示例
└── README_API.md       # 本文件
```

## 代码重构说明

### 🔧 解决的问题
- **消除代码重复**：之前`app.py`和`run.py`有重复的路由定义
- **改进代码组织**：使用Flask应用工厂模式，更好的模块化

### 📁 重构后的文件职责

**`api/app.py`** - Flask应用定义
- `create_app()` - 应用工厂函数
- `register_routes()` - 注册所有API路由
- `register_error_handlers()` - 注册错误处理器
- 支持直接运行：`python api/app.py`

**`api/run.py`** - 启动脚本
- 解决Python路径和模块导入问题
- 调用`create_app()`创建应用实例
- 推荐的启动方式：`python api/run.py`

## 快速启动

### 1. 安装依赖
```bash
# 安装API依赖
pip install -r api/requirements.txt

# 如果需要测试脚本，还需要安装requests
pip install requests
```

### 2. 启动API服务

**推荐方式（解决模块导入问题）：**
```bash
python api/run.py
```

**备用方式：**
```bash
python api/app.py
```

### 3. 验证服务

服务启动后会在 `http://localhost:5000` 运行：

```bash
# 健康检查
curl http://localhost:5000/health

# 搜索表
curl "http://localhost:5000/api/tables/search?table_name=USER"

# 查询表列信息
curl http://localhost:5000/api/tables/USER_INFO/columns
```

### 4. 运行测试

```bash
# 运行自动化测试
python temp/api_test.py

# 查看curl命令示例
python temp/api_test.py --curl
```

## 主要接口

### GET /api/tables/{table_name}/columns
**核心接口**：根据表名查询列的详细信息

**参数：**
- `table_name`（路径参数）：表名，支持模糊匹配
- `owner`（查询参数，可选）：表所有者

**返回：**
- 表基本信息（所有者、表名、注释、行数等）
- 列详细信息（列名、数据类型、是否可空、默认值、注释等）
- 主键信息
- 外键信息  
- 索引信息

## 注意事项

1. **数据库配置**：确保MySQL数据库 `his-metadata` 中已有Oracle表结构数据
2. **连接配置**：如需修改数据库连接，请编辑 `api/database.py`
3. **模糊匹配**：表名支持模糊匹配，返回第一个匹配结果
4. **精确查询**：多个同名表时建议使用 `owner` 参数

## 故障排除

### 导入错误
使用 `python api/run.py` 启动，它会自动处理Python路径问题。

### 数据库连接失败
检查 `api/database.py` 中的数据库配置：
- host: host.docker.internal
- port: 3306  
- user: root
- password: root
- database: his-metadata

### 表未找到
确保已使用 `oracle_db_analyzer.py` 工具分析过Oracle数据库并将结果存储到MySQL中。

## 扩展说明

详细的API接口说明和示例请参考 `temp/api_example.md` 文件。

## 重构优势

✅ **消除代码重复** - 不再有重复的路由定义  
✅ **更好的模块化** - 使用Flask应用工厂模式  
✅ **灵活的部署** - 支持多种启动方式  
✅ **易于测试** - 应用创建和配置分离 