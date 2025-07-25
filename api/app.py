#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Oracle表结构查询API
提供查询Oracle表列信息的RESTful API接口
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import traceback

from database import test_connection
from models import get_table_columns_info, search_tables, update_table_info, update_table_columns, get_id_mapping_by_name


def create_app():
    """创建Flask应用工厂函数"""
    app = Flask(__name__)
    CORS(app)  # 启用跨域支持
    
    # 设置JSON编码，确保中文正常显示
    app.config['JSON_AS_ASCII'] = False
    app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'
    
    # 注册路由
    register_routes(app)
    register_error_handlers(app)
    
    return app


def parse_table_name(table_name):
    """
    解析表名，支持OWNER.TABLE_NAME格式
    
    Args:
        table_name: 表名，可能包含owner信息（如 "IIH.USER_INFO" 或 "USER_INFO"）
    
    Returns:
        tuple: (actual_table_name, owner) 
    """
    if not table_name:
        return None, None
    
    table_name = table_name.strip()
    if '.' in table_name:
        # 包含owner信息，格式为 OWNER.TABLE_NAME
        parts = table_name.split('.', 1)  # 只分割第一个点号
        if len(parts) == 2:
            owner = parts[0].strip()
            actual_table_name = parts[1].strip()
            return actual_table_name, owner if owner else None
    
    # 不包含owner信息，直接返回表名
    return table_name, None


def register_routes(app):
    """注册所有路由"""

    @app.route('/health', methods=['GET'])
    def health_check():
        """健康检查接口"""
        try:
            if test_connection():
                response = jsonify({
                    'success': True,
                    'message': '服务正常',
                    'database': '连接正常'
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response
            else:
                response = jsonify({
                    'success': False,
                    'message': '数据库连接失败'
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 500
        except Exception as e:
            response = jsonify({
                'success': False,
                'message': f'健康检查失败: {str(e)}'
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response, 500

    @app.route('/api/tables/<table_name>/columns', methods=['GET'])
    def get_table_columns(table_name):
        """
        获取表的列信息
        
        Args:
            table_name: 表名（路径参数），支持OWNER.TABLE_NAME格式
        
        Returns:
            JSON: 表和列的详细信息
        """
        try:
            # 解析表名，提取owner和实际表名
            actual_table_name, owner = parse_table_name(table_name)
            
            # 验证表名
            if not actual_table_name:
                response = jsonify({
                    'success': False,
                    'error': '表名不能为空'
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 400
            
            # 查询表列信息
            result = get_table_columns_info(actual_table_name, owner)
            
            if result is None:
                display_name = f'{owner}.{actual_table_name}' if owner else actual_table_name
                response = jsonify({
                    'success': False,
                    'error': f'未找到表 {display_name}',
                    'message': '请检查表名是否正确，支持格式：TABLE_NAME 或 OWNER.TABLE_NAME'
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 404
            
            response = jsonify({
                'success': True,
                'data': result
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
            
        except Exception as e:
            print(f"API错误: {e}")
            traceback.print_exc()
            response = jsonify({
                'success': False,
                'error': '服务器内部错误',
                'message': str(e)
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response, 500

    @app.route('/api/tables/search', methods=['GET'])
    def search_tables_api():
        """
        搜索表名和注释
        
        Args:
            keyword: 搜索关键词（查询参数，可选）- 匹配表名或注释
            owner: 表所有者（查询参数，可选）
        
        Returns:
            JSON: 匹配的表列表
        """
        try:
            # 获取查询参数
            keyword = request.args.get('keyword')
            owner = request.args.get('owner')
            
            # 搜索表
            tables = search_tables(keyword, owner)
            
            response = jsonify({
                'success': True,
                'data': {
                    'tables': tables,
                    'count': len(tables)
                }
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
            
        except Exception as e:
            print(f"搜索表API错误: {e}")
            traceback.print_exc()
            response = jsonify({
                'success': False,
                'error': '服务器内部错误',
                'message': str(e)
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response, 500

    @app.route('/api/tables/<table_name>', methods=['PUT'])
    def update_table(table_name):
        """
        更新表的基本信息
        
        Args:
            table_name: 表名（路径参数），支持OWNER.TABLE_NAME格式
        
        Request Body:
            JSON: 包含要更新的表信息
        
        Returns:
            JSON: 更新结果
        """
        try:
            # 解析表名，提取owner和实际表名
            actual_table_name, owner = parse_table_name(table_name)
            
            # 验证表名
            if not actual_table_name:
                response = jsonify({
                    'success': False,
                    'error': '表名不能为空'
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 400
            
            # 获取请求体数据
            if not request.is_json:
                response = jsonify({
                    'success': False,
                    'error': '请求内容必须是JSON格式'
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 400
            
            table_data = request.get_json()
            if not table_data:
                response = jsonify({
                    'success': False,
                    'error': '请求体不能为空'
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 400
            
            # 更新表信息
            result = update_table_info(actual_table_name, owner, table_data)
            
            if result['success']:
                response = jsonify({
                    'success': True,
                    'data': result
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response
            else:
                response = jsonify({
                    'success': False,
                    'error': result['error']
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 400
            
        except Exception as e:
            print(f"更新表信息API错误: {e}")
            traceback.print_exc()
            response = jsonify({
                'success': False,
                'error': '服务器内部错误',
                'message': str(e)
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response, 500

    @app.route('/api/tables/<table_name>/columns', methods=['PUT'])
    def update_table_columns_api(table_name):
        """
        批量更新表的列信息
        
        Args:
            table_name: 表名（路径参数），支持OWNER.TABLE_NAME格式
        
        Request Body:
            JSON: 包含要更新的列信息数组
        
        Returns:
            JSON: 批量更新结果
        """
        try:
            # 解析表名，提取owner和实际表名
            actual_table_name, owner = parse_table_name(table_name)
            
            # 验证表名
            if not actual_table_name:
                response = jsonify({
                    'success': False,
                    'error': '表名不能为空'
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 400
            
            # 获取请求体数据
            if not request.is_json:
                response = jsonify({
                    'success': False,
                    'error': '请求内容必须是JSON格式'
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 400
            
            request_data = request.get_json()
            if not request_data:
                response = jsonify({
                    'success': False,
                    'error': '请求体不能为空'
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 400
            
            # 提取columns数组
            columns_data = request_data.get('columns', [])
            if not columns_data:
                response = jsonify({
                    'success': False,
                    'error': '请求体中必须包含columns数组'
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 400
            
            # 批量更新列信息
            result = update_table_columns(actual_table_name, owner, columns_data)
            
            if result['success']:
                response = jsonify({
                    'success': True,
                    'data': result
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response
            else:
                response = jsonify({
                    'success': False,
                    'error': result['error']
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 400
            
        except Exception as e:
            print(f"批量更新列信息API错误: {e}")
            traceback.print_exc()
            response = jsonify({
                'success': False,
                'error': '服务器内部错误',
                'message': str(e)
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response, 500

    @app.route('/api/id-mappings/<id_name>', methods=['GET'])
    def get_id_mapping(id_name):
        """
        获取ID映射信息
        
        Args:
            id_name: ID字段名（路径参数）
        
        Returns:
            JSON: ID映射信息
        """
        try:
            # 验证ID名
            if not id_name:
                response = jsonify({
                    'success': False,
                    'error': 'ID名不能为空'
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 400
            
            # 查询映射信息
            mapping = get_id_mapping_by_name(id_name)
            
            if mapping is None:
                response = jsonify({
                    'success': False,
                    'error': {
                        'code': 'ID_NOT_FOUND',
                        'message': f"未找到ID名为 '{id_name}' 的映射"
                    }
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 404
            
            # 返回映射信息
            response = jsonify({
                'success': True,
                'data': mapping,
                'message': '查询成功'
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
            
        except Exception as e:
            print(f"获取ID映射API错误: {e}")
            traceback.print_exc()
            response = jsonify({
                'success': False,
                'error': '服务器内部错误',
                'message': str(e)
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response, 500


def register_error_handlers(app):
    """注册错误处理器"""
    @app.errorhandler(404)
    def not_found(error):
        """404错误处理"""
        response = jsonify({
            'success': False,
            'error': '接口不存在'
        })
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response, 404

    @app.errorhandler(500)
    def internal_error(error):
        """500错误处理"""
        response = jsonify({
            'success': False,
            'error': '服务器内部错误'
        })
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response, 500


# 创建应用实例供gunicorn使用
app = create_app()

# 为了向后兼容，保留直接运行的方式
if __name__ == '__main__':
    print("启动Oracle表结构查询API服务...")
    app.run(host='0.0.0.0', port=5050, debug=True) 