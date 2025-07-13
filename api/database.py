#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据库连接配置模块
用于连接存储Oracle表结构信息的MySQL数据库
"""

import os
import pymysql
from contextlib import contextmanager

# 数据库连接配置 - 支持环境变量覆盖默认值
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'host.docker.internal'),
    'port': int(os.environ.get('DB_PORT', '3306')),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'root'),
    'database': os.environ.get('DB_DATABASE', 'his-metadata'),
    'charset': os.environ.get('DB_CHARSET', 'utf8mb4')
}


@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器"""
    connection = None
    try:
        connection = pymysql.connect(**DB_CONFIG)
        yield connection
    except Exception as e:
        print(f"数据库连接错误: {e}")
        raise
    finally:
        if connection:
            connection.close()


def test_connection():
    """测试数据库连接"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result is not None
    except Exception as e:
        print(f"数据库连接测试失败: {e}")
        return False


def init_database():
    """初始化数据库连接，启动时自动执行"""
    print("正在初始化数据库连接...")
    print(f"数据库配置: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result:
                    print("数据库连接成功!")
                    return True
                else:
                    raise Exception("数据库连接测试失败")
    except Exception as e:
        error_msg = f"数据库连接失败: {e}"
        print(error_msg)
        raise RuntimeError(error_msg) from e


# 启动时自动连接数据库
if __name__ != "__main__":
    # 只有在模块被导入时才自动连接，直接运行时不自动连接
    init_database() 