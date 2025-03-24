from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    
    # 配置
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), '../data.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 初始化数据库
    db.init_app(app)
    
    # 注册蓝图
    from app.routes import main_bp, proxy_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(proxy_bp)
    
    # 确保数据库存在
    with app.app_context():
        db.create_all()
    
    return app 