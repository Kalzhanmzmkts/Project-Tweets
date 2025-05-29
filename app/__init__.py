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


class Application:
    def __init__(self):
        self.app = Flask(__name__)
        self.configure_app()
        self.init_extensions()
        self.register_blueprints()
        self.setup_callbacks()

    def configure_app(self):
        self.app.secret_key = 'key'
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tweets.db'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        self.app.config['UPLOAD_FOLDER'] = os.path.join(self.app.root_path, 'static', 'uploads')
        self.app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
        self.app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
        self.app.permanent_session_lifetime = timedelta(minutes=30)

    def init_extensions(self):
        db.init_app(self.app)
        login_manager.init_app(self.app)
        login_manager.login_view = 'auth.login'
        Bootstrap(self.app)
        Migrate(self.app, db)

    def register_blueprints(self):
        from app.auth import auth_bp
        from app.main import main_bp
        from app.tweets import tweets_bp

        self.app.register_blueprint(auth_bp, url_prefix='/auth')
        self.app.register_blueprint(main_bp, url_prefix='/main')
        self.app.register_blueprint(tweets_bp, url_prefix='/tweets')

    def setup_callbacks(self):
        from app.models import User
        from flask_login import current_user
        from flask import session, render_template

        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))

        @self.app.before_request
        def update_last_seen():
            if current_user.is_authenticated:
                current_user.last_seen = datetime.utcnow()
                db.session.commit()

        @self.app.before_request
        def make_session_permanent():
            session.permanent = True

        @self.app.errorhandler(404)
        def not_found(e):
            return render_template('404.html'), 404

        @self.app.errorhandler(403)
        def forbidden(e):
            return render_template('403.html'), 403

    def get_app(self):
        return self.app


def create_app():
    application = Application()
    return application.get_app()
