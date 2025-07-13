# Oracle数据库字典分析工具

这是一个用于分析Oracle数据库表结构的工具，它通过读取数据字典，提取表结构和字段信息，分析字段含义，并生成易于阅读的Markdown文档。

## 功能特点

- 连接到Oracle数据库并提取数据字典信息
- 分析表结构、列、主键、外键和索引
- 自动猜测字段含义
- 生成包含完整表结构的Markdown文档
- 特别优化支持Oracle 11g数据库

## 开发环境

本项目使用VS Code和devcontainer开发，确保使用x86_64的Oracle客户端以兼容Oracle 11g。

### 环境要求

- Docker
- Visual Studio Code
- VS Code的Remote Development插件

### 快速开始

1. 克隆项目：
   ```
   git clone https://github.com/yourusername/oracle-db-analyzer.git
   cd oracle-db-analyzer
   ```

2. 使用VS Code打开项目，并在Remote Container中打开

3. VS Code会自动构建开发容器（这可能需要几分钟时间）

4. 容器启动后，可以直接运行分析脚本

## 使用方法

1. 编辑`oracle_db_analyzer.py`中的数据库连接信息：

```python
# 数据库连接信息 - 请修改为实际的连接信息
username = "your_username"
password = "your_password"
dsn = "your_dsn"  # 如 "localhost:1521/ORCL"
```

2. 运行脚本：

```bash
python oracle_db_analyzer.py
```

3. 查看生成的`database_readme.md`文件，其中包含完整的数据库表结构文档

## Oracle 11g 支持说明

该项目专门配置了兼容Oracle 11g的环境：

- 使用Oracle Instant Client 19.3版本（兼容Oracle 11g）
- 使用cx_Oracle 7.3.0版本（稳定支持旧版Oracle）
- 强制使用x86_64架构容器确保兼容性
- 预配置了所有必要的环境变量

## 输出示例

生成的文档包括以下内容：

- 表列表和描述
- 每个表的详细结构
- 列信息（数据类型、是否可空、默认值、注释）
- 字段含义猜测
- 主键、外键和索引信息

## 注意事项

- 本工具需要对Oracle数据库有适当的访问权限
- 为获得最佳结果，请确保您的Oracle用户有权访问ALL_TABLES, ALL_TAB_COMMENTS等视图
- 生成的文档大小取决于数据库模式的大小和复杂性

## 开发说明

本项目使用cx_Oracle连接Oracle数据库。容器环境中已经配置好Oracle Instant Client，无需额外安装。

如果您遇到Oracle客户端相关的错误，请检查容器中的Oracle环境配置。

## 自定义

如果需要针对特定的表或模式进行分析，可以修改 `get_all_tables` 函数中的SQL查询语句中的WHERE条件。

## 许可证

MIT 

## ARM架构兼容性问题说明

### 问题描述

在ARM架构系统（如Apple M1/M2/M3芯片、树莓派等）上运行需要连接Oracle数据库的Python应用程序时，会遇到以下错误：

```
DPI-1047: Cannot locate a 64-bit Oracle Client library: "libclntsh.so: cannot open shared object file: No such file or directory".
```

这是因为Oracle官方不直接提供ARM架构的Oracle Instant Client，标准的cx_Oracle库需要这些本地库文件才能正常工作。

### 解决方案

针对ARM架构设备连接Oracle数据库，有以下几种解决方案：

#### 1. 使用oracledb的Thin模式（推荐）

oracledb库提供"Thin模式"，可以不依赖Oracle客户端库直接连接Oracle数据库：

```python
import oracledb

connection = oracledb.connect(
    user="your_username",
    password="your_password",
    dsn="hostname:port/service_name",
    config_dir=None,  # 禁用配置目录
    thin=True  # 使用Thin模式
)
```

这种方式完全兼容ARM架构，无需任何原生库。

#### 2. 使用Docker x86_64容器

如果必须使用cx_Oracle，可以在Docker中创建x86_64架构的容器：

```bash
docker run --platform linux/amd64 -it --name oracle-app python:3.11 bash
```

然后在容器内安装cx_Oracle和Oracle Instant Client。

#### 3. 使用代理层

设置一个运行在x86_64架构服务器上的API代理层，由ARM架构设备通过HTTP/REST接口调用。

## 文件说明

- `oracle_db_analyzer.py` - 原始版本，使用cx_Oracle（仅在x86_64架构上可用）
- `oracle_db_analyzer_arm.py` - 修改版，使用oracledb的Thin模式（ARM兼容）
- `connect_oracle_alternative.py` - ARM架构连接方案说明
- `oracle_thin_example.py` - 使用Thin模式的简单示例
- `fix_oracle_arm.sh` - ARM架构解决方案安装脚本

## 安装与使用

1. 安装ARM兼容的库：
```bash
pip uninstall -y cx_Oracle
pip install oracledb pandas markdown
```

2. 修改连接信息：
编辑`oracle_db_analyzer_arm.py`文件，设置正确的数据库连接信息。

3. 运行程序：
```bash
python oracle_db_analyzer_arm.py
```

## 注意事项

- Thin模式支持大多数Oracle功能，但某些高级功能可能不可用
- 确保网络可以直接访问Oracle数据库
- 如果连接Oracle 11g，请确保使用兼容的oracledb版本 