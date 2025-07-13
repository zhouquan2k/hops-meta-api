#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Oracle数据库字典分析工具
用于从Oracle数据库字典中提取表结构和字段信息，分析字段含义，并生成markdown文档
同时支持将分析结果保存到MySQL数据库
"""

import os
# 设置Oracle客户端库路径
oracle_client_path = os.environ.get('ORACLE_HOME', '/opt/oracle/instantclient_19_3')
os.environ['LD_LIBRARY_PATH'] = f"{oracle_client_path}:{os.environ.get('LD_LIBRARY_PATH', '')}"

import cx_Oracle  # type: ignore
import pymysql  # type: ignore
import pandas as pd  # type: ignore
import markdown  # type: ignore
from datetime import datetime
import time
import argparse
import sys
import io
import concurrent.futures
import threading
import queue

# 添加一个计时装饰器
def timer(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        # 只为主要函数输出执行时间
        if func.__name__ == "analyze_tables_concurrent":
            print(f"{func.__name__} 执行耗时: {end_time - start_time:.2f} 秒")
        return result
    return wrapper


def get_all_tables(cursor, owner_filter=None, table_filter=None):
    """查询所有表，支持根据所有者和表名过滤"""
    query = """
    SELECT ALL_TAB_COMMENTS.OWNER, ALL_TAB_COMMENTS.TABLE_NAME, ALL_TABLES.TABLESPACE_NAME, 
           ALL_TABLES.STATUS, ALL_TABLES.NUM_ROWS, 
           ALL_TABLES.LAST_ANALYZED, ALL_TAB_COMMENTS.COMMENTS
    FROM ALL_TAB_COMMENTS 
    JOIN ALL_TABLES ON ALL_TAB_COMMENTS.OWNER = ALL_TABLES.OWNER 
                    AND ALL_TAB_COMMENTS.TABLE_NAME = ALL_TABLES.TABLE_NAME
    WHERE ALL_TAB_COMMENTS.OWNER NOT IN ('SYS', 'SYSTEM')
    """
    
    params = {}
    if owner_filter:
        query += " AND ALL_TAB_COMMENTS.OWNER = :owner"
        params['owner'] = owner_filter
    
    if table_filter:
        query += " AND ALL_TAB_COMMENTS.TABLE_NAME LIKE :table_name"
        params['table_name'] = f"%{table_filter}%"
    
    query += " ORDER BY ALL_TAB_COMMENTS.OWNER, ALL_TAB_COMMENTS.TABLE_NAME"
    
    cursor.execute(query, params)
    return cursor.fetchall()


def get_table_columns(cursor, owner, table_name):
    """查询表的列信息"""
    query = """
    SELECT ALL_TAB_COLUMNS.COLUMN_NAME, ALL_TAB_COLUMNS.DATA_TYPE, ALL_TAB_COLUMNS.DATA_LENGTH, 
           ALL_TAB_COLUMNS.NULLABLE, ALL_TAB_COLUMNS.DATA_DEFAULT, ALL_COL_COMMENTS.COMMENTS, 
           ALL_TAB_COLUMNS.COLUMN_ID, ALL_TAB_COLUMNS.DATA_PRECISION, ALL_TAB_COLUMNS.DATA_SCALE
    FROM ALL_COL_COMMENTS 
    JOIN ALL_TAB_COLUMNS ON ALL_COL_COMMENTS.OWNER = ALL_TAB_COLUMNS.OWNER 
                        AND ALL_COL_COMMENTS.TABLE_NAME = ALL_TAB_COLUMNS.TABLE_NAME 
                        AND ALL_COL_COMMENTS.COLUMN_NAME = ALL_TAB_COLUMNS.COLUMN_NAME
    WHERE ALL_COL_COMMENTS.OWNER = :owner AND ALL_COL_COMMENTS.TABLE_NAME = :table_name
    ORDER BY ALL_TAB_COLUMNS.COLUMN_ID
    """
    cursor.execute(query, {'owner': owner, 'table_name': table_name})
    return cursor.fetchall()


def get_primary_keys(cursor, owner, table_name):
    """获取主键信息"""
    query = """
    SELECT ACC.COLUMN_NAME
    FROM ALL_CONSTRAINTS AC
    JOIN ALL_CONS_COLUMNS ACC ON AC.OWNER = ACC.OWNER AND AC.CONSTRAINT_NAME = ACC.CONSTRAINT_NAME
    WHERE AC.CONSTRAINT_TYPE = 'P'
      AND AC.TABLE_NAME = :table_name
      AND AC.OWNER = :owner
    ORDER BY ACC.POSITION
    """
    cursor.execute(query, {'owner': owner, 'table_name': table_name})
    return [row[0] for row in cursor.fetchall()]


def get_foreign_keys(cursor, owner, table_name):
    """获取外键信息"""
    query = """
    SELECT AC.CONSTRAINT_NAME, 
           ACC.COLUMN_NAME,
           AC_REF.TABLE_NAME AS REFERENCED_TABLE,
           ACC_REF.COLUMN_NAME AS REFERENCED_COLUMN
    FROM ALL_CONSTRAINTS AC
    JOIN ALL_CONS_COLUMNS ACC ON AC.OWNER = ACC.OWNER AND AC.CONSTRAINT_NAME = ACC.CONSTRAINT_NAME
    JOIN ALL_CONSTRAINTS AC_REF ON AC.R_OWNER = AC_REF.OWNER AND AC.R_CONSTRAINT_NAME = AC_REF.CONSTRAINT_NAME
    JOIN ALL_CONS_COLUMNS ACC_REF ON AC_REF.OWNER = ACC_REF.OWNER AND AC_REF.CONSTRAINT_NAME = ACC_REF.CONSTRAINT_NAME
    WHERE AC.CONSTRAINT_TYPE = 'R'
      AND AC.TABLE_NAME = :table_name
      AND AC.OWNER = :owner
      AND ACC.POSITION = ACC_REF.POSITION
    ORDER BY AC.CONSTRAINT_NAME, ACC.POSITION
    """
    cursor.execute(query, {'owner': owner, 'table_name': table_name})
    return cursor.fetchall()


def get_indices(cursor, owner, table_name):
    """获取索引信息"""
    query = """
    SELECT AI.INDEX_NAME, AI.INDEX_TYPE, AI.UNIQUENESS, AIC.COLUMN_NAME, AI.STATUS
    FROM ALL_INDEXES AI
    JOIN ALL_IND_COLUMNS AIC ON AI.OWNER = AIC.INDEX_OWNER AND AI.INDEX_NAME = AIC.INDEX_NAME
    WHERE AI.TABLE_OWNER = :owner
      AND AI.TABLE_NAME = :table_name
    ORDER BY AI.INDEX_NAME, AIC.COLUMN_POSITION
    """
    cursor.execute(query, {'owner': owner, 'table_name': table_name})
    return cursor.fetchall()
    
    # 如果已有注释，直接返回
    if column_comment and column_comment != '无描述':
        return column_comment
    
    # 否则尝试根据字段名称猜测
    column_name_lower = column_name.lower()
    
    for pattern, meaning in common_patterns.items():
        if pattern in column_name_lower:
            return f"推测含义: {meaning}"
    
    # 处理常见的前缀后缀
    if column_name_lower.endswith('_id'):
        return f"推测含义: {column_name_lower[:-3]} 的唯一标识符"
    if column_name_lower.endswith('_name'):
        return f"推测含义: {column_name_lower[:-5]} 的名称"
    if column_name_lower.endswith('_code'):
        return f"推测含义: {column_name_lower[:-5]} 的编码"
    if column_name_lower.endswith('_date'):
        return f"推测含义: {column_name_lower[:-5]} 的日期"
    if column_name_lower.endswith('_time'):
        return f"推测含义: {column_name_lower[:-5]} 的时间"
    if column_name_lower.startswith('is_'):
        return f"推测含义: 是否 {column_name_lower[3:]}"
    if column_name_lower.startswith('has_'):
        return f"推测含义: 是否拥有 {column_name_lower[4:]}"
    
    return "无法推测含义"


class MarkdownWriter:
    """Markdown文档写入器，支持流式写入"""
    
    def __init__(self, filename):
        self.filename = filename
        self.file = None
        self.tables_count = 0
        self.tables_index = {}  # 存储表名到目录项的映射
        self.tables_content = {}  # 存储表名到表内容的映射
        self.lock = threading.RLock()  # 使用可重入锁保护文件操作
        self.content_lock = threading.RLock()  # 用于保护内容生成
    
    def open(self):
        """打开文件并写入头部"""
        with self.lock:
            try:
                self.file = open(self.filename, 'w', encoding='utf-8')
                self.write_header()
                return self
            except Exception as e:
                print(f"打开文件失败: {e}")
                if self.file:
                    self.file.close()
                    self.file = None
                raise
    
    def close(self):
        """关闭文件"""
        with self.lock:
            if self.file:
                try:
                    self.file.flush()
                    self.file.close()
                except Exception as e:
                    print(f"关闭文件失败: {e}")
                finally:
                    self.file = None
    
    def __enter__(self):
        """支持上下文管理器协议的进入方法"""
        return self.open()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器协议的退出方法"""
        self.close()
        return False  # 不抑制异常
    
    def write_header(self):
        """写入文档头部"""
        with self.lock:
            if not self.file:
                print("文件未打开，无法写入头部")
                return False
                
            try:
                content = "# 数据库表结构文档\n\n"
                content += f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
                content += "## 目录\n\n"
                content += "\n## 详细表结构\n\n"  # 预先添加分隔线
                
                self.file.write(content)
                self.file.flush()
                return True
            except Exception as e:
                print(f"写入文件头部失败: {e}")
                return False
    
    def ensure_file_open(self):
        """确保文件已打开"""
        with self.lock:
            if not self.file:
                try:
                    self.file = open(self.filename, 'a', encoding='utf-8')
                    return True
                except Exception as e:
                    print(f"重新打开文件失败: {e}")
                    return False
            return True
    
    def write_to_file(self, content):
        """安全地写入内容到文件"""
        with self.lock:
            if not self.ensure_file_open():
                return False
                
            try:
                self.file.write(content)
                self.file.flush()
                return True
            except Exception as e:
                print(f"写入文件失败: {e}")
                return False
    
    def write_table_index(self, owner, table_name, comment):
        """记录表索引到内存"""
        with self.content_lock:
            anchor = f"{owner.lower()}-{table_name.lower()}"
            display_comment = comment if comment and comment != "-" else "无描述"
            content = f"- [{owner}.{table_name}](#{anchor}) - {display_comment}\n"
            self.tables_index[f"{owner}.{table_name}"] = content
            self.tables_count += 1
    
    def finalize_toc(self):
        """重新生成排序后的最终文档"""
        with self.lock:
            final_filename = f"{self.filename}.final"
            
            try:
                # 创建最终文件
                with open(final_filename, 'w', encoding='utf-8') as final_file:
                    # 写入文档头部
                    content = "# 数据库表结构文档\n\n"
                    content += f"*最终更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
                    content += "## 目录\n\n"
                    
                    # 按表名排序写入目录内容
                    for table_key in sorted(self.tables_index.keys()):
                        final_file.write(self.tables_index[table_key])
                    
                    # 添加分隔线
                    final_file.write("\n## 详细表结构\n\n")
                    
                    # 如果有保存表内容，则按照排序后的表名从内存写入表内容
                    if self.tables_content:
                        for table_key in sorted(self.tables_content.keys()):
                            final_file.write(self.tables_content[table_key])
                    # 否则，从原文件中复制表内容（跳过头部和目录）
                    else:
                        with open(self.filename, 'r', encoding='utf-8') as original_file:
                            # 跳过头部和目录
                            found_detail_section = False
                            for line in original_file:
                                if not found_detail_section and "## 详细表结构" in line:
                                    found_detail_section = True
                                    continue  # 跳过这一行
                                
                                if found_detail_section:
                                    final_file.write(line)
                
                # 替换原始文件
                self.close()  # 确保原文件已关闭
                
                try:
                    os.replace(final_filename, self.filename)
                    print(f"已生成最终排序文档: {self.filename}")
                    return True
                except Exception as e:
                    print(f"替换原始文件失败: {e}")
                    print(f"最终文档保存在: {final_filename}")
                    return False
                    
            except Exception as e:
                print(f"生成最终文档失败: {e}")
                return False
    
    def write_table_structure(self, table_info):
        """写入单个表的结构信息，直接写入主文件"""
        with self.content_lock:
            owner = table_info['owner']
            table_name = table_info['name']
            
            # 记录索引以便后续生成目录
            comment = table_info['comment'] if table_info['comment'] and table_info['comment'] != '无描述' else "-"
            self.write_table_index(owner, table_name, comment)
            
            # 构建表内容
            rows = table_info['rows'] or "-"
            last_analyzed = table_info['last_analyzed'] or "-"
            
            # 先创建完整内容
            content = f"### {owner}.{table_name}\n\n"
            content += f"**表描述**: {comment}\n\n"
            content += f"**记录数**: {rows}\n\n"
            content += f"**最后分析时间**: {last_analyzed}\n\n"
            
            # 列信息
            content += "#### 列信息\n\n"
            content += "| 序号 | 列名 | 数据类型 | 允许空 | 默认值 | 注释 |\n"
            content += "| --- | --- | --- | --- | --- | --- |\n"
            
            for i, column in enumerate(table_info['columns']):
                column_comment = column['comment'] if column['comment'] and column['comment'] != '无描述' else "-"
                default_value = column['default'] if column['default'] and column['default'] != "-" else "-"
                content += f"| {i+1} | {column['name']} | {column['data_type']} | {'是' if column['nullable'] == 'Y' else '否'} | {default_value} | {column_comment} |\n"
            
            # 主键信息
            if table_info['primary_keys']:
                content += "\n#### 主键\n\n"
                content += "| 列名 |\n"
                content += "| --- |\n"
                for pk in table_info['primary_keys']:
                    content += f"| {pk} |\n"
            
            # 外键信息
            if table_info['foreign_keys']:
                content += "\n#### 外键\n\n"
                content += "| 约束名 | 列名 | 引用表 | 引用列 |\n"
                content += "| --- | --- | --- | --- |\n"
                for fk in table_info['foreign_keys']:
                    content += f"| {fk[0]} | {fk[1]} | {fk[2]} | {fk[3]} |\n"
            
            # 索引信息
            if table_info['indices']:
                content += "\n#### 索引\n\n"
                content += "| 索引名 | 类型 | 唯一性 | 列名 | 状态 |\n"
                content += "| --- | --- | --- | --- | --- |\n"
                for idx in table_info['indices']:
                    content += f"| {idx[0]} | {idx[1]} | {idx[2]} | {idx[3]} | {idx[4]} |\n"
            
            content += "\n"
            
            # 可选：存储表内容到内存以便最终排序（如果表太多可能占用内存过多，可以删除）
            # self.tables_content[f"{owner}.{table_name}"] = content
            
            # 直接写入到主文件
            with self.lock:
                self.write_to_file(content)


class MySQLWriter:
    """MySQL数据库写入器，支持将表结构信息保存到MySQL数据库"""
    
    def __init__(self, host, port, user, password, database):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        self.lock = threading.Lock()  # 添加线程锁保护数据库写入
    
    def open(self):
        """打开数据库连接并创建所需表"""
        try:
            self.connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset='utf8mb4'
            )
            
            # 创建所需的表
            self._create_tables()
            
            return self
        except Exception as e:
            print(f"MySQL连接失败: {e}")
            if self.connection:
                self.connection.close()
                self.connection = None
            raise
    
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def __enter__(self):
        """支持上下文管理器协议的进入方法"""
        return self.open()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器协议的退出方法"""
        self.close()
        return False  # 不抑制异常
    
    def _create_tables(self):
        """创建必要的数据库表"""
        with self.connection.cursor() as cursor:
            # 创建表信息表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS oracle_tables (
                id INT AUTO_INCREMENT PRIMARY KEY,
                owner VARCHAR(128) NOT NULL,
                table_name VARCHAR(128) NOT NULL,
                comment TEXT,
                rows_count BIGINT,
                last_analyzed DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY(owner, table_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # 创建列信息表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS oracle_columns (
                id INT AUTO_INCREMENT PRIMARY KEY,
                table_id INT NOT NULL,
                column_name VARCHAR(128) NOT NULL,
                data_type VARCHAR(128),
                nullable VARCHAR(3),
                default_value TEXT,
                comment TEXT,
                column_id INT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY(table_id, column_name),
                FOREIGN KEY(table_id) REFERENCES oracle_tables(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # 创建主键表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS oracle_primary_keys (
                id INT AUTO_INCREMENT PRIMARY KEY,
                table_id INT NOT NULL,
                column_name VARCHAR(128) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY(table_id, column_name),
                FOREIGN KEY(table_id) REFERENCES oracle_tables(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # 创建外键表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS oracle_foreign_keys (
                id INT AUTO_INCREMENT PRIMARY KEY,
                table_id INT NOT NULL,
                constraint_name VARCHAR(128) NOT NULL,
                column_name VARCHAR(128) NOT NULL,
                referenced_table VARCHAR(128) NOT NULL,
                referenced_column VARCHAR(128) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY(table_id, constraint_name, column_name),
                FOREIGN KEY(table_id) REFERENCES oracle_tables(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # 创建索引表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS oracle_indices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                table_id INT NOT NULL,
                index_name VARCHAR(128) NOT NULL,
                index_type VARCHAR(128),
                uniqueness VARCHAR(128),
                column_name VARCHAR(128) NOT NULL,
                status VARCHAR(128),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(table_id) REFERENCES oracle_tables(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            self.connection.commit()
    
    def save_table_info(self, table_info):
        """保存表信息到MySQL数据库"""
        try:
            with self.lock:  # 使用线程锁
                if not self.connection:
                    print("MySQL连接已关闭，无法保存数据")
                    return False
                
                owner = table_info['owner']
                table_name = table_info['name']
                
                # 使用事务包装所有操作，确保原子性
                with self.connection.cursor() as cursor:
                    try:
                        # 开始事务
                        self.connection.begin()
                        
                        # 插入或更新表信息
                        cursor.execute("""
                        INSERT INTO oracle_tables 
                            (owner, table_name, comment, rows_count, last_analyzed)
                        VALUES 
                            (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            comment = VALUES(comment),
                            rows_count = VALUES(rows_count),
                            last_analyzed = VALUES(last_analyzed);
                        """, (
                            owner,
                            table_name,
                            table_info['comment'] if table_info['comment'] != "-" else None,
                            table_info['rows'],
                            table_info['last_analyzed']
                        ))
                        
                        # 获取表ID
                        cursor.execute("""
                        SELECT id FROM oracle_tables WHERE owner = %s AND table_name = %s;
                        """, (owner, table_name))
                        table_id = cursor.fetchone()[0]
                        
                        # 清除旧数据
                        cursor.execute("DELETE FROM oracle_columns WHERE table_id = %s;", (table_id,))
                        cursor.execute("DELETE FROM oracle_primary_keys WHERE table_id = %s;", (table_id,))
                        cursor.execute("DELETE FROM oracle_foreign_keys WHERE table_id = %s;", (table_id,))
                        cursor.execute("DELETE FROM oracle_indices WHERE table_id = %s;", (table_id,))
                        
                        # 插入列信息
                        for column in table_info['columns']:
                            cursor.execute("""
                            INSERT INTO oracle_columns 
                                (table_id, column_name, data_type, nullable, default_value, comment)
                            VALUES 
                                (%s, %s, %s, %s, %s, %s);
                            """, (
                                table_id,
                                column['name'],
                                column['data_type'],
                                column['nullable'],
                                column['default'] if column['default'] != "-" else None,
                                column['comment'] if column['comment'] != "-" else None
                            ))
                        
                        # 插入主键信息
                        for pk in table_info['primary_keys']:
                            cursor.execute("""
                            INSERT INTO oracle_primary_keys 
                                (table_id, column_name)
                            VALUES 
                                (%s, %s);
                            """, (table_id, pk))
                        
                        # 插入外键信息
                        for fk in table_info['foreign_keys']:
                            cursor.execute("""
                            INSERT INTO oracle_foreign_keys 
                                (table_id, constraint_name, column_name, referenced_table, referenced_column)
                            VALUES 
                                (%s, %s, %s, %s, %s);
                            """, (table_id, fk[0], fk[1], fk[2], fk[3]))
                        
                        # 插入索引信息
                        for idx in table_info['indices']:
                            cursor.execute("""
                            INSERT INTO oracle_indices 
                                (table_id, index_name, index_type, uniqueness, column_name, status)
                            VALUES 
                                (%s, %s, %s, %s, %s, %s);
                            """, (table_id, idx[0], idx[1], idx[2], idx[3], idx[4]))
                        
                        # 提交事务
                        self.connection.commit()
                        return True
                    except Exception as e:
                        # 发生错误，回滚事务
                        self.connection.rollback()
                        print(f"保存表 {owner}.{table_name} 到MySQL时出错，事务已回滚: {e}")
                        return False
                    
        except Exception as e:
            print(f"保存表 {table_info['owner']}.{table_info['name']} 到MySQL时出错: {e}")
            return False


# 创建Oracle连接池并预先获取所需连接
def create_oracle_connection_pool(username, password, dsn, concurrency=10, table_timeout=60, min_size=None, max_size=None, increment=1):
    """创建Oracle连接池并预先测试获取指定数量的连接
    
    参数:
        username: 数据库用户名
        password: 数据库密码  
        dsn: 数据库连接字符串
        concurrency: 并发数，也是要预先测试获取的连接数
        table_timeout: 表查询超时时间（秒）
        min_size: 连接池最小连接数，默认为concurrency
        max_size: 连接池最大连接数，默认为concurrency+2  
        increment: 连接池增长步长
        
    返回:
        成功时返回连接池，失败时返回None
    """
    try:
        # 设置默认值
        if min_size is None:
            min_size = concurrency
            
        if max_size is None:
            max_size = concurrency + 2
            
        print(f"正在创建Oracle连接池 (min={min_size}, max={max_size}, increment={increment})...")
        
        # 创建连接池
        pool = cx_Oracle.SessionPool(
            user=username,
            password=password,
            dsn=dsn,
            min=min_size,
            max=max_size,
            increment=increment,
            encoding="UTF-8",
            threaded=True  # 支持多线程
        )
        
        # 预先测试获取连接
        print(f"正在测试获取 {concurrency} 个数据库连接...")
        connections = []
        
        try:
            # 尝试获取所需数量的连接
            for i in range(concurrency):
                try:
                    # 获取连接
                    conn = pool.acquire()
                    if conn:
                        # 设置超时
                        conn.callTimeout = table_timeout * 1000  # 毫秒
                        connections.append(conn)
                        print(f"已获取连接 {i+1}/{concurrency}")
                    else:
                        raise Exception("无法获取连接，连接池可能已耗尽")
                except Exception as e:
                    print(f"获取第 {i+1} 个连接失败: {e}")
                    raise
                    
            print(f"已成功测试获取 {len(connections)} 个连接，连接池正常工作")
                
            # 返还所有连接到池
            for conn in connections:
                pool.release(conn)
                
            return pool
            
        except Exception as e:
            # 确保释放已获取的连接
            for conn in connections:
                try:
                    pool.release(conn)
                except:
                    pass
                    
            # 关闭连接池
            try:
                pool.close()
            except:
                pass
                
            print(f"连接池预获取连接测试失败: {e}")
            print("无法获取足够的数据库连接资源，请减少并发数或检查数据库连接配置")
            return None
            
    except Exception as e:
        print(f"创建Oracle连接池失败: {e}")
        return None


def analyze_table_worker_with_pool(pool, table, table_timeout=60):
    """使用连接池的表分析工作函数"""
    owner, table_name = table[0], table[1]
    
    # 从连接池获取连接
    connection = None
    cursor = None

    try:
        # 获取连接
        connection = pool.acquire()
        connection.callTimeout = table_timeout * 1000  # 毫秒
        cursor = connection.cursor()
        
        # 获取主键信息
        primary_keys = get_primary_keys(cursor, owner, table_name)
        
        # 获取外键信息
        foreign_keys = get_foreign_keys(cursor, owner, table_name)
        
        # 获取索引信息
        indices = get_indices(cursor, owner, table_name)
        
        # 构建表信息
        comment = table[6] if table[6] and table[6] != '无描述' else "-"
        table_info = {
            'owner': owner,
            'name': table_name,
            'comment': comment,
            'rows': table[4],
            'last_analyzed': table[5],
            'columns': [],
            'primary_keys': primary_keys,
            'foreign_keys': foreign_keys,
            'indices': indices
        }
        
        # 获取列信息
        columns = get_table_columns(cursor, owner, table_name)
        
        for column in columns:
            column_comment = column[5] if column[5] and column[5] != '无描述' else "-"
            column_info = {
                'name': column[0],
                'data_type': f"{column[1]}({column[7] or column[2] or ''}{',' + str(column[8]) if column[8] is not None else ''})",
                'nullable': column[3],
                'default': column[4],
                'comment': column_comment
            }
            table_info['columns'].append(column_info)
        
        return True, table_info
    
    except cx_Oracle.Error as error:
        error_msg = str(error)
        # 只打印具体错误，不需要堆栈
        print(f"分析表 {owner}.{table_name} 时出错: {error_msg}")
        return False, None
    
    except Exception as e:
        print(f"分析表 {owner}.{table_name} 时出现未预期的错误: {e}")
        return False, None
    
    finally:
        # 确保资源正确释放
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
            
        try:
            if connection:
                # 将连接归还到连接池而不是关闭
                pool.release(connection)
        except Exception:
            pass


@timer
def analyze_tables_with_pool(tables, pool, output_file, mysql_params=None, concurrency=10, table_timeout=60):
    """使用连接池并发分析表结构并写入文件"""
    if not tables:
        print("没有找到符合条件的表")
        return 0
    
    # 最大并发数不超过表的数量、系统限制和连接池最大大小
    concurrency = min(concurrency, len(tables), os.cpu_count() * 2, pool.max)
    print(f"共找到 {len(tables)} 个表，使用 {concurrency} 个并发线程进行分析...")
    
    success_count = 0
    
    # 创建线程安全的计数器
    processed_count = 0
    lock = threading.Lock()
    
    # 创建Markdown写入器
    with MarkdownWriter(output_file) as md_writer:
        # 创建MySQL写入器(如果配置了)
        mysql_writer = None
        if mysql_params:
            try:
                mysql_writer = MySQLWriter(
                    host=mysql_params.get('host', 'localhost'),
                    port=mysql_params.get('port', 3306),
                    user=mysql_params.get('user', 'root'),
                    password=mysql_params.get('password', ''),
                    database=mysql_params.get('database', 'oracle_metadata')
                ).open()
                print(f"成功连接到MySQL数据库: {mysql_params.get('database')}@{mysql_params.get('host')}")
            except Exception as e:
                print(f"MySQL连接失败，将只保存到Markdown文件: {e}")
                mysql_writer = None
        
        try:
            # 创建线程池
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                # 提交所有表分析任务
                futures = {}
                for i, table in enumerate(tables):
                    # 不再输出开始分析的信息
                    future = executor.submit(analyze_table_worker_with_pool, pool, table, table_timeout)
                    futures[future] = (i+1, table)
                
                # 处理结果
                for future in concurrent.futures.as_completed(futures):
                    i, table = futures[future]
                    table_name = f"{table[0]}.{table[1]}"
                    
                    try:
                        success, table_info = future.result()
                        
                        # 更新处理计数
                        with lock:
                            processed_count += 1
                            print(f"[{processed_count}/{len(tables)}] 完成分析表 {table_name}")
                        
                        # 检查分析是否成功
                        if not success:
                            print(f"错误：表 {table_name} 分析失败，程序退出")
                            # 将结果标记为错误并退出程序
                            sys.exit(1)
                        
                        if table_info is None:
                            print(f"错误：表 {table_name} 分析结果为空，程序退出")
                            sys.exit(1)
                            
                        # 写入表结构到Markdown文件
                        md_writer.write_table_structure(table_info)
                        
                        # 写入表结构到MySQL数据库
                        if mysql_writer:
                            mysql_save_success = mysql_writer.save_table_info(table_info)
                            if not mysql_save_success:
                                print(f"错误：表 {table_info['owner']}.{table_info['name']} 保存到MySQL失败")
                                # sys.exit(1)
                        
                        # 原子地增加成功计数
                        with lock:
                            success_count += 1
                            
                    except Exception as e:
                        print(f"错误：处理表 {table_name} 时发生异常: {e}，程序退出")
                        sys.exit(1)
            
            # 完成后更新目录
            md_writer.finalize_toc()
        
        finally:
            # 关闭MySQL连接
            if mysql_writer:
                mysql_writer.close()
    
    print(f"表结构分析完成，成功分析 {success_count}/{len(tables)} 个表")
    return success_count


def main(args=None):
    """主函数"""
    # 数据库连接信息 - 请修改为实际的连接信息
    username = "iih"
    password = "1WhQjdl43b"
    dsn = "192.168.1.227:1521/iih"  # 如 "localhost:1521/ORCL"
    
    # 设置全局超时（单位：秒）
    query_timeout = args.timeout if args and hasattr(args, 'timeout') else 300  # 单个查询超时时间
    table_timeout = args.table_timeout if args and hasattr(args, 'table_timeout') else 60  # 单表分析超时时间
    
    # 并发数
    concurrency = args.concurrency if args and hasattr(args, 'concurrency') else 10
    
    # 过滤条件
    owner_filter = args.owner if args and hasattr(args, 'owner') else None
    table_filter = args.table if args and hasattr(args, 'table') else None
    
    if owner_filter or table_filter:
        print(f"应用过滤条件: 所有者={owner_filter or '任意'}, 表名={table_filter or '任意'}")
    
    print(f"全局超时: {query_timeout}秒, 单表超时: {table_timeout}秒, 并发线程: {concurrency}")
    
    # 输出文件
    output_file = args.output if args and hasattr(args, 'output') else 'database_readme.md'
    
    # MySQL连接参数 - 直接在代码中配置
    mysql_params = {
        'host': 'host.docker.internal',     # MySQL主机地址
        'port': 3306,            # MySQL端口
        'user': 'root',          # MySQL用户名
        'password': 'root',          # MySQL密码
        'database': 'his-metadata'  # MySQL数据库名
    }
    
    # 是否启用MySQL保存 - 启用MySQL保存功能
    enable_mysql = True  # 设置为True启用MySQL保存功能
    
    if enable_mysql:
        print(f"MySQL保存已启用: {mysql_params['database']}@{mysql_params['host']}")
    else:
        mysql_params = None
        print("MySQL保存功能已禁用，仅保存到Markdown文件")
    
    # 各种连接对象
    connection = None
    cursor = None
    pool = None
    
    try:
        # 建立连接
        print("正在连接到Oracle数据库...")
        
        # 创建Oracle连接池并预先测试连接
        pool = create_oracle_connection_pool(
            username, 
            password, 
            dsn,
            concurrency=concurrency,
            table_timeout=table_timeout
        )
        
        if not pool:
            print("创建Oracle连接池失败，程序终止")
            return
            
        # 创建一个连接用于初始查询
        connection = pool.acquire()
        connection.callTimeout = query_timeout * 1000  # 毫秒
        cursor = connection.cursor()
        
        print("Oracle连接成功！")
        
        # 获取表列表
        print("正在获取表信息...")
        tables = get_all_tables(cursor, owner_filter, table_filter)
        
        if not tables:
            print("未找到符合条件的表！请检查过滤条件是否正确。")
            return
        
        # 归还连接到连接池
        if cursor:
            cursor.close()
            cursor = None
        
        if connection:
            pool.release(connection)
            connection = None
            
        # 使用连接池分析并写入文件
        analyze_tables_with_pool(tables, pool, output_file, mysql_params, concurrency, table_timeout)
        
        print(f"成功生成数据库文档: {output_file}")
        
    except cx_Oracle.Error as error:
        error_msg = str(error)
        print(f"数据库错误: {error_msg}")
        
        if "DPI-1047" in error_msg:
            print("Oracle客户端库错误：未找到或无法加载Oracle客户端库")
        elif "ORA-12154" in error_msg:
            print("连接标识符错误：请检查DSN格式是否正确")
        elif "ORA-00918" in error_msg:
            print("SQL错误：列名冲突")
        elif "ORA-03113" in error_msg or "ORA-03114" in error_msg:
            print("数据库连接已断开，可能是网络问题或Oracle服务器重启")
        elif "DPI-1067" in error_msg or "timeout" in error_msg.lower():
            print("查询超时：某个查询操作花费了太长时间")
            print("建议增加超时时间或减少并发数")
            
    except Exception as e:
        print(f"生成文档时出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理所有资源
        try:
            if cursor:
                cursor.close()
        except:
            pass
            
        try:
            if connection:
                if pool:
                    pool.release(connection)
                else:
                    connection.close()
        except:
            pass
            
        try:
            if pool:
                pool.close()
        except:
            pass
            
        print("数据库连接已关闭")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Oracle数据库字典分析工具")
    parser.add_argument("--owner", help="过滤所有者")
    parser.add_argument("--table", help="过滤表名")
    parser.add_argument("--timeout", type=int, default=300, help="全局查询超时时间（秒）")
    parser.add_argument("--table-timeout", type=int, default=60, help="单表分析超时时间（秒）")
    parser.add_argument("--output", default="database_readme.md", help="输出文件名")
    parser.add_argument("--concurrency", type=int, default=10, help="并发线程数")
    
    args = parser.parse_args()
    main(args) 