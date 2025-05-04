from flask import Blueprint, render_template, request, Response, jsonify, current_app, stream_with_context, session, redirect, url_for, flash
import requests
import time
import json
import os
from app import db, bcrypt
from app.models import Request as RequestModel, Response as ResponseModel, AdminUser
import copy
import sqlite3
from functools import wraps

# 前端界面路由
main_bp = Blueprint('main', __name__)

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')

# 全局变量，用于存储API设置
OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
API_KEY = None
DEFAULT_MODEL = None
AUTO_REPLACE_KEY = True
AUTO_REPLACE_MODEL = True
# 替换模式: 'force'表示强制替换，'missing'表示缺了才补全
KEY_REPLACE_MODE = 'force'
MODEL_REPLACE_MODE = 'force'

def save_config_to_file():
    """保存当前配置到配置文件"""
    config = {
        'base_url': OPENROUTER_BASE_URL,
        'api_key': API_KEY,
        'default_model': DEFAULT_MODEL,
        'auto_replace_key': AUTO_REPLACE_KEY,
        'auto_replace_model': AUTO_REPLACE_MODEL,
        'key_replace_mode': KEY_REPLACE_MODE,
        'model_replace_mode': MODEL_REPLACE_MODE
    }
    
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"配置已保存到文件: {CONFIG_FILE}")
    except Exception as e:
        print(f"保存配置到文件失败: {str(e)}")

def load_config_from_file():
    """从配置文件加载配置"""
    global OPENROUTER_BASE_URL, API_KEY, DEFAULT_MODEL, AUTO_REPLACE_KEY, AUTO_REPLACE_MODEL, KEY_REPLACE_MODE, MODEL_REPLACE_MODE
    
    if not os.path.exists(CONFIG_FILE):
        print(f"配置文件不存在: {CONFIG_FILE}")
        return False
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 更新全局变量
        if 'base_url' in config and config['base_url']:
            OPENROUTER_BASE_URL = config['base_url']
        
        if 'api_key' in config and config['api_key']:
            API_KEY = config['api_key']
        
        if 'default_model' in config and config['default_model']:
            DEFAULT_MODEL = config['default_model']
        
        if 'auto_replace_key' in config:
            AUTO_REPLACE_KEY = config['auto_replace_key']
        
        if 'auto_replace_model' in config:
            AUTO_REPLACE_MODEL = config['auto_replace_model']
        
        if 'key_replace_mode' in config:
            KEY_REPLACE_MODE = config['key_replace_mode']
        
        if 'model_replace_mode' in config:
            MODEL_REPLACE_MODE = config['model_replace_mode']
        
        print(f"从文件加载配置成功: {CONFIG_FILE}")
        print(f"  Base URL: {OPENROUTER_BASE_URL}")
        print(f"  API Key: {'已设置' if API_KEY else '未设置'}")
        print(f"  Default Model: {DEFAULT_MODEL or '未设置'}")
        print(f"  Auto Replace Key: {AUTO_REPLACE_KEY}")
        print(f"  Auto Replace Model: {AUTO_REPLACE_MODEL}")
        print(f"  Key Replace Mode: {KEY_REPLACE_MODE}")
        print(f"  Model Replace Mode: {MODEL_REPLACE_MODE}")
        
        return True
    except Exception as e:
        print(f"从文件加载配置失败: {str(e)}")
        return False

# 尝试获取第一个已配置的API设置
def load_first_config():
    """
    尝试从数据库中获取第一个请求，从中提取API Key和模型信息，
    如果发现有效的API Key和模型，则自动设置为全局默认值
    """
    global API_KEY, DEFAULT_MODEL
    
    # 如果已经有设置过API Key，则不需要再自动设置
    if API_KEY:
        print("已有API Key配置，无需自动加载")
        return
        
    try:
        # 查询最近的请求记录
        recent_requests = RequestModel.query.order_by(RequestModel.id.desc()).limit(20).all()
        
        # 如果没有请求记录，无法自动配置
        if not recent_requests:
            print("没有找到历史请求记录，无法自动配置API Key")
            return
            
        # 寻找同时具有有效API Key和模型的请求
        best_request = None
        api_key_found = None
        model_found = None
        
        # 遍历最近的请求，寻找包含API Key和模型的请求
        for req in recent_requests:
            headers = req.get_headers()
            current_api_key = None
            current_model = None
            
            # 如果有'original'字段，获取原始请求头
            if 'original' in headers and isinstance(headers['original'], dict):
                headers = headers['original']
                
            # 检查Authorization头部
            auth = headers.get('Authorization') or headers.get('authorization')
            if auth and auth.startswith('Bearer ') and len(auth) > 8:  # 确保Bearer后有实际内容
                current_api_key = auth[7:]  # 提取Bearer后的Token
            
            # 检查x-api-key头部
            if not current_api_key:
                api_key = headers.get('x-api-key') or headers.get('X-Api-Key')
                if api_key and len(api_key.strip()) > 0:  # 确保不是空字符串
                    current_api_key = api_key
            
            # 如果找到有效的API Key，尝试获取模型信息
            if current_api_key:
                body = req.get_body()
                if body:
                    # 如果有'original'字段，获取原始请求体
                    if 'original' in body and isinstance(body['original'], dict):
                        body = body['original']
                    
                    if 'model' in body and body['model'] and isinstance(body['model'], str) and len(body['model'].strip()) > 0:
                        current_model = body['model']
                
                # 记录找到的信息
                if current_api_key and not api_key_found:
                    api_key_found = current_api_key
                    
                if current_model and not model_found:
                    model_found = current_model
                
                # 如果同时找到API Key和模型，这是最理想的情况
                if current_api_key and current_model:
                    best_request = req
                    break
        
        # 优先使用同时具有API Key和模型的请求
        if best_request:
            headers = best_request.get_headers()
            body = best_request.get_body()
            
            # 如果有'original'字段，获取原始数据
            if 'original' in headers and isinstance(headers['original'], dict):
                headers = headers['original']
            
            if 'original' in body and isinstance(body['original'], dict):
                body = body['original']
            
            # 设置API Key
            auth = headers.get('Authorization') or headers.get('authorization')
            if auth and auth.startswith('Bearer '):
                API_KEY = auth[7:]
            else:
                API_KEY = headers.get('x-api-key') or headers.get('X-Api-Key')
            
            # 设置模型
            DEFAULT_MODEL = body.get('model')
            
            print(f"自动加载完整配置 - API Key: {API_KEY[:4]}****{API_KEY[-4:]} 和模型: {DEFAULT_MODEL}")
            # 保存配置到文件
            save_config_to_file()
            return
        
        # 次优选择：至少有API Key
        if api_key_found:
            API_KEY = api_key_found
            if model_found:
                DEFAULT_MODEL = model_found
            
            print(f"自动加载部分配置 - API Key: {API_KEY[:4]}****{API_KEY[-4:]}")
            if DEFAULT_MODEL:
                print(f"自动加载模型: {DEFAULT_MODEL}")
            else:
                print("未找到可用的模型配置")
            # 保存配置到文件
            save_config_to_file()
            return
                
        print("没有找到包含有效API Key的历史请求")
            
    except Exception as e:
        print(f"自动加载配置失败: {str(e)}")

# 尝试在模块加载时先加载之前保存的配置，如果没有再从历史记录查找
if not load_config_from_file():
    print("从配置文件加载失败，尝试从历史记录查找配置")
    load_first_config()

# 辅助函数：从请求头和基础URL确定API服务名称
def getApiServiceName(headers, base_url):
    """
    从请求头和基础URL确定API服务名称
    :param headers: 请求头字典
    :param base_url: 基础URL
    :return: API服务名称
    """
    # 根据请求头中的Host确定服务
    host = headers.get('Host', '') or headers.get('host', '')
    if host:
        if 'openrouter.ai' in host:
            return 'OpenRouter'
        if 'siliconflow.cn' in host:
            return '硅基流动'
        if 'deepseek.com' in host:
            return 'DeepSeek'
        if 'minimax.chat' in host:
            return 'MiniMax'
        if 'bigmodel.cn' in host:
            return '智谱'
        if 'dashscope.aliyuncs.com' in host:
            return '千问'
        if 'openai.com' in host:
            return 'OpenAI'
    
    # 根据基础URL确定服务
    if base_url:
        if 'openrouter.ai' in base_url:
            return 'OpenRouter'
        if 'siliconflow.cn' in base_url:
            return '硅基流动'
        if 'deepseek.com' in base_url:
            return 'DeepSeek'
        if 'minimax.chat' in base_url:
            return 'MiniMax'
        if 'bigmodel.cn' in base_url:
            return '智谱'
        if 'dashscope.aliyuncs.com' in base_url:
            return '千问'
        if 'openai.com' in base_url:
            return 'OpenAI'
    
    # 默认返回未知
    return '未知服务'

# 辅助函数：从请求体中获取模型名称
def getModelName(json_data):
    """
    从请求体中获取模型名称
    :param json_data: 请求体JSON数据
    :return: 模型名称或None
    """
    if not json_data:
        return None
        
    # 处理字典格式
    if isinstance(json_data, dict):
        # 处理带有original和modified属性的格式
        if 'original' in json_data and isinstance(json_data['original'], dict):
            return json_data['original'].get('model')
            
        # 处理常规格式
        return json_data.get('model')
    
    return None

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = AdminUser.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            if user.force_change:
                return redirect(url_for('main.change_password'))
            return redirect(url_for('main.index'))
        else:
            flash('用户名或密码错误')
    return render_template('login.html')

@main_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))

@main_bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'admin_logged_in' not in session:
        return redirect(url_for('main.login'))
    user = AdminUser.query.filter_by(username=session['admin_username']).first()
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not bcrypt.check_password_hash(user.password_hash, old_password):
            flash('原密码错误')
        elif new_password != confirm_password:
            flash('两次输入的新密码不一致')
        elif new_password == 'admin':
            flash('新密码不能为 admin')
        else:
            user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
            user.force_change = False
            db.session.commit()
            flash('密码修改成功，请重新登录')
            return redirect(url_for('main.logout'))
    return render_template('change_password.html', force_change=user.force_change)

from functools import wraps

def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

# 修改首页路由，增加登录校验
@main_bp.route('/')
@admin_login_required
def index():
    return render_template('index.html')

@main_bp.route('/api/settings', methods=['POST'])
def save_settings():
    """保存API设置的端点"""
    global OPENROUTER_BASE_URL, API_KEY, DEFAULT_MODEL, AUTO_REPLACE_KEY, AUTO_REPLACE_MODEL, KEY_REPLACE_MODE, MODEL_REPLACE_MODE
    
    data = request.get_json()
    if not data:
        return jsonify({'message': '无效的请求数据'}), 400
    
    # 更新前的值，用于记录变更
    old_base_url = OPENROUTER_BASE_URL
    old_api_key = API_KEY
    old_default_model = DEFAULT_MODEL
    old_auto_replace_key = AUTO_REPLACE_KEY
    old_auto_replace_model = AUTO_REPLACE_MODEL
    old_key_replace_mode = KEY_REPLACE_MODE
    old_model_replace_mode = MODEL_REPLACE_MODE
    
    # 更新全局变量
    if 'base_url' in data and data['base_url']:
        OPENROUTER_BASE_URL = data['base_url']
    
    if 'api_key' in data:
        API_KEY = data['api_key']
    
    if 'default_model' in data:
        DEFAULT_MODEL = data['default_model']
    
    # 更新自动替换配置
    if 'auto_replace_key' in data:
        AUTO_REPLACE_KEY = data['auto_replace_key']
    
    if 'auto_replace_model' in data:
        AUTO_REPLACE_MODEL = data['auto_replace_model']
    
    # 更新替换模式配置
    if 'key_replace_mode' in data:
        KEY_REPLACE_MODE = data['key_replace_mode']
    
    if 'model_replace_mode' in data:
        MODEL_REPLACE_MODE = data['model_replace_mode']
    
    # 记录变更
    print(f"设置已更新:")
    print(f"  Base URL: {old_base_url} -> {OPENROUTER_BASE_URL}")
    print(f"  API Key: {'已设置' if old_api_key else '未设置'} -> {'已设置' if API_KEY else '未设置'}")
    print(f"  Default Model: {old_default_model or '未设置'} -> {DEFAULT_MODEL or '未设置'}")
    print(f"  Auto Replace Key: {old_auto_replace_key} -> {AUTO_REPLACE_KEY}")
    print(f"  Auto Replace Model: {old_auto_replace_model} -> {AUTO_REPLACE_MODEL}")
    print(f"  Key Replace Mode: {old_key_replace_mode} -> {KEY_REPLACE_MODE}")
    print(f"  Model Replace Mode: {old_model_replace_mode} -> {MODEL_REPLACE_MODE}")
    
    # 保存配置到文件
    save_config_to_file()
    
    # 对替换模式进行映射转换
    key_mode_text = '强制替换' if KEY_REPLACE_MODE == 'force' else '缺少时补全'
    model_mode_text = '强制替换' if MODEL_REPLACE_MODE == 'force' else '缺少时补全'
    
    return jsonify({
        'message': '设置已保存',
        'base_url': OPENROUTER_BASE_URL,
        'api_key': API_KEY[:4] + '****' + API_KEY[-4:] if API_KEY else None,
        'default_model': DEFAULT_MODEL,
        'auto_replace_key': AUTO_REPLACE_KEY,
        'auto_replace_model': AUTO_REPLACE_MODEL,
        'key_replace_mode': KEY_REPLACE_MODE,
        'model_replace_mode': MODEL_REPLACE_MODE,
        'key_replace_mode_text': key_mode_text,
        'model_replace_mode_text': model_mode_text
    })

@main_bp.route('/api/settings', methods=['GET'])
def get_settings():
    """获取当前API设置的端点"""
    global OPENROUTER_BASE_URL, API_KEY, DEFAULT_MODEL, AUTO_REPLACE_KEY, AUTO_REPLACE_MODEL, KEY_REPLACE_MODE, MODEL_REPLACE_MODE
    
    # 打印当前全局变量值以便调试
    print(f"DEBUG - 当前服务器设置:")
    print(f"  OPENROUTER_BASE_URL = {OPENROUTER_BASE_URL}")
    print(f"  API_KEY = {'已设置' if API_KEY else '未设置'}")
    print(f"  DEFAULT_MODEL = {DEFAULT_MODEL or '未设置'}")
    print(f"  AUTO_REPLACE_KEY = {AUTO_REPLACE_KEY}")
    print(f"  AUTO_REPLACE_MODEL = {AUTO_REPLACE_MODEL}")
    print(f"  KEY_REPLACE_MODE = {KEY_REPLACE_MODE}")
    print(f"  MODEL_REPLACE_MODE = {MODEL_REPLACE_MODE}")
    
    # 对替换模式进行映射转换
    key_mode_text = '强制替换' if KEY_REPLACE_MODE == 'force' else '缺少时补全'
    model_mode_text = '强制替换' if MODEL_REPLACE_MODE == 'force' else '缺少时补全'
    
    return jsonify({
        'base_url': OPENROUTER_BASE_URL,
        'api_key': API_KEY[:4] + '****' + API_KEY[-4:] if API_KEY else None,
        'default_model': DEFAULT_MODEL,
        'auto_replace_key': AUTO_REPLACE_KEY,
        'auto_replace_model': AUTO_REPLACE_MODEL,
        'key_replace_mode': KEY_REPLACE_MODE,
        'model_replace_mode': MODEL_REPLACE_MODE,
        'key_replace_mode_text': key_mode_text,
        'model_replace_mode_text': model_mode_text
    })

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
        'api_service': req.api_service,
        'model': req.model,
        'original_url': req.original_url,
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

@main_bp.route('/api/requests/<int:request_id>', methods=['DELETE'])
def delete_request(request_id):
    """删除单个请求记录的API"""
    req = RequestModel.query.get_or_404(request_id)
    
    # 先删除关联的响应记录
    for resp in req.responses:
        db.session.delete(resp)
    
    # 再删除请求记录
    db.session.delete(req)
    db.session.commit()
    
    return jsonify({'message': '请求记录已成功删除'})

@main_bp.route('/api/requests', methods=['DELETE'])
def delete_all_requests():
    """清空所有请求记录的API"""
    # 先删除所有响应记录
    ResponseModel.query.delete()
    
    # 再删除所有请求记录
    RequestModel.query.delete()
    
    db.session.commit()
    
    return jsonify({'message': '所有请求记录已成功清空'})

@main_bp.route('/api/select_model', methods=['POST'])
def select_current_model():
    """快速切换当前使用的模型的API端点"""
    global DEFAULT_MODEL, MODEL_REPLACE_MODE, AUTO_REPLACE_MODEL
    
    data = request.get_json()
    if not data:
        return jsonify({'message': '无效的请求数据'}), 400
    
    old_model = DEFAULT_MODEL
    old_mode = MODEL_REPLACE_MODE
    
    # 更新模型相关设置
    if 'model' in data:
        DEFAULT_MODEL = data['model']
    
    if 'replace_mode' in data:
        MODEL_REPLACE_MODE = data['replace_mode']
        
    if 'auto_replace' in data:
        AUTO_REPLACE_MODEL = data['auto_replace']
    
    print(f"模型已切换: {old_model} -> {DEFAULT_MODEL}")
    print(f"模型替换模式: {old_mode} -> {MODEL_REPLACE_MODE}")
    print(f"自动替换模型: {AUTO_REPLACE_MODEL}")
    
    # 保存配置到文件
    save_config_to_file()
    
    # 返回当前设置状态
    mode_text = '强制替换' if MODEL_REPLACE_MODE == 'force' else '缺少时补全'
    return jsonify({
        'message': '已切换模型',
        'model': DEFAULT_MODEL,
        'replace_mode': MODEL_REPLACE_MODE,
        'replace_mode_text': mode_text,
        'auto_replace': AUTO_REPLACE_MODEL
    })

@main_bp.route('/api/select_key', methods=['POST'])
def select_current_api_key():
    """快速切换当前使用的API Key的API端点"""
    global API_KEY, KEY_REPLACE_MODE, AUTO_REPLACE_KEY
    
    data = request.get_json()
    if not data:
        return jsonify({'message': '无效的请求数据'}), 400
    
    old_key = API_KEY
    old_mode = KEY_REPLACE_MODE
    
    # 更新API Key相关设置
    if 'api_key' in data:
        API_KEY = data['api_key']
    
    if 'replace_mode' in data:
        KEY_REPLACE_MODE = data['replace_mode']
        
    if 'auto_replace' in data:
        AUTO_REPLACE_KEY = data['auto_replace']
    
    print(f"API Key已切换: {old_key[:4] + '****' + old_key[-4:] if old_key else '未设置'} -> {API_KEY[:4] + '****' + API_KEY[-4:] if API_KEY else '未设置'}")
    print(f"API Key替换模式: {old_mode} -> {KEY_REPLACE_MODE}")
    print(f"自动替换API Key: {AUTO_REPLACE_KEY}")
    
    # 保存配置到文件
    save_config_to_file()
    
    # 返回当前设置状态
    mode_text = '强制替换' if KEY_REPLACE_MODE == 'force' else '缺少时补全'
    return jsonify({
        'message': '已切换API Key',
        'api_key': API_KEY[:4] + '****' + API_KEY[-4:] if API_KEY else None,
        'replace_mode': KEY_REPLACE_MODE,
        'replace_mode_text': mode_text,
        'auto_replace': AUTO_REPLACE_KEY
    })

# 模型列表路由
@main_bp.route('/api/models')
def get_models():
    """获取可用的模型列表"""
    global API_KEY, OPENROUTER_BASE_URL
    
    # 检查API Key是否存在
    if not API_KEY:
        return jsonify({
            "success": False,
            "error": "未设置API Key",
            "data": []
        }), 400
    
    # 清理API Key，确保没有额外的空格
    clean_api_key = API_KEY.strip()
    
    # 确保API Key没有重复的Bearer前缀
    if clean_api_key.lower().startswith("bearer "):
        auth_header = clean_api_key
    else:
        auth_header = f"Bearer {clean_api_key}"
    
    # 构建请求URL
    models_url = f"{OPENROUTER_BASE_URL}/models"
    
    print(f"获取模型列表 - URL: {models_url}")
    print(f"Authorization: {auth_header[:10]}...{auth_header[-4:] if len(auth_header) > 14 else ''}")
    
    try:
        # 发起请求获取模型列表
        response = requests.get(
            models_url,
            headers={"Authorization": auth_header}
        )
        
        # 检查响应状态
        if response.status_code == 200:
            # 直接返回OpenRouter的完整响应
            models_data = response.json()
            return jsonify({
                "success": True,
                "data": models_data.get("data", [])
            })
        else:
            # 处理错误响应
            error_message = f"获取模型列表失败: {response.status_code}"
            try:
                error_json = response.json()
                if isinstance(error_json, dict):
                    error_message = f"获取模型列表失败: {error_json}"
            except:
                pass
                
            print(f"模型列表请求失败: {error_message}")
            
            return jsonify({
                "success": False,
                "error": error_message,
                "data": []
            }), response.status_code
            
    except Exception as e:
        # 处理请求异常
        print(f"请求模型列表异常: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"获取模型列表时发生错误: {str(e)}",
            "data": []
        }), 500

# 代理服务路由
proxy_bp = Blueprint('proxy', __name__, url_prefix='/api/v1')

def make_proxy_request(method, path, headers, json_data=None):
    """处理普通请求的代理函数"""
    global API_KEY, DEFAULT_MODEL, AUTO_REPLACE_KEY, AUTO_REPLACE_MODEL, KEY_REPLACE_MODE, MODEL_REPLACE_MODE
    
    print(f"请求处理 - 替换模式: Key={KEY_REPLACE_MODE}, Model={MODEL_REPLACE_MODE}")
    print(f"自动替换: Key={AUTO_REPLACE_KEY}, Model={AUTO_REPLACE_MODEL}")
    print(f"当前服务器API Key: {API_KEY[:4] + '****' + API_KEY[-4:] if API_KEY else '未设置'}")
    print(f"当前服务器默认模型: {DEFAULT_MODEL or '未设置'}")
    
    # 保存原始请求头和主体，用于前端对比显示
    original_headers = dict(headers)
    original_json_data = copy.deepcopy(json_data) if json_data else None
    
    # 转发请求到配置的API服务
    start_time = time.time()
    url = f"{OPENROUTER_BASE_URL}{path}"
    
    proxied_headers = dict(headers)
    # 移除可能导致问题的头部
    if 'Host' in proxied_headers:
        del proxied_headers['Host']
        
    print(f"原始请求头: {proxied_headers}")
    
    # 处理API Key替换 - 改进检查逻辑，不区分大小写
    # 创建请求头的小写映射，用于检查
    headers_lower = {k.lower(): k for k in proxied_headers.keys()}
    print(f"所有请求头: {list(proxied_headers.keys())}")
    print(f"所有请求头(小写): {list(headers_lower.keys())}")
    
    # 检查是否存在任何形式的API Key头
    has_api_key = False
    api_key_headers = []
    
    # 检查'authorization'头
    if 'authorization' in headers_lower:
        actual_key = headers_lower['authorization']
        has_api_key = True
        api_key_headers.append(actual_key)
        print(f"找到Authorization头: {actual_key} = {proxied_headers[actual_key]}")
    
    # 检查'x-api-key'头
    if 'x-api-key' in headers_lower:
        actual_key = headers_lower['x-api-key']
        has_api_key = True
        api_key_headers.append(actual_key)
        print(f"找到X-Api-Key头: {actual_key} = {proxied_headers[actual_key]}")
            
    print(f"请求是否包含API Key: {has_api_key}, 找到的API Key头: {api_key_headers}")
    
    print(f"**** 强制模式：无条件替换API Key ****")
    
    # 更彻底地清理所有可能的请求头 - 无论大小写
    headers_to_delete = []
    for k in list(proxied_headers.keys()):
        if k.lower() in ['authorization', 'x-api-key'] or (k in api_key_headers):
            headers_to_delete.append(k)
        
    for k in headers_to_delete:
        # 记录即将删除的头及其值
        print(f"删除原有的Key: {k} = {proxied_headers[k]}")
        del proxied_headers[k]
        
    # 设置新的API Key - 使用标准格式
    if API_KEY:
        proxied_headers['Authorization'] = f'Bearer {API_KEY}'
        print(f"设置新的API Key: Bearer {API_KEY[:4]}...{API_KEY[-4:]}")
        print(f"完成API Key设置，API Key被成功替换!")
    
    # 处理模型替换
    if method == 'POST' and json_data:
        has_model = 'model' in json_data
        original_model = json_data.get('model')
        print(f"请求是否包含模型: {has_model}, 原始模型: {original_model}")
        
        if AUTO_REPLACE_MODEL and DEFAULT_MODEL:
            print(f"模型替换条件: 强制模式={MODEL_REPLACE_MODE=='force'}, 缺失时才替换={MODEL_REPLACE_MODE=='missing' and not has_model}")
            
            if MODEL_REPLACE_MODE == 'force' or (MODEL_REPLACE_MODE == 'missing' and not has_model):
                print(f"执行模型替换: 模式={MODEL_REPLACE_MODE}, 原始模型={'存在: '+original_model if has_model else '不存在'}")
                # 强制模式：直接替换；缺失模式：只有在没有模型时才替换
                old_model = json_data.get('model', '未设置')
                json_data['model'] = DEFAULT_MODEL
                print(f"模型替换: {old_model} -> {DEFAULT_MODEL}")
            else:
                print(f"不执行模型替换: 模式={MODEL_REPLACE_MODE}, 有模型={has_model}")
        else:
            print(f"模型替换未触发: AUTO_REPLACE_MODEL={AUTO_REPLACE_MODEL}, DEFAULT_MODEL是否存在={DEFAULT_MODEL is not None}")
    
    # 在替换后创建新的请求记录
    db_request = RequestModel(
        method=method,
        path=path,
        api_service=getApiServiceName(original_headers, OPENROUTER_BASE_URL),
        model=getModelName(original_json_data),
        original_url=OPENROUTER_BASE_URL
    )
    # 保存原始请求和修改后的请求以便比较
    db_request.set_headers({
        'original': original_headers,
        'modified': proxied_headers
    })
    if json_data:
        db_request.set_body({
            'original': original_json_data,
            'modified': json_data
        })
    
    db.session.add(db_request)
    db.session.commit()
                
    # 打印最终请求信息
    print(f"最终请求URL: {url}")
    print(f"最终请求头: {proxied_headers}")
    
    # 增强调试输出，检查API Key是否真的被替换了
    if 'Authorization' in proxied_headers:
        auth_key = proxied_headers['Authorization']
        print(f"实际发送请求的Authorization头: {auth_key}")
        print(f"已设置的API Key是否生效: {API_KEY and auth_key == f'Bearer {API_KEY}'}")
    else:
        print(f"警告: 最终请求中没有Authorization头!")
        for header_key in proxied_headers.keys():
            if header_key.lower() in ['authorization', 'x-api-key']:
                print(f"但找到了类似的头: {header_key} = {proxied_headers[header_key]}")
    
    if method == 'POST' and json_data:
        print(f"最终请求体: {json_data}")
        
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
    global API_KEY, DEFAULT_MODEL, AUTO_REPLACE_KEY, AUTO_REPLACE_MODEL, KEY_REPLACE_MODE, MODEL_REPLACE_MODE
    
    print(f"流式请求处理 - 替换模式: Key={KEY_REPLACE_MODE}, Model={MODEL_REPLACE_MODE}")
    print(f"流式自动替换: Key={AUTO_REPLACE_KEY}, Model={AUTO_REPLACE_MODEL}")
    print(f"当前服务器API Key: {API_KEY[:4] + '****' + API_KEY[-4:] if API_KEY else '未设置'}")
    print(f"当前服务器默认模型: {DEFAULT_MODEL or '未设置'}")
    
    # 保存原始请求头和主体，用于前端对比显示
    original_headers = dict(headers)
    original_json_data = copy.deepcopy(json_data) if json_data else None
    
    # 转发请求到配置的API服务
    start_time = time.time()
    url = f"{OPENROUTER_BASE_URL}{path}"
    
    proxied_headers = dict(headers)
    # 移除可能导致问题的头部
    if 'Host' in proxied_headers:
        del proxied_headers['Host']
        
    print(f"原始流式请求头: {proxied_headers}")
    
    # 处理API Key替换 - 改进检查逻辑，不区分大小写
    # 创建请求头的小写映射，用于检查
    headers_lower = {k.lower(): k for k in proxied_headers.keys()}
    print(f"所有流式请求头: {list(proxied_headers.keys())}")
    print(f"所有流式请求头(小写): {list(headers_lower.keys())}")
    
    # 检查是否存在任何形式的API Key头
    has_api_key = False
    api_key_headers = []
    
    # 检查'authorization'头
    if 'authorization' in headers_lower:
        actual_key = headers_lower['authorization']
        has_api_key = True
        api_key_headers.append(actual_key)
        print(f"找到流式Authorization头: {actual_key} = {proxied_headers[actual_key]}")
    
    # 检查'x-api-key'头
    if 'x-api-key' in headers_lower:
        actual_key = headers_lower['x-api-key']
        has_api_key = True
        api_key_headers.append(actual_key)
        print(f"找到流式X-Api-Key头: {actual_key} = {proxied_headers[actual_key]}")
    
    print(f"流式请求是否包含API Key: {has_api_key}, 找到的API Key头: {api_key_headers}")
    
    print(f"**** 强制模式：无条件替换API Key ****")
    
    # 更彻底地清理所有可能的请求头 - 无论大小写
    headers_to_delete = []
    for k in list(proxied_headers.keys()):
        if k.lower() in ['authorization', 'x-api-key'] or (k in api_key_headers):
            headers_to_delete.append(k)
        
    for k in headers_to_delete:
        # 记录即将删除的头及其值
        print(f"删除流式请求原有的Key: {k} = {proxied_headers[k]}")
        del proxied_headers[k]
        
    # 设置新的API Key - 使用标准格式
    if API_KEY:
        proxied_headers['Authorization'] = f'Bearer {API_KEY}'
        print(f"设置流式请求新的API Key: Bearer {API_KEY[:4]}...{API_KEY[-4:]}")
        print(f"完成流式请求API Key设置，API Key被成功替换!")
    
    # 处理模型替换
    if method == 'POST' and json_data:
        has_model = 'model' in json_data
        original_model = json_data.get('model')
        print(f"流式请求是否包含模型: {has_model}, 原始模型: {original_model}")
        
        if AUTO_REPLACE_MODEL and DEFAULT_MODEL:
            print(f"模型替换条件: 强制模式={MODEL_REPLACE_MODE=='force'}, 缺失时才替换={MODEL_REPLACE_MODE=='missing' and not has_model}")
            
            if MODEL_REPLACE_MODE == 'force' or (MODEL_REPLACE_MODE == 'missing' and not has_model):
                print(f"执行流式模型替换: 模式={MODEL_REPLACE_MODE}, 原始模型={'存在: '+original_model if has_model else '不存在'}")
                # 强制模式：直接替换；缺失模式：只有在没有模型时才替换
                old_model = json_data.get('model', '未设置')
                json_data['model'] = DEFAULT_MODEL
                print(f"流式模型替换: {old_model} -> {DEFAULT_MODEL}")
            else:
                print(f"不执行流式模型替换: 模式={MODEL_REPLACE_MODE}, 有模型={has_model}")
        else:
            print(f"流式模型替换未触发: AUTO_REPLACE_MODEL={AUTO_REPLACE_MODEL}, DEFAULT_MODEL是否存在={DEFAULT_MODEL is not None}")
    
    # 在替换后创建新的请求记录
    db_request = RequestModel(
        method=method,
        path=path,
        api_service=getApiServiceName(original_headers, OPENROUTER_BASE_URL),
        model=getModelName(original_json_data),
        original_url=OPENROUTER_BASE_URL
    )
    # 保存原始请求和修改后的请求以便比较
    db_request.set_headers({
        'original': original_headers,
        'modified': proxied_headers
    })
    if json_data:
        db_request.set_body({
            'original': original_json_data,
            'modified': json_data
        })
    
    db.session.add(db_request)
    db.session.commit()
    
    # 打印最终请求信息
    print(f"最终流式请求URL: {url}")
    print(f"最终流式请求头: {proxied_headers}")
    
    # 增强调试输出，检查API Key是否真的被替换了
    if 'Authorization' in proxied_headers:
        auth_key = proxied_headers['Authorization']
        print(f"实际发送流式请求的Authorization头: {auth_key}")
        print(f"已设置的API Key是否生效: {API_KEY and auth_key == f'Bearer {API_KEY}'}")
    else:
        print(f"警告: 最终流式请求中没有Authorization头!")
        for header_key in proxied_headers.keys():
            if header_key.lower() in ['authorization', 'x-api-key']:
                print(f"但找到了类似的头: {header_key} = {proxied_headers[header_key]}")
    
    if method == 'POST' and json_data:
        print(f"最终流式请求体: {json_data}")
        
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
        
        # 创建一个响应头的副本，并确保删除Transfer-Encoding以避免重复
        response_headers = dict(resp.headers)
        if 'Transfer-Encoding' in response_headers:
            del response_headers['Transfer-Encoding']
        
        return Response(
            stream_with_context(generate()),
            status=resp.status_code,
            headers=response_headers
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