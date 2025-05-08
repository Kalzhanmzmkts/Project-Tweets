from flask import Flask, render_template, session
from app.extensions import db, login_manager
from app.auth import auth_bp
from app.main import main_bp
from app.tweets import tweets_bp
from flask_bootstrap import Bootstrap
from flask_migrate import Migrate
from flask_login import current_user
from datetime import datetime, timedelta
import os


def create_app():
    app: Flask = Flask(__name__)
    app.secret_key = 'ваш-секретный-ключ'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tweets.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
    app.permanent_session_lifetime = timedelta(minutes=30)

    # Инициализация расширений
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # Убедитесь, что такой маршрут существует
    Bootstrap(app)
    Migrate(app, db)

    from app.models import User
    from app.models import Tweet, Comment

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.before_request
    def update_last_seen():
        if current_user.is_authenticated:
            current_user.last_seen = datetime.utcnow()
            db.session.commit()

    @app.before_request
    def make_session_permanent():
        session.permanent = True

    @app.errorhandler(404)
    def not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('403.html'), 403

    # Регистрируем блюпринты с url_prefix
    app.register_blueprint(auth_bp, url_prefix='/auth')  # Указан url_prefix
    app.register_blueprint(main_bp, url_prefix='/main')
    app.register_blueprint(tweets_bp, url_prefix='/tweets')

    return app
