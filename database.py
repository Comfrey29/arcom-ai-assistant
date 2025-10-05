# database.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    username = db.Column(db.String(80), primary_key=True, nullable=False)
    password = db.Column(db.LargeBinary, nullable=False)
    is_premium = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    # Camps nous per protecció contra bruteforce
    failed_logins = db.Column(db.Integer, default=0, nullable=False)
    last_failed = db.Column(db.DateTime, nullable=True)
    locked_until = db.Column(db.DateTime, nullable=True)
    banned = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<User {self.username}>"

class PremiumKey(db.Model):
    __tablename__ = 'premium_keys'
    key = db.Column(db.String(64), primary_key=True, nullable=False)
    used = db.Column(db.Boolean, default=False)
    uses_left = db.Column(db.Integer, default=10)
    expires_at = db.Column(db.DateTime, nullable=True)
