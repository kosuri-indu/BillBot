from flask_sqlalchemy import SQLAlchemy
from flask import Flask
import os

db = SQLAlchemy()


def init_db(app: Flask):
    # Expect DATABASE_URL in env, fall back to sqlite for local dev
    database_url = os.environ.get('DATABASE_URL') or 'sqlite:///dev.db'
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return db
