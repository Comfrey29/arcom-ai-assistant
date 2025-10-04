import os
import secrets
import string
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import bcrypt
import requests
import psycopg2-binary

app = Flask(__name__)
app.config['SECRET_KEY'] = 'una_clau_molt_secreta_i_llarga'

# Configuració de la base de dades PostgreSQL (canvia la cadena de connexió segons el teu entorn)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/mydatabase')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

PREDEFINED_ADMINS = ['admin', 'Comfrey']
MODEL_PREMIUM = "gpt-3.5-turbo"
MODEL_FREE = "deepseek/deepseek-chat-v3-0324"

class User(db.Model):
    __tablename__ = 'users'
    username = db.Column(db.String(80), primary_key=True, nullable=False)
    password = db.Column(db.LargeBinary, nullable=False)  # bcrypt hashed password
    is_premium = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

class PremiumKey(db.Model):
    __tablename__ = 'premium_keys'
    key = db.Column(db.String(64), primary_key=True, nullable=False)
    used = db.Column(db.Boolean, default=False)
    uses_left = db.Column(db.Integer, default=10)
    expires_at = db.Column(db.DateTime, nullable=True)

def generate_premium_key(length=30):
    alphabet = string.ascii_letters + string.digits + "-_"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def is_admin(username):
    if username in PREDEFINED_ADMINS:
        return True
    user = User.query.filter_by(username=username).first()
    return user.is_admin if user else False

def query_openrouter(messages, model):
    if not os.environ.get('OPENROUTER_API_KEY'):
        return "⚠️ API key OpenRouter no configurada"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 150,
        "stream": False
    }
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY')}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost"
        },
        json=payload, timeout=30)
    if response.status_code != 200:
        return f"⚠️ Error OpenRouter: {response.status_code} - {response.text}"
    data = response.json()
    if "choices" in data and len(data["choices"]) > 0:
        return data["choices"][0]["message"]["content"].strip()
    return "⚠️ No he pogut generar resposta."

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Omple tots els camps')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Aquest usuari ja existeix')
            return redirect(url_for('register'))
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        new_user = User(username=username, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash('Registre completat! Ara pots iniciar sessió.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password):
            session['username'] = username
            flash('Login efectuat!')
            return redirect(url_for('index'))
        flash('Credencials incorrectes')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Sessió tancada')
    return redirect(url_for('login'))

def get_conversations(username):
    # Aquesta part la pots mantenir si no vols migrar
    import json, os
    CONVERSATIONS_FILE = 'conversations.json'
    if not os.path.exists(CONVERSATIONS_FILE):
        return []
    with open(CONVERSATIONS_FILE) as f:
        conversations = json.load(f)
    return conversations.get(username, [])

def save_conversation(username, line):
    import json, os
    CONVERSATIONS_FILE = 'conversations.json'
    conversations = {}
    if os.path.exists(CONVERSATIONS_FILE):
        with open(CONVERSATIONS_FILE) as f:
            conversations = json.load(f)
    conversations.setdefault(username, []).append(line)
    conversations[username] = conversations[username][-20:]
    with open(CONVERSATIONS_FILE, 'w') as f:
        json.dump(conversations, f, indent=4)

@app.route('/api/chat', methods=['POST'])
def chat():
    if 'username' not in session:
        return jsonify({"error": "No has iniciat sessió"}), 401
    data = request.get_json(force=True)
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({"error": "Cal enviar un missatge"}), 400
    model = data.get('model')
    current_user = session['username']
    user = User.query.filter_by(username=current_user).first()
    if model not in [MODEL_PREMIUM, MODEL_FREE]:
        model = MODEL_PREMIUM if user and user.is_premium else MODEL_FREE

    history = get_conversations(current_user)
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    history = history[-20:]
    for line in history:
        if line.startswith("Usuari: "):
            messages.append({"role": "user", "content": line[len("Usuari: "):]})
        elif line.startswith("Assistència: "):
            messages.append({"role": "assistant", "content": line[len("Assistència: "):]})

    messages.append({"role": "user", "content": user_message})
    bot_reply = query_openrouter(messages, model)

    save_conversation(current_user, f"Usuari: {user_message}")
    save_conversation(current_user, f"Assistència: {bot_reply}")

    return jsonify({"reply": bot_reply})

@app.route('/premium', methods=['GET'])
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

    if not premium_key:
        flash('Clau no vàlida')
        return redirect(url_for('premium'))

    if premium_key.used:
        flash('Clau ja utilitzada')
        return redirect(url_for('premium'))

    if premium_key.expires_at and now > premium_key.expires_at:
        flash('Clau caducada')
        return redirect(url_for('premium'))

    premium_key.used = True
    db.session.commit()

    current_user = session['username']
    user = User.query.filter_by(username=current_user).first()
    if user:
        user.is_premium = True
        db.session.commit()

    flash('Compte premium activat!')
    return redirect(url_for('index'))

@app.route('/admin/keys', methods=['GET', 'POST'])
def admin_keys():
    if 'username' not in session or not is_admin(session['username']):
        flash("No tens permisos d'administrador.")
        return redirect(url_for('login'))
    keys = PremiumKey.query.all()
    users = User.query.all()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            period = request.form.get('period')
            days = 30 if period == 'month' else 365
            new_key = generate_premium_key(30)
            expires_at = datetime.utcnow() + timedelta(days=days)
            premium_key = PremiumKey(key=new_key, used=False, uses_left=10, expires_at=expires_at)
            db.session.add(premium_key)
            db.session.commit()
            flash(f"Nova clau generada: {new_key}")
        elif action == 'revoke':
            key_to_revoke = request.form.get('key')
            premium_key = PremiumKey.query.filter_by(key=key_to_revoke).first()
            if premium_key:
                premium_key.used = True
                db.session.commit()
                flash(f"Clau revocada: {key_to_revoke}")
        elif action == 'add_admin':
            admin_user = request.form.get('admin_user', '').strip()
            user = User.query.filter_by(username=admin_user).first()
            if user:
                user.is_admin = True
                db.session.commit()
                flash(f"Usuari {admin_user} ara és administrador")
            else:
                flash("Usuari no trobat")
        elif action == 'remove_admin':
            admin_user = request.form.get('admin_user', '').strip()
            user = User.query.filter_by(username=admin_user).first()
            if user:
                user.is_admin = False
                db.session.commit()
                flash(f"Usuari {admin_user} ja no és administrador")
            else:
                flash("Usuari no trobat")

    return render_template('admin_keys.html', keys=keys, users=users)

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', user=session['username'])

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
