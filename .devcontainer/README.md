python oracle_db_analyzer.py --owner IIH --output my_db_doc.md --concurrency 2

# VS Code 开发容器使用指南

本项目配置了VS Code开发容器环境，提供完整的Python开发环境，特别适用于Oracle数据库分析工具的开发和运行。

## 前置条件

1. 安装 [VS Code](https://code.visualstudio.com/)
2. 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop)
3. 在VS Code中安装 [Dev Containers扩展](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

## 使用方法

1. 在VS Code中打开本项目
2. 点击左下角的绿色图标，或按下 `F1` 键，输入 `Remote-Containers: Reopen in Container`
3. VS Code将自动构建容器并在容器内打开项目，首次构建可能需要几分钟时间

## 环境特性

- Python 3.11 基础环境
- 已预安装常用开发工具 (git, curl, vim)
- 已配置Python开发工具 (ipython, pytest, black, flake8, mypy)
- 已集成Oracle即时客户端 (19.3)
- 配置了VS Code智能补全、代码格式化和Lint工具

## 扩展和设置

开发容器自动安装以下VS Code扩展：

- Python扩展和Pylance (代码补全和智能提示)
- Jupyter支持
- Docker支持
- 自动文档字符串生成
- MyPy类型检查

## 注意事项

使用cx_Oracle连接Oracle数据库需要Oracle客户端库，这些已在容器中配置好。如需连接实际数据库，请创建`.env`文件并填入正确的连接信息。

## 测试Oracle连接

容器内已提供了一个测试脚本，可以通过以下命令验证Oracle客户端是否安装正确：

```bash
check_oracle.sh
``` 