from database import db

class User(db.Model):
    __tablename__ = 'users'
    username = db.Column(db.String(80), primary_key=True, nullable=False)
    password = db.Column(db.LargeBinary, nullable=False)
    is_premium = db.Column(db.Boolean, default=False)
    language = db.Column(db.String(10), default='ca')
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

class PremiumKey(db.Model):
    __tablename__ = 'premium_keys'
    key = db.Column(db.String(64), primary_key=True, nullable=False)
    used = db.Column(db.Boolean, default=False)
    uses_left = db.Column(db.Integer, default=10)
    expires_at = db.Column(db.DateTime, nullable=True)
