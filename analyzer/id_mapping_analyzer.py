#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Oracle ID映射分析工具
用于创建ID到显示名称的映射表，从表主键中推测对应的名称列映射关系
"""

import os
# 设置Oracle客户端库路径
oracle_client_path = os.environ.get('ORACLE_HOME', '/opt/oracle/instantclient_19_3')
os.environ['LD_LIBRARY_PATH'] = f"{oracle_client_path}:{os.environ.get('LD_LIBRARY_PATH', '')}"

import cx_Oracle  # type: ignore
import pymysql  # type: ignore
from datetime import datetime
import argparse
import sys
import re


class IDMappingAnalyzer:
    """ID映射分析器，从表主键中推测对应的名称列映射关系"""
    
    def __init__(self, oracle_conn, mysql_conn):
        self.oracle_conn = oracle_conn
        self.mysql_conn = mysql_conn
        
    def create_mapping_table(self):
        """创建oracle_id_mapping表"""
        print("正在创建oracle_id_mapping表...")
        
        with self.mysql_conn.cursor() as cursor:
            cursor.execute("""
                                      CREATE TABLE IF NOT EXISTS oracle_id_mapping (
                 id INT AUTO_INCREMENT PRIMARY KEY,
                 id_name VARCHAR(128) NOT NULL COMMENT 'ID字段名',
                 schema_name VARCHAR(128) NOT NULL COMMENT 'Schema名称',
                 table_name VARCHAR(128) NOT NULL COMMENT '表名',
                 name_column VARCHAR(128) NULL COMMENT '名称列名，找不到时为空',
                 created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                 updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                 UNIQUE KEY(schema_name, id_name),
                 INDEX idx_id_name (id_name),
                 INDEX idx_schema_table (schema_name, table_name)
             ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ID到显示名称映射表';
            """)
            
            self.mysql_conn.commit()
            print("oracle_id_mapping表创建成功")
    

    
    def get_primary_key_mappings(self):
        """从现有的表结构中获取主键映射"""
        print("正在从表结构中获取主键映射...")
        
        mappings = []
        
        with self.mysql_conn.cursor() as cursor:
            # 获取所有主键信息
            cursor.execute("""
            SELECT DISTINCT 
                ot.owner,
                ot.table_name,
                opk.column_name as pk_column
            FROM oracle_tables ot
            JOIN oracle_primary_keys opk ON ot.id = opk.table_id
            WHERE opk.column_name IS NOT NULL
            ORDER BY ot.owner, ot.table_name, opk.column_name
            """)
            
            pk_data = cursor.fetchall()
            print(f"找到 {len(pk_data)} 个主键字段")
            
            # 检查是否有重复的(schema_name, id_name)组合
            schema_id_combinations = {}
            for row in pk_data:
                owner, table_name, pk_column = row
                key = (owner.lower(), pk_column.lower())
                if key not in schema_id_combinations:
                    schema_id_combinations[key] = []
                schema_id_combinations[key].append((owner, table_name, pk_column))
            
            # 处理重复的组合，选择表名最短的
            valid_mappings = []
            
            for (schema, id_name), table_list in schema_id_combinations.items():
                if len(table_list) > 1:
                    # 同一schema下有多个表使用相同的主键名，选择表名最短的
                    shortest_table = min(table_list, key=lambda t: len(t[1]))
                    table_names = [f"{t[0]}.{t[1]}" for t in table_list]
                    print(f"主键名 {id_name} (Schema: {schema}) 出现在多个表: {', '.join(table_names)}，选择最短表名: {shortest_table[0]}.{shortest_table[1]}")
                    valid_mappings.append(shortest_table)
                else:
                    # 唯一的组合，直接处理
                    valid_mappings.extend(table_list)
            
            print(f"处理后获得 {len(valid_mappings)} 个主键字段（重复的已选择最短表名）")
            
            # 处理有效的映射
            for owner, table_name, pk_column in valid_mappings:
                # 推测对应的名称列
                name_column = self.guess_name_column(pk_column, owner, table_name)
                
                # 如果没有推测到合适的列，name_column设为空
                if not name_column:
                    name_column = ""
                    print(f"未找到合适的name/code列，name_column设为空: {pk_column} -> (空) (表: {owner}.{table_name})")
                else:
                    print(f"找到映射: {pk_column} -> {name_column} (表: {owner}.{table_name})")
                
                # 生成映射记录
                mappings.append({
                    'id_name': pk_column.lower(),
                    'schema_name': owner.lower(),
                    'table_name': table_name.lower(),
                    'name_column': name_column.lower() if name_column else ""
                })
        
        print(f"生成了 {len(mappings)} 个主键映射")
        return mappings
    
    def guess_name_column(self, pk_column, owner, table_name):
        """推测主键对应的名称列"""
        if not pk_column:
            return None
            
        pk_lower = pk_column.lower()
        
        # 生成所有候选列名（包括name和code）
        candidates = self._generate_display_candidates(pk_lower)
        
        # 验证候选列是否存在，且不能是id类型的列名
        for candidate in candidates:
            if self.verify_column_exists(owner, table_name, candidate) and not self._is_id_like_column(candidate):
                return candidate
        
        return None
    
    def _generate_display_candidates(self, pk_lower):
        """生成显示列的候选名称（包括name和code）"""
        candidates = []
        
        # 特殊情况处理
        special_mappings = {
        }
        '''
        'pk_dept': ['dept_name', 'dept_code'],
            'pk_user': ['user_name', 'user_code'],
            'pk_patient': ['patient_name', 'patient_code'],
            'pk_doctor': ['doctor_name', 'doctor_code'],
            'id_dept': ['name_dept', 'code_dept'],
            'id_user': ['name_user', 'code_user'],
        '''
        
        # 检查特殊映射
        if pk_lower in special_mappings:
            candidates.extend(special_mappings[pk_lower])
        
        # 通用模式匹配
        patterns = [
            # name模式（优先）
            (r'(.+)_id$', [r'\1_name', r'\1_code']),
            (r'(.+)_code$', [r'\1_name', r'\1_code']),
            (r'(.+)id$', [r'\1name', r'\1code']),
            (r'(.+)code$', [r'\1name', r'\1code']),
        ]
        
        # 应用正则模式匹配
        for pattern, replacements in patterns:
            for replacement in replacements:
                result = re.sub(pattern, replacement, pk_lower)
                if result != pk_lower:
                    candidates.append(result)
        
        # 如果包含id，尝试更多通用规则
        if 'id' in pk_lower:
            candidates.extend([
                # name变体
                pk_lower.replace('id', 'name'),
                pk_lower.replace('_id', '_name'),
                pk_lower + '_name',
                'name_' + pk_lower.replace('id', '').replace('_', ''),
                # code变体
                pk_lower.replace('id', 'code'),
                pk_lower.replace('_id', '_code'),
                pk_lower + '_code',
                'code_' + pk_lower.replace('id', '').replace('_', ''),
            ])
        
        # 添加通用列名
        candidates.extend(['name', 'code', 'title', 'label', 'desc', 'description'])
        
        # 去重并保持顺序
        seen = set()
        unique_candidates = []
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                unique_candidates.append(candidate)
        
        return unique_candidates
    
    def _is_id_like_column(self, column_name):
        """判断列名是否为id类型（应该避免作为显示列）"""
        if not column_name:
            return False
            
        column_lower = column_name.lower()
        
        # 检查是否包含id关键词
        id_patterns = [
            'id',           # 包含id
            '_id',          # 以_id结尾
            'id_',          # 以id_开头
            'key',          # 包含key
            '_key',         # 以_key结尾
            'key_',         # 以key_开头
        ]
        
        for pattern in id_patterns:
            if pattern in column_lower:
                return True
                
        return False
    
    def verify_column_exists(self, owner, table_name, column_name):
        """验证列是否存在于指定表中"""
        with self.mysql_conn.cursor() as cursor:
            cursor.execute("""
            SELECT COUNT(*)
            FROM oracle_columns oc
            JOIN oracle_tables ot ON oc.table_id = ot.id
            WHERE ot.owner = %s 
            AND ot.table_name = %s 
            AND oc.column_name = %s
            """, (owner, table_name, column_name.upper()))
            
            result = cursor.fetchone()
            return result[0] > 0
    
    def save_mappings(self, mappings):
        """保存映射关系到数据库"""
        if not mappings:
            print("没有映射数据需要保存")
            return 0
        
        print(f"正在保存 {len(mappings)} 个映射关系...")
        
        saved_count = 0
        with self.mysql_conn.cursor() as cursor:
            for mapping in mappings:
                try:
                    cursor.execute("""
                    INSERT INTO oracle_id_mapping (id_name, schema_name, table_name, name_column)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        name_column = VALUES(name_column),
                        updated_at = CURRENT_TIMESTAMP
                    """, (
                        mapping['id_name'],
                        mapping['schema_name'],
                        mapping['table_name'], 
                        mapping['name_column'] if mapping['name_column'] else None
                    ))
                    saved_count += 1
                except Exception as e:
                    print(f"保存映射失败 {mapping}: {e}")
            
            self.mysql_conn.commit()
        
        print(f"成功保存 {saved_count} 个映射关系")
        return saved_count
    
    def analyze_and_generate(self):
        """分析并生成ID映射表"""
        print("开始ID映射分析...")
        
        # 创建映射表
        self.create_mapping_table()
        
        # 收集主键映射
        pk_mappings = self.get_primary_key_mappings()
        
        # 使用主键映射作为所有映射
        all_mappings = pk_mappings
        
        # 去重
        unique_mappings = []
        seen = set()
        for mapping in all_mappings:
            key = (mapping['schema_name'], mapping['id_name'])
            if key not in seen:
                seen.add(key)
                unique_mappings.append(mapping)
        
        print(f"去重后共有 {len(unique_mappings)} 个唯一映射")
        
        # 保存映射
        saved_count = self.save_mappings(unique_mappings)
        
        print(f"ID映射分析完成，共保存 {saved_count} 个映射关系")
        return saved_count


def create_oracle_connection(username, password, dsn):
    """创建Oracle数据库连接"""
    try:
        connection = cx_Oracle.connect(
            user=username,
            password=password, 
            dsn=dsn,
            encoding="UTF-8"
        )
        return connection
    except Exception as e:
        print(f"Oracle连接失败: {e}")
        return None


def create_mysql_connection(host, port, user, password, database):
    """创建MySQL数据库连接"""
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset='utf8mb4'
        )
        return connection
    except Exception as e:
        print(f"MySQL连接失败: {e}")
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Oracle ID映射分析工具")
    parser.add_argument("--rebuild", action="store_true", help="重建映射表（清空后重新生成）")
    
    args = parser.parse_args()
    
    # Oracle数据库连接信息
    oracle_config = {
        'username': "iih",
        'password': "1WhQjdl43b", 
        'dsn': "192.168.1.227:1521/iih"
    }
    
    # MySQL数据库连接信息
    mysql_config = {
        'host': 'host.docker.internal',
        'port': 3306,
        'user': 'root',
        'password': 'root',
        'database': 'his-metadata'
    }
    
    oracle_conn = None
    mysql_conn = None
    
    try:
        # 连接Oracle数据库
        print("正在连接Oracle数据库...")
        oracle_conn = create_oracle_connection(
            oracle_config['username'],
            oracle_config['password'],
            oracle_config['dsn']
        )
        
        if not oracle_conn:
            print("Oracle连接失败，程序退出")
            return
        
        print("Oracle连接成功")
        
        # 连接MySQL数据库
        print("正在连接MySQL数据库...")
        mysql_conn = create_mysql_connection(
            mysql_config['host'],
            mysql_config['port'], 
            mysql_config['user'],
            mysql_config['password'],
            mysql_config['database']
        )
        
        if not mysql_conn:
            print("MySQL连接失败，程序退出") 
            return
            
        print("MySQL连接成功")
        
        # 如果需要重建表，先清空
        if args.rebuild:
            print("正在清空现有映射表...")
            with mysql_conn.cursor() as cursor:
                cursor.execute("DROP TABLE IF EXISTS oracle_id_mapping")
                mysql_conn.commit()
            print("映射表已清空")
        
        # 创建分析器并执行分析
        analyzer = IDMappingAnalyzer(oracle_conn, mysql_conn)
        saved_count = analyzer.analyze_and_generate()
        
        if saved_count > 0:
            print(f"\n映射表生成成功！共生成 {saved_count} 个ID映射关系")
            
            # 显示一些示例数据
            with mysql_conn.cursor() as cursor:
                cursor.execute("""
                SELECT id_name, schema_name, table_name, name_column 
                FROM oracle_id_mapping 
                ORDER BY schema_name, table_name, id_name 
                LIMIT 10
                """)
                
                sample_data = cursor.fetchall()
                if sample_data:
                    print("\n示例映射数据:")
                    print("ID名称 | Schema | 表名 | 名称列")
                    print("-" * 60)
                    for row in sample_data:
                        print(f"{row[0]} | {row[1]} | {row[2]} | {row[3]}")
        else:
            print("未生成任何映射关系")
            
    except Exception as e:
        print(f"程序执行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭数据库连接
        if oracle_conn:
            oracle_conn.close()
            print("Oracle连接已关闭")
            
        if mysql_conn:
            mysql_conn.close() 
            print("MySQL连接已关闭")


if __name__ == "__main__":
    main() 