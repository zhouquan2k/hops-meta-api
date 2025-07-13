#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据库连接配置模块
用于连接存储Oracle表结构信息的MySQL数据库
"""

import pymysql
from contextlib import contextmanager

# 数据库连接配置 - 与主程序保持一致
DB_CONFIG = {
    'host': 'host.docker.internal',
    'port': 3306,
    'user': 'root',
    'password': 'root',
    'database': 'his-metadata',
    'charset': 'utf8mb4'
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