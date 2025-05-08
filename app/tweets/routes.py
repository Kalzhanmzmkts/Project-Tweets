from datetime import datetime

from app.extensions import db
from flask import render_template, redirect, url_for, request, flash, abort, current_app
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from werkzeug.utils import secure_filename
from wtforms import TextAreaField, FileField, SubmitField
from wtforms.validators import DataRequired, Length
import os
from app.models import Tweet, Comment
from app.tweets import tweets_bp



class TweetForm(FlaskForm):
    content = TextAreaField('Текст твита', validators=[DataRequired(), Length(max=280)])
    image = FileField('Изображение', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Только изображения!')])
    submit = SubmitField('Опубликовать')


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tweet_id = db.Column(db.Integer, db.ForeignKey('tweet.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CommentForm(FlaskForm):
    content = TextAreaField('Комментарий', validators=[DataRequired(), Length(max=280)])
    submit = SubmitField('Отправить')





def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def save_uploaded_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return filename
    return None


@tweets_bp.route('/tweet/new', methods=['GET', 'POST'])
@login_required
def new_tweet():
    form = TweetForm()
    if form.validate_on_submit():
        filename = save_uploaded_file(form.image.data) if form.image.data else None
        tweet = Tweet(content=form.content.data, user_id=current_user.id, image=filename)
        db.session.add(tweet)
        db.session.commit()
        flash('Твит создан!', 'success')
        return redirect(url_for('main.home'))
    return render_template('create_tweet.html', form=form)


@tweets_bp.route('/tweet/<int:tweet_id>/edit', methods=['GET', 'POST'])
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
        return redirect(url_for('main.profile'))
    elif request.method == 'GET':
        form.content.data = tweet.content
    return render_template('edit_tweet.html', form=form, tweet=tweet)


@tweets_bp.route('/tweet/<int:tweet_id>/like', methods=['POST'])
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
    return redirect(request.referrer or url_for('main.home'))


@tweets_bp.route('/tweet/<int:tweet_id>/delete', methods=['POST'])
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
    return redirect(url_for('main.profile'))


@tweets_bp.route('/tweet/<int:tweet_id>/comment', methods=['POST'])
@login_required
def add_comment(tweet_id):
    tweet = Tweet.query.get_or_404(tweet_id)
    comment_content = request.form.get('comment')

    if comment_content:
        new_comment = Comment(content=comment_content, user_id=current_user.id, tweet_id=tweet.id)
        db.session.add(new_comment)
        db.session.commit()
        flash('Комментарий добавлен!', 'success')

    return redirect(url_for('tweets.view_tweet', tweet_id=tweet.id))


@tweets_bp.route('/tweet/<int:tweet_id>', methods=['GET', 'POST'])
@login_required
def view_tweet(tweet_id):
    tweet = Tweet.query.get_or_404(tweet_id)

    # Обработка добавления комментария
    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            # Создание нового комментария
            comment = Comment(content=content, tweet_id=tweet.id, user_id=current_user.id)
            db.session.add(comment)
            db.session.commit()
            flash('Комментарий добавлен!', 'success')
            return redirect(url_for('tweets.view_tweet', tweet_id=tweet.id))

    return render_template('view_tweet.html', tweet=tweet)


@tweets_bp.route('/tweet/<int:tweet_id>/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(tweet_id, comment_id):
    # Получаем твит
    tweet = Tweet.query.get_or_404(tweet_id)

    # Получаем комментарий
    comment = Comment.query.get_or_404(comment_id)

    # Проверяем, что пользователь является автором комментария или твита
    if comment.user_id != current_user.id and tweet.author_id != current_user.id:
        flash('Вы не можете удалить этот комментарий.', 'danger')
        return redirect(url_for('tweets.view_tweet', tweet_id=tweet.id))

    # Удаляем комментарий
    db.session.delete(comment)
    db.session.commit()
    flash('Комментарий удален!', 'success')

    # Перенаправляем обратно на страницу твита
    return redirect(url_for('tweets.view_tweet', tweet_id=tweet.id))


