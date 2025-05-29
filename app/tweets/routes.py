from datetime import datetime
import os

import torch
from PIL import Image
from flask import (
    render_template, redirect, url_for, request,
    flash, abort, current_app
)
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from werkzeug.utils import secure_filename
from wtforms import TextAreaField, FileField, SubmitField
from wtforms.validators import DataRequired, Length

from app.extensions import db
from app.models import Tweet, Comment, Like
from app.tweets import tweets_bp

from transformers import pipeline


# ——— FORMS ———————————————————————————————————————————————————————————————
class TweetForm(FlaskForm):
    content = TextAreaField('Tweet Text', validators=[DataRequired(), Length(max=280)])
    image = FileField('Image', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Only images allowed!')])
    submit = SubmitField('Publish')


class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired(), Length(max=280)])
    submit = SubmitField('Post')


# ——— FILE STORAGE ———————————————————————————————————————————————————————————————
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def save_uploaded_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{filename}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return filepath
    return None


# ——— SENTIMENT ANALYSIS ———————————————————————————————————————————————————————
_sentiment_pipeline = None


def get_sentiment_pipeline():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        _sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english"
        )
    return _sentiment_pipeline


def analyze_sentiment(text: str) -> str:
    pipeline_ = get_sentiment_pipeline()
    text = text[:512]
    result = pipeline_(text)
    if result and isinstance(result, list) and 'label' in result[0]:
        return result[0]['label']
    return "NEUTRAL"


# ——— HASHTAG GENERATION ———————————————————————————————————————————————————————
_hashtag_generator = None


def get_hashtag_generator():
    global _hashtag_generator
    if _hashtag_generator is None:
        _hashtag_generator = pipeline('text2text-generation', model='t5-small')
    return _hashtag_generator


def generate_hashtags_hf(text: str, max_tags=5) -> list[str]:
    generator = get_hashtag_generator()
    prompt = f"generate hashtags: {text}"
    results = generator(prompt, max_length=50, num_return_sequences=1)
    hashtags_text = results[0]['generated_text']
    tags = hashtags_text.replace('#', '').replace(',', ' ').split()
    unique_tags = []
    for tag in tags:
        tag = tag.lower()
        if tag.isalpha() and tag not in unique_tags:
            unique_tags.append(tag)
        if len(unique_tags) >= max_tags:
            break
    return [f"#{tag}" for tag in unique_tags]


# ——— GRAMMAR CORRECTION ——————————————————————————————————————————————————————
_grammar_corrector = None


def get_grammar_corrector():
    global _grammar_corrector
    if _grammar_corrector is None:
        _grammar_corrector = pipeline(
            "text2text-generation",
            model="AventIQ-AI/T5-small-grammar-correction"
        )
    return _grammar_corrector


def correct_grammar(text: str) -> str:
    corrector = get_grammar_corrector()
    result = corrector(text, max_length=128, do_sample=False)
    if result and isinstance(result, list):
        return result[0]['generated_text']
    return text


# ——— ROUTES ————————————————————————————————————————————————————————————————
@tweets_bp.route('/tweet/new', methods=['GET', 'POST'])
@login_required
def new_tweet():
    form = TweetForm()
    if form.validate_on_submit():
        image_path = save_uploaded_file(form.image.data) if form.image.data else None
        corrected_text = correct_grammar(form.content.data)
        sentiment = analyze_sentiment(corrected_text)
        hashtags_list = generate_hashtags_hf(corrected_text)
        hashtags = " ".join(hashtags_list)

        tweet = Tweet(
            content=corrected_text,
            user_id=current_user.id,
            image=os.path.basename(image_path) if image_path else None,
            sentiment=sentiment,
            hashtags=hashtags,
        )
        db.session.add(tweet)
        db.session.commit()
        flash(f'Tweet created! Corrected text: "{corrected_text}" | Sentiment: {sentiment}', 'success')
        return redirect(url_for('main.home'))
    return render_template('create_tweet.html', form=form)


@tweets_bp.route('/tweet/<int:tweet_id>', methods=['GET', 'POST'])
@login_required
def view_tweet(tweet_id):
    tweet = Tweet.query.get_or_404(tweet_id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(
            content=form.content.data,
            tweet_id=tweet.id,
            user_id=current_user.id
        )
        db.session.add(comment)
        db.session.commit()
        flash('Comment added!', 'success')
        return redirect(url_for('tweets.view_tweet', tweet_id=tweet.id))
    return render_template('view_tweet.html', tweet=tweet, form=form)


@tweets_bp.route('/tweet/<int:tweet_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_tweet(tweet_id):
    tweet = Tweet.query.get_or_404(tweet_id)
    if tweet.author != current_user:
        abort(403)
    form = TweetForm()

    if form.validate_on_submit():
        corrected_text = correct_grammar(form.content.data)
        tweet.content = corrected_text
        tweet.sentiment = analyze_sentiment(corrected_text)
        hashtags_list = generate_hashtags_hf(corrected_text)
        tweet.hashtags = " ".join(hashtags_list)

        if form.image.data:
            if tweet.image:
                try:
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], tweet.image))
                except OSError:
                    pass
            image_path = save_uploaded_file(form.image.data)
            if image_path:
                tweet.image = os.path.basename(image_path)
            else:
                tweet.image = None

        db.session.commit()
        flash('Tweet updated!', 'success')
        return redirect(url_for('tweets.view_tweet', tweet_id=tweet.id))

    if request.method == 'GET':
        form.content.data = tweet.content

    return render_template('edit_tweet.html', form=form, tweet=tweet)


@tweets_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id and comment.tweet.author != current_user:
        abort(403)
    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted!', 'success')
    return redirect(url_for('tweets.view_tweet', tweet_id=comment.tweet_id))


@tweets_bp.route('/tweet/<int:tweet_id>/like', methods=['POST'])
@login_required
def like_tweet(tweet_id):
    tweet = Tweet.query.get_or_404(tweet_id)
    if tweet.user_id == current_user.id:
        abort(403)
    existing = Like.query.filter_by(user_id=current_user.id, tweet_id=tweet.id).first()
    if existing:
        db.session.delete(existing)
        flash('Like removed', 'info')
    else:
        db.session.add(Like(user_id=current_user.id, tweet_id=tweet.id))
        flash('Like added!', 'success')
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
            os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], tweet.image))
        except OSError:
            pass
    db.session.delete(tweet)
    db.session.commit()
    flash('Tweet deleted!', 'success')
    return redirect(url_for('main.profile'))
