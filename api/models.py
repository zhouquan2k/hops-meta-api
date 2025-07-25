#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据模型模块
定义查询Oracle表结构信息的数据访问方法
"""

import pymysql
from database import get_db_connection


def filter_none_values(data):
    """
    递归过滤字典和列表中的None值
    
    Args:
        data: 要过滤的数据（字典、列表或基本类型）
    
    Returns:
        过滤后的数据，None值被移除
    """
    if isinstance(data, dict):
        return {k: filter_none_values(v) for k, v in data.items() if v is not None}
    elif isinstance(data, list):
        return [filter_none_values(item) for item in data if item is not None]
    else:
        return data


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
                SELECT t.id, t.owner, t.table_name, t.comment, t.rows_count, t.last_analyzed, t.id_column, t.name_column, t.code_column
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
                SELECT c.column_name, c.data_type, c.nullable, c.default_value, c.comment, 
                       c.column_id, c.column_type, c.column_info,
                       ref_table.id_column as ref_id_column,
                       ref_table.name_column as ref_name_column,
                       ref_table.code_column as ref_code_column
                FROM oracle_columns c
                LEFT JOIN oracle_tables ref_table ON (c.column_type = 'FK' AND c.column_info = ref_table.table_name)
                WHERE c.table_id = %s
                ORDER BY c.column_id
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
                

                
                # 构建返回结果
                result = {
                    'table_info': {
                        'owner': table_info['owner'],
                        'table_name': table_info['table_name'],
                        'comment': table_info['comment'] or '',
                        'rows_count': table_info['rows_count'],
                        'last_analyzed': table_info['last_analyzed'].isoformat() if table_info['last_analyzed'] else None,
                        'id_column': table_info['id_column'],
                        'name_column': table_info['name_column'],
                        'code_column': table_info['code_column']
                    },
                    'columns': columns,
                    'primary_keys': primary_keys,
                    'foreign_keys': foreign_keys,
                    'indices': indices
                }
                
                # 过滤None值以节省带宽
                return filter_none_values(result)
                
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
                SELECT owner, table_name, comment, rows_count, id_column, name_column, code_column
                FROM oracle_tables
                {where_clause}
                ORDER BY owner, table_name
                LIMIT 100
                """
                
                cursor.execute(query, params)
                tables = cursor.fetchall()
                
                # 过滤None值以节省带宽
                return [filter_none_values(table) for table in tables]
                
    except Exception as e:
        print(f"搜索表错误: {e}")
        raise


def update_table_info(table_name, owner=None, table_data=None):
    """
    更新表的基本信息
    
    Args:
        table_name: 表名
        owner: 表所有者（可选）
        table_data: 要更新的表信息字典，包含comment等字段
    
    Returns:
        dict: 更新结果
    """
    if not table_data:
        result = {'success': False, 'error': '没有提供要更新的数据'}
        return filter_none_values(result)
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 构建查询条件，查找表是否存在
                table_where = "table_name LIKE %s"
                params = [f"%{table_name}%"]
                
                if owner:
                    table_where += " AND owner = %s"
                    params.append(owner)
                
                # 查询表是否存在
                check_query = f"""
                SELECT id, owner, table_name 
                FROM oracle_tables 
                WHERE {table_where}
                """
                
                cursor.execute(check_query, params)
                table_record = cursor.fetchone()
                
                if not table_record:
                    result = {
                        'success': False, 
                        'error': f'未找到表 {owner + "." + table_name if owner else table_name}'
                    }
                    return filter_none_values(result)
                
                # 构建更新语句
                update_fields = []
                update_params = []
                
                if 'comment' in table_data:
                    update_fields.append("comment = %s")
                    update_params.append(table_data['comment'])
                
                if not update_fields:
                    result = {'success': False, 'error': '没有提供有效的更新字段'}
                    return filter_none_values(result)
                
                # 执行更新
                update_query = f"""
                UPDATE oracle_tables 
                SET {', '.join(update_fields)}
                WHERE id = %s
                """
                update_params.append(table_record['id'])
                
                cursor.execute(update_query, update_params)
                conn.commit()
                
                if cursor.rowcount > 0:
                    result = {
                        'success': True,
                        'message': f'成功更新表 {table_record["owner"]}.{table_record["table_name"]}',
                        'updated_fields': list(table_data.keys())
                    }
                    return filter_none_values(result)
                else:
                    result = {'success': False, 'error': '更新失败，没有行被修改'}
                    return filter_none_values(result)
                
    except Exception as e:
        print(f"更新表信息错误: {e}")
        raise


def update_table_columns(table_name, owner=None, columns_data=None):
    """
    批量更新表的列信息
    
    Args:
        table_name: 表名
        owner: 表所有者（可选）
        columns_data: 要更新的列信息列表，每个元素包含column_name和要更新的字段
    
    Returns:
        dict: 更新结果
    """
    if not columns_data or not isinstance(columns_data, list):
        result = {'success': False, 'error': '没有提供有效的列更新数据'}
        return filter_none_values(result)
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 构建查询条件，查找表是否存在
                table_where = "table_name LIKE %s"
                params = [f"%{table_name}%"]
                
                if owner:
                    table_where += " AND owner = %s"
                    params.append(owner)
                
                # 查询表是否存在
                check_query = f"""
                SELECT id, owner, table_name 
                FROM oracle_tables 
                WHERE {table_where}
                """
                
                cursor.execute(check_query, params)
                table_record = cursor.fetchone()
                
                if not table_record:
                    result = {
                        'success': False, 
                        'error': f'未找到表 {owner + "." + table_name if owner else table_name}'
                    }
                    return filter_none_values(result)
                
                table_id = table_record['id']
                updated_columns = []
                failed_columns = []
                
                # 开始事务
                conn.begin()
                
                try:
                    # 逐个更新列
                    for column_update in columns_data:
                        if not isinstance(column_update, dict) or 'column_name' not in column_update:
                            failed_columns.append({
                                'column': column_update.get('column_name', '未知'),
                                'error': '无效的列更新数据格式'
                            })
                            continue
                        
                        column_name = column_update['column_name']
                        
                        # 检查列是否存在
                        column_check_query = """
                        SELECT id FROM oracle_columns 
                        WHERE table_id = %s AND column_name = %s
                        """
                        cursor.execute(column_check_query, [table_id, column_name])
                        column_record = cursor.fetchone()
                        
                        if not column_record:
                            failed_columns.append({
                                'column': column_name,
                                'error': '列不存在'
                            })
                            continue
                        
                        # 构建列更新语句
                        update_fields = []
                        update_params = []
                        
                        if 'comment' in column_update:
                            update_fields.append("comment = %s")
                            update_params.append(column_update['comment'])
                        
                        if 'nullable' in column_update:
                            update_fields.append("nullable = %s")
                            update_params.append(column_update['nullable'])
                        
                        if 'default_value' in column_update:
                            update_fields.append("default_value = %s")
                            update_params.append(column_update['default_value'])
                        
                        if 'column_type' in column_update:
                            update_fields.append("column_type = %s")
                            update_params.append(column_update['column_type'])
                        
                        if 'column_info' in column_update:
                            update_fields.append("column_info = %s")
                            update_params.append(column_update['column_info'])
                        
                        if not update_fields:
                            failed_columns.append({
                                'column': column_name,
                                'error': '没有提供有效的更新字段'
                            })
                            continue
                        
                        # 执行列更新
                        column_update_query = f"""
                        UPDATE oracle_columns 
                        SET {', '.join(update_fields)}
                        WHERE id = %s
                        """
                        update_params.append(column_record['id'])
                        
                        cursor.execute(column_update_query, update_params)
                        
                        if cursor.rowcount > 0:
                            updated_columns.append({
                                'column': column_name,
                                'updated_fields': [field for field in column_update.keys() if field != 'column_name']
                            })
                        else:
                            failed_columns.append({
                                'column': column_name,
                                'error': '更新失败，没有行被修改'
                            })
                    
                    # 提交事务
                    conn.commit()
                    
                    result = {
                        'success': True,
                        'message': f'批量更新表 {table_record["owner"]}.{table_record["table_name"]} 的列信息完成',
                        'updated_columns': updated_columns,
                        'failed_columns': failed_columns,
                        'summary': {
                            'total': len(columns_data),
                            'success': len(updated_columns),
                            'failed': len(failed_columns)
                        }
                    }
                    return filter_none_values(result)
                    
                except Exception as e:
                    # 回滚事务
                    conn.rollback()
                    raise e
                
    except Exception as e:
        print(f"批量更新列信息错误: {e}")
        raise


def get_id_mapping_by_name(id_name):
    """
    根据ID名查询映射信息
    
    Args:
        id_name: ID字段名
    
    Returns:
        list: 包含映射信息的字典列表，如果只有一个匹配则返回单个字典
    """
    if not id_name:
        return None
        
    try:
        with get_db_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 查询映射信息
                query = """
                SELECT id_name, schema_name, table_name, name_column
                FROM oracle_id_mapping
                WHERE id_name = %s
                ORDER BY schema_name, table_name
                """
                
                cursor.execute(query, [id_name])
                mappings = cursor.fetchall()
                
                if not mappings:
                    return None
                
                # 过滤None值以节省带宽
                filtered_mappings = [filter_none_values(mapping) for mapping in mappings]
                
                # 如果只有一个匹配，返回单个字典
                if len(filtered_mappings) == 1:
                    return filtered_mappings[0]
                
                # 如果有多个匹配，返回列表
                return filtered_mappings
                
    except Exception as e:
        print(f"查询ID映射时出错: {e}")
        return None


 