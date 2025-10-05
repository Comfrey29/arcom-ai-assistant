from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_migrate import Migrate
import os
import secrets
import string
from datetime import datetime, timedelta
import bcrypt
import requests

from database import db, User, PremiumKey  # Assegura't que els models tenen camps nous de seguretat

# --- Configuració Flask ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una_clau_molt_secreta_i_llarga')

# Seguretat de cookies i sessions
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,        # HTTPS en producció
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=7)
)

# --- Configuració base de dades ---
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    raise RuntimeError("❌ La variable d'entorn DATABASE_URL no està configurada!")
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

# --- Taula per IP bans ---
class BannedIP(db.Model):
    __tablename__ = 'banned_ips'
    ip = db.Column(db.String(45), primary_key=True, nullable=False)
    reason = db.Column(db.String(200), nullable=True)
    banned_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# --- Constants ---
PREDEFINED_ADMINS = ['admin', 'Comfrey']
MODEL_PREMIUM = "gpt-3.5-turbo"
MODEL_FREE = "deepseek/deepseek-chat-v3-0324"
MODEL_PREMIUM_TWO = "deepseek/deepseek-r1"
MODEL_FREE_TWO = "moonshotai/kimi-k2"
MODEL_PREMIUM_ONLINE = "openai/gpt-4o:online"
MAX_FAILED = 5
LOCKOUT_MINUTES = 15
TEMP_LOCK = True  # Si False, ban permanent després de MAX_FAILED

# --- Helpers ---
def generate_premium_key(length=30):
    alphabet = string.ascii_letters + string.digits + "-_"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def is_admin(username):
    if username in PREDEFINED_ADMINS:
        return True
    user = User.query.filter_by(username=username).first()
    return user.is_admin if user else False

def query_openrouter(messages, model):
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        return "⚠️ API key OpenRouter no configurada"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 150,
        "stream": False
    }
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        return f"⚠️ Error OpenRouter: {e}"
    data = resp.json()
    if "choices" in data and len(data["choices"]) > 0:
        return data["choices"][0]["message"]["content"].strip()
    return "⚠️ No he pogut generar resposta."

# --- Proteccions globals ---
@app.before_request
def block_banned_ip():
    ip = request.remote_addr
    if ip and BannedIP.query.filter_by(ip=ip).first():
        return ("Your IP has been banned.", 403)

@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'geolocation=()'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self';"
    return response

# --- Converses ---
CONVERSATIONS_FILE = 'conversations.json'

def get_conversations(username):
    import json
    if not os.path.exists(CONVERSATIONS_FILE):
        return []
    with open(CONVERSATIONS_FILE) as f:
        conversations = json.load(f)
    return conversations.get(username, [])

def save_conversation(username, line):
    import json
    conversations = {}
    if os.path.exists(CONVERSATIONS_FILE):
        with open(CONVERSATIONS_FILE) as f:
            conversations = json.load(f)
    conversations.setdefault(username, []).append(line)
    conversations[username] = conversations[username][-20:]
    with open(CONVERSATIONS_FILE, 'w') as f:
        json.dump(conversations, f, indent=4)

# --- Rutes principals ---
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', user=session['username'])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Omple tots els camps')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Aquest usuari ja existeix')
            return redirect(url_for('register'))
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        new_user = User(username=username, password=hashed_pw)
        try:
            db.session.add(new_user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash('Error creant usuari.')
            return redirect(url_for('register'))
        flash('Registre completat! Ara pots iniciar sessió.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if not user:
            flash('Credencials incorrectes')
            return redirect(url_for('login'))

        now = datetime.utcnow()
        if getattr(user, 'banned', False):
            flash('Compte bloquejat.')
            return redirect(url_for('login'))
        if getattr(user, 'locked_until', None) and user.locked_until > now:
            remaining = int((user.locked_until - now).total_seconds() // 60) + 1
            flash(f'Too many failed attempts. Try again in {remaining} minute(s).')
            return redirect(url_for('login'))

        if bcrypt.checkpw(password.encode('utf-8'), user.password):
            user.failed_logins = 0
            user.last_failed = None
            user.locked_until = None
            user.last_ip = request.remote_addr
            user.last_login = datetime.utcnow()
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            session['username'] = username
            flash('Login efectuat!')
            return redirect(url_for('index'))
        else:
            user.failed_logins = (user.failed_logins or 0) + 1
            user.last_failed = now
            if user.failed_logins >= MAX_FAILED:
                if TEMP_LOCK:
                    user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                    flash(f'Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes.')
                else:
                    user.banned = True
                    flash('Compte bloquejat permanentment.')
            else:
                flash('Credencials incorrectes')
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Sessió tancada')
    return redirect(url_for('login'))

@app.route('/api/chat', methods=['POST'])
def chat():
    if 'username' not in session:
        return jsonify({"error": "No has iniciat sessió"}), 401

    data = request.get_json(force=True)
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({"error": "Cal enviar un missatge"}), 400

    requested_model = data.get('model', '').strip()
    current_user = session['username']
    user = User.query.filter_by(username=current_user).first()

    if user and getattr(user, 'banned', False):
        return jsonify({"error": "Compte banejat"}), 403

    # Determinar el model a usar
    if requested_model == MODEL_PREMIUM_ONLINE and user and user.is_premium:
        model = MODEL_PREMIUM_ONLINE
    elif requested_model == MODEL_PREMIUM_TWO and user and user.is_premium:
        model = MODEL_PREMIUM_TWO
    elif requested_model == MODEL_FREE_TWO:
        model = MODEL_FREE_TWO
    elif requested_model == MODEL_PREMIUM and user and user.is_premium:
        model = MODEL_PREMIUM
    else:
        model = MODEL_FREE

    # Historial de converses
    history = get_conversations(current_user)[-20:]
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    for line in history:
        if line.startswith("Usuari: "):
            messages.append({"role": "user", "content": line[len("Usuari: "):]})
        elif line.startswith("Assistència: "):
            messages.append({"role": "assistant", "content": line[len("Assistència: "):]})

    messages.append({"role": "user", "content": user_message})

    # Crida a OpenRouter / model local segons model
    bot_reply = query_openrouter(messages, model)

    save_conversation(current_user, f"Usuari: {user_message}")
    save_conversation(current_user, f"Assistència: {bot_reply}")

    return jsonify({"reply": bot_reply})


@app.route('/premium')
def premium():
    if 'username' not in session:
        flash('Has de fer login')
        return redirect(url_for('login'))
    return render_template('premium.html')

@app.route('/premium/activate', methods=['POST'])
def premium_activate():
    if 'username' not in session:
        flash('Has de fer login per activar premium')
        return redirect(url_for('login'))
    key = request.form.get('key', '').strip()
    premium_key = PremiumKey.query.filter_by(key=key).first()
    now = datetime.utcnow()
    if not premium_key or premium_key.used or (premium_key.expires_at and now > premium_key.expires_at):
        flash('Clau no vàlida o caducada')
        return redirect(url_for('premium'))
    try:
        premium_key.used = True
        db.session.commit()
        user = User.query.filter_by(username=session['username']).first()
        if user:
            user.is_premium = True
            db.session.commit()
    except Exception:
        db.session.rollback()
        flash('Error activant premium.')
        return redirect(url_for('premium'))
    flash('Compte premium activat!')
    return redirect(url_for('index'))

# --- Arrencada ---
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
