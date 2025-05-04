from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()

def create_app():
    app = Flask(__name__)
    
    # 配置
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), '../data.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = 'your_secret_key_here'
    
    # 初始化数据库
    db.init_app(app)
    bcrypt.init_app(app)
    
    # 这里再导入 models，避免循环引用
    from app.models import AdminUser
    # 注册蓝图
    from app.routes import main_bp, proxy_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(proxy_bp)
    
    # 确保数据库存在
    with app.app_context():
        db.create_all()
        # 检查是否已有管理员账号
        if not AdminUser.query.filter_by(username='admin').first():
            admin = AdminUser(
                username='admin',
                password_hash=bcrypt.generate_password_hash('admin').decode('utf-8'),
                force_change=True
            )
            db.session.add(admin)
            db.session.commit()
    
    return app 