#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
API服务启动脚本
解决相对导入问题的启动入口
"""

import os
import sys

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 导入Flask应用
from api.app import create_app


if __name__ == '__main__':
    print("启动Oracle表结构查询API服务...")
    print(f"项目根目录: {project_root}")
    print("API服务将在 http://0.0.0.0:5050 启动")
    
    # 创建应用实例
    app = create_app()
    
    # 启动服务
    app.run(host='0.0.0.0', port=5050, debug=True) 