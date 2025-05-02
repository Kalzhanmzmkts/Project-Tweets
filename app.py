from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_bootstrap import Bootstrap5
from flask_migrate import Migrate
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from wtforms import StringField, PasswordField, TextAreaField, FileField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo
from datetime import datetime
import os

# --- App Configuration ---
app = Flask(__name__)
app.secret_key = 'ваш-секретный-ключ'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tweets.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# --- Extensions ---
db = SQLAlchemy(app)
bootstrap = Bootstrap5(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
migrate = Migrate(app, db)

# --- Forms ---
class RegistrationForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Подтвердите пароль', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Зарегистрироваться')

class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')

class TweetForm(FlaskForm):
    content = TextAreaField('Текст твита', validators=[DataRequired(), Length(max=280)])
    image = FileField('Изображение', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Только изображения!')])
    submit = SubmitField('Опубликовать')

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    profile_image = db.Column(db.String(100))
    tweets = db.relationship('Tweet', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Tweet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(280), nullable=False)
    image = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    likes = db.relationship('Like', backref='tweet', lazy=True, cascade='all, delete-orphan')

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tweet_id = db.Column(db.Integer, db.ForeignKey('tweet.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- Login Manager ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Before Request ---
@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

# --- Helpers ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_uploaded_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return filename
    return None

# --- Routes ---
@app.route('/')
def home():
    tweets = Tweet.query.order_by(Tweet.created_at.desc()).all()
    return render_template('home.html', tweets=tweets)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            profile_image=None
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Регистрация прошла успешно!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(request.args.get('next') or url_for('home'))
        flash('Неверное имя пользователя или пароль', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('home'))

@app.route('/profile')
@login_required
def profile():
    tweets = Tweet.query.filter_by(user_id=current_user.id).order_by(Tweet.created_at.desc()).all()
    return render_template('profile.html', tweets=tweets)

@app.route('/tweet/new', methods=['GET', 'POST'])
@login_required
def new_tweet():
    form = TweetForm()
    if form.validate_on_submit():
        filename = save_uploaded_file(form.image.data) if form.image.data else None
        tweet = Tweet(content=form.content.data, user_id=current_user.id, image=filename)
        db.session.add(tweet)
        db.session.commit()
        flash('Твит создан!', 'success')
        return redirect(url_for('home'))
    return render_template('create_tweet.html', form=form)

@app.route('/tweet/<int:tweet_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_tweet(tweet_id):
    tweet = Tweet.query.get_or_404(tweet_id)
    if tweet.author != current_user:
        abort(403)
    form = TweetForm()
    if form.validate_on_submit():
        tweet.content = form.content.data
        if form.image.data:
            if tweet.image:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], tweet.image))
                except Exception:
                    pass
            tweet.image = save_uploaded_file(form.image.data)
        db.session.commit()
        flash('Твит обновлен!', 'success')
        return redirect(url_for('profile'))
    elif request.method == 'GET':
        form.content.data = tweet.content
    return render_template('edit_tweet.html', form=form, tweet=tweet)

@app.route('/tweet/<int:tweet_id>/delete', methods=['POST'])
@login_required
def delete_tweet(tweet_id):
    tweet = Tweet.query.get_or_404(tweet_id)
    if tweet.author != current_user:
        abort(403)
    if tweet.image:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], tweet.image))
        except Exception:
            pass
    db.session.delete(tweet)
    db.session.commit()
    flash('Твит удален!', 'success')
    return redirect(url_for('profile'))

@app.route('/tweet/<int:tweet_id>/like', methods=['POST'])
@login_required
def like_tweet(tweet_id):
    tweet = Tweet.query.get_or_404(tweet_id)
    if tweet.user_id == current_user.id:
        abort(403)
    existing_like = Like.query.filter_by(user_id=current_user.id, tweet_id=tweet.id).first()
    if existing_like:
        db.session.delete(existing_like)
        flash('Вы убрали лайк', 'info')
    else:
        db.session.add(Like(user_id=current_user.id, tweet_id=tweet.id))
        flash('Вам понравился этот твит!', 'success')
    db.session.commit()
    return redirect(request.referrer or url_for('home'))

# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

# --- Run App ---
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(debug=True)
