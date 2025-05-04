from app import db
from datetime import datetime
import json

class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    path = db.Column(db.String)
    method = db.Column(db.String)
    headers = db.Column(db.Text)  # 存储为JSON字符串
    body = db.Column(db.Text)  # 存储为JSON字符串
    api_service = db.Column(db.String)  # 存储API服务名称
    model = db.Column(db.String)  # 存储模型名称
    original_url = db.Column(db.String)  # 存储原始完整URL
    responses = db.relationship('Response', backref='request', lazy=True)
    
    def set_headers(self, headers_dict):
        self.headers = json.dumps(dict(headers_dict))
        
    def get_headers(self):
        return json.loads(self.headers) if self.headers else {}
    
    def set_body(self, body_dict):
        self.body = json.dumps(body_dict)
        
    def get_body(self):
        return json.loads(self.body) if self.body else {}

class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('request.id'))
    status_code = db.Column(db.Integer)
    headers = db.Column(db.Text)  # 存储为JSON字符串
    body = db.Column(db.Text)
    is_stream = db.Column(db.Boolean, default=False)
    time_taken = db.Column(db.Float)  # 以秒为单位
    
    def set_headers(self, headers_dict):
        self.headers = json.dumps(dict(headers_dict))
        
    def get_headers(self):
        return json.loads(self.headers) if self.headers else {}

class AdminUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    force_change = db.Column(db.Boolean, default=True)  # 首次登录后强制改密 