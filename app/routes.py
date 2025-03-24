from flask import Blueprint, render_template, request, Response, jsonify, current_app, stream_with_context
import requests
import time
import json
import os
from app import db
from app.models import Request as RequestModel, Response as ResponseModel

# 前端界面路由
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """显示请求列表的主页面"""
    return render_template('index.html')

@main_bp.route('/api/readme')
def get_readme():
    """获取README.md内容的API"""
    readme_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'README.md')
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/requests')
def get_requests():
    """获取所有请求的API"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    pagination = RequestModel.query.order_by(RequestModel.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    
    requests_data = []
    for req in pagination.items:
        requests_data.append({
            'id': req.id,
            'timestamp': req.timestamp.isoformat(),
            'method': req.method,
            'path': req.path,
            'has_response': len(req.responses) > 0
        })
    
    return jsonify({
        'requests': requests_data,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    })

@main_bp.route('/api/requests/<int:request_id>')
def get_request_detail(request_id):
    """获取请求详情的API"""
    req = RequestModel.query.get_or_404(request_id)
    
    request_data = {
        'id': req.id,
        'timestamp': req.timestamp.isoformat(),
        'method': req.method,
        'path': req.path,
        'headers': req.get_headers(),
        'body': req.get_body(),
        'responses': []
    }
    
    for resp in req.responses:
        response_data = {
            'id': resp.id,
            'status_code': resp.status_code,
            'headers': json.loads(resp.headers) if resp.headers else {},
            'body': resp.body,
            'is_stream': resp.is_stream,
            'time_taken': resp.time_taken
        }
        request_data['responses'].append(response_data)
    
    return jsonify(request_data)

# 代理服务路由
proxy_bp = Blueprint('proxy', __name__, url_prefix='/api/v1')

OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'

def make_proxy_request(method, path, headers, json_data=None):
    """处理普通请求的代理函数"""
    # 创建新的请求记录
    db_request = RequestModel(
        method=method,
        path=path
    )
    db_request.set_headers(headers)
    if json_data:
        db_request.set_body(json_data)
    
    db.session.add(db_request)
    db.session.commit()
    
    # 转发请求到OpenRouter
    start_time = time.time()
    url = f"{OPENROUTER_BASE_URL}{path}"
    
    proxied_headers = dict(headers)
    # 移除可能导致问题的头部
    if 'Host' in proxied_headers:
        del proxied_headers['Host']
        
    try:
        if method == 'GET':
            resp = requests.get(url, headers=proxied_headers)
        elif method == 'POST':
            resp = requests.post(url, headers=proxied_headers, json=json_data)
        elif method == 'DELETE':
            resp = requests.delete(url, headers=proxied_headers)
        elif method == 'PUT':
            resp = requests.put(url, headers=proxied_headers, json=json_data)
        else:
            resp = Response('Method not supported', status=405)
            
        time_taken = time.time() - start_time
        
        # 保存响应
        db_response = ResponseModel(
            request_id=db_request.id,
            status_code=resp.status_code,
            body=resp.text,
            time_taken=time_taken,
            is_stream=False
        )
        db_response.set_headers(dict(resp.headers))
        
        db.session.add(db_response)
        db.session.commit()
        
        # 返回响应给客户端
        response = Response(
            resp.content,
            status=resp.status_code,
            headers=dict(resp.headers)
        )
        return response
        
    except Exception as e:
        time_taken = time.time() - start_time
        
        # 保存错误响应
        db_response = ResponseModel(
            request_id=db_request.id,
            status_code=500,
            body=str(e),
            time_taken=time_taken,
            is_stream=False
        )
        db.session.add(db_response)
        db.session.commit()
        
        return jsonify({'error': str(e)}), 500

def make_proxy_stream_request(method, path, headers, json_data=None):
    """处理流式请求的代理函数"""
    # 创建新的请求记录
    db_request = RequestModel(
        method=method,
        path=path
    )
    db_request.set_headers(headers)
    if json_data:
        db_request.set_body(json_data)
    
    db.session.add(db_request)
    db.session.commit()
    
    # 转发请求到OpenRouter
    start_time = time.time()
    url = f"{OPENROUTER_BASE_URL}{path}"
    
    proxied_headers = dict(headers)
    # 移除可能导致问题的头部
    if 'Host' in proxied_headers:
        del proxied_headers['Host']
        
    try:
        # 使用stream=True发送请求
        resp = requests.post(url, headers=proxied_headers, json=json_data, stream=True)
        
        # 收集整个响应内容用于日志记录
        complete_content = b''
        
        def generate():
            nonlocal complete_content
            for chunk in resp.iter_content(chunk_size=1024):
                complete_content += chunk
                yield chunk
            
            # 在完成流后记录响应
            time_taken = time.time() - start_time
            
            # 保存响应
            db_response = ResponseModel(
                request_id=db_request.id,
                status_code=resp.status_code,
                body=complete_content.decode('utf-8', errors='replace'),
                time_taken=time_taken,
                is_stream=True
            )
            db_response.set_headers(dict(resp.headers))
            
            db.session.add(db_response)
            db.session.commit()
        
        return Response(
            stream_with_context(generate()),
            status=resp.status_code,
            headers=dict(resp.headers)
        )
        
    except Exception as e:
        time_taken = time.time() - start_time
        
        # 保存错误响应
        db_response = ResponseModel(
            request_id=db_request.id,
            status_code=500,
            body=str(e),
            time_taken=time_taken,
            is_stream=False
        )
        db.session.add(db_response)
        db.session.commit()
        
        return jsonify({'error': str(e)}), 500

@proxy_bp.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE'])
@proxy_bp.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy(path):
    """通用代理路由，处理所有OpenRouter API请求"""
    # 检查请求是否期望流式响应
    headers = dict(request.headers)
    json_data = request.get_json(silent=True)
    
    if request.method == 'POST' and json_data and json_data.get('stream', False):
        return make_proxy_stream_request(request.method, '/' + path, headers, json_data)
    else:
        return make_proxy_request(request.method, '/' + path, headers, json_data) 