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
from models import get_table_columns_info, search_tables


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
            table_name: 表名（路径参数）
            owner: 表所有者（查询参数，可选）
        
        Returns:
            JSON: 表和列的详细信息
        """
        try:
            # 获取查询参数
            owner = request.args.get('owner')
            
            # 验证表名
            if not table_name or not table_name.strip():
                response = jsonify({
                    'success': False,
                    'error': '表名不能为空'
                })
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return response, 400
            
            # 查询表列信息
            result = get_table_columns_info(table_name.strip(), owner)
            
            if result is None:
                response = jsonify({
                    'success': False,
                    'error': f'未找到表 {table_name}',
                    'message': '请检查表名是否正确，或指定正确的owner参数'
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