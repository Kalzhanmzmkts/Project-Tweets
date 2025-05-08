from . import main_bp
from app.extensions import db
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app.models import User, Tweet

from app.main import main_bp


@main_bp.route('/')
def home():
    query = request.args.get('q', '').strip()
    if query:
        if query.startswith('@'):
            username = query[1:]
            user = User.query.filter_by(username=username).first()
            if user:
                tweets = Tweet.query.filter_by(user_id=user.id).order_by(Tweet.created_at.desc()).all()
            else:
                tweets = []
        else:
            tweets = Tweet.query.filter(Tweet.content.ilike(f'%{query}%')).order_by(Tweet.created_at.desc()).all()
    else:
        tweets = Tweet.query.order_by(Tweet.created_at.desc()).all()

    return render_template('home.html', tweets=tweets, query=query)


@main_bp.route('/profile')
@login_required
def profile():
    tweets = Tweet.query.filter_by(user_id=current_user.id).order_by(Tweet.created_at.desc()).all()
    return render_template('profile.html', tweets=tweets)
