from flask import render_template, request
from flask_login import login_required, current_user
from sqlalchemy import func, desc, asc
from datetime import datetime, timedelta

from app.models import User, Tweet, Like, Comment
from app.main import main_bp


@main_bp.route('/')
def home():
    query = request.args.get('q', '').strip()
    date_str = request.args.get('date', '').strip()
    min_likes = request.args.get('min_likes', '').strip()
    min_comments = request.args.get('min_comments', '').strip()

    # New: sort options
    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')

    tweets_query = Tweet.query

    # Поиск
    if query:
        if query.startswith('@'):
            username = query[1:]
            user = User.query.filter_by(username=username).first()
            if user:
                tweets_query = tweets_query.filter(Tweet.user_id == user.id)
            else:
                tweets_query = tweets_query.filter(False)
        elif query.startswith('#'):
            hashtag = query.lower()
            tweets_query = tweets_query.filter(Tweet.hashtags.ilike(f'%{hashtag}%'))
        else:
            tweets_query = tweets_query.filter(Tweet.content.ilike(f'%{query}%'))

    # Фильтр по дате
    if date_str:
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            next_day = date + timedelta(days=1)
            tweets_query = tweets_query.filter(
                Tweet.created_at >= date,
                Tweet.created_at < next_day
            )
        except ValueError:
            pass

    # Лайки и комментарии — джойним
    tweets_query = tweets_query \
        .outerjoin(Like, Like.tweet_id == Tweet.id) \
        .outerjoin(Comment, Comment.tweet_id == Tweet.id) \
        .group_by(Tweet.id)

    if min_likes.isdigit():
        tweets_query = tweets_query.having(func.count(Like.id) >= int(min_likes))

    if min_comments.isdigit():
        tweets_query = tweets_query.having(func.count(Comment.id) >= int(min_comments))

    # --- Сортировка ---
    sort_order_func = desc if order == 'desc' else asc

    if sort_by == 'likes':
        tweets_query = tweets_query.order_by(sort_order_func(func.count(Like.id)))
    elif sort_by == 'comments':
        tweets_query = tweets_query.order_by(sort_order_func(func.count(Comment.id)))
    else:  # default or 'date'
        tweets_query = tweets_query.order_by(sort_order_func(Tweet.created_at))

    tweets = tweets_query.all()

    return render_template(
        'home.html',
        tweets=tweets,
        query=query,
        date=date_str,
        min_likes=min_likes,
        min_comments=min_comments,
        sort_by=sort_by,
        order=order
    )


@main_bp.route('/profile')
@login_required
def profile():
    tweets = Tweet.query \
        .filter_by(user_id=current_user.id) \
        .order_by(Tweet.created_at.desc()) \
        .all()

    return render_template('profile.html', tweets=tweets)
