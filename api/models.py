#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据模型模块
定义查询Oracle表结构信息的数据访问方法
"""

import pymysql
from .database import get_db_connection


def get_table_columns_info(table_name, owner=None):
    """
    获取指定表的列信息
    
    Args:
        table_name: 表名（支持模糊匹配）
        owner: 表所有者（可选）
    
    Returns:
        dict: 包含表信息和列详情的字典
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 构建查询条件
                table_where = "t.table_name LIKE %s"
                params = [f"%{table_name}%"]
                
                if owner:
                    table_where += " AND t.owner = %s"
                    params.append(owner)
                
                # 查询表基本信息
                table_query = f"""
                SELECT t.id, t.owner, t.table_name, t.comment, t.rows_count, t.last_analyzed
                FROM oracle_tables t
                WHERE {table_where}
                ORDER BY t.owner, t.table_name
                """
                
                cursor.execute(table_query, params)
                tables = cursor.fetchall()
                
                if not tables:
                    return None
                
                # 如果找到多个表，返回第一个匹配的表
                table_info = tables[0]
                table_id = table_info['id']
                
                # 查询列信息
                columns_query = """
                SELECT column_name, data_type, nullable, default_value, comment, column_id
                FROM oracle_columns
                WHERE table_id = %s
                ORDER BY column_id
                """
                
                cursor.execute(columns_query, [table_id])
                columns = cursor.fetchall()
                
                # 查询主键信息
                pk_query = """
                SELECT column_name
                FROM oracle_primary_keys
                WHERE table_id = %s
                """
                
                cursor.execute(pk_query, [table_id])
                primary_keys = [row['column_name'] for row in cursor.fetchall()]
                
                # 查询外键信息
                fk_query = """
                SELECT constraint_name, column_name, referenced_table, referenced_column
                FROM oracle_foreign_keys
                WHERE table_id = %s
                """
                
                cursor.execute(fk_query, [table_id])
                foreign_keys = cursor.fetchall()
                
                # 查询索引信息
                idx_query = """
                SELECT index_name, index_type, uniqueness, column_name, status
                FROM oracle_indices
                WHERE table_id = %s
                """
                
                cursor.execute(idx_query, [table_id])
                indices = cursor.fetchall()
                
                # 为每个列添加主键标记
                for column in columns:
                    column['is_primary_key'] = column['column_name'] in primary_keys
                
                # 构建返回结果
                result = {
                    'table_info': {
                        'owner': table_info['owner'],
                        'table_name': table_info['table_name'],
                        'comment': table_info['comment'] or '',
                        'rows_count': table_info['rows_count'],
                        'last_analyzed': table_info['last_analyzed'].isoformat() if table_info['last_analyzed'] else None
                    },
                    'columns': columns,
                    'primary_keys': primary_keys,
                    'foreign_keys': foreign_keys,
                    'indices': indices
                }
                
                return result
                
    except Exception as e:
        print(f"查询表列信息错误: {e}")
        raise


def search_tables(keyword=None, owner=None):
    """
    搜索表名和注释
    
    Args:
        keyword: 搜索关键词（可选）- 匹配表名或注释
        owner: 表所有者（可选）
    
    Returns:
        list: 表列表
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 构建查询条件
                where_conditions = []
                params = []
                
                if keyword:
                    # 搜索表名或注释
                    where_conditions.append("(table_name LIKE %s OR comment LIKE %s)")
                    params.extend([f"%{keyword}%", f"%{keyword}%"])
                
                if owner:
                    where_conditions.append("owner = %s")
                    params.append(owner)
                
                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)
                
                query = f"""
                SELECT owner, table_name, comment, rows_count
                FROM oracle_tables
                {where_clause}
                ORDER BY owner, table_name
                LIMIT 100
                """
                
                cursor.execute(query, params)
                return cursor.fetchall()
                
    except Exception as e:
        print(f"搜索表错误: {e}")
        raise


 