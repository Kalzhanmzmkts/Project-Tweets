import os

class Config:
    SECRET_KEY = 'admin'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///tweets.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
