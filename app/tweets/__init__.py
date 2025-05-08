from flask import Blueprint

tweets_bp = Blueprint('tweets', __name__)

from . import routes
