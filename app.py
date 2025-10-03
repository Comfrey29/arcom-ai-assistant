import os
import requests
import secrets
import string
import bcrypt
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session, g
import sqlite3
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'una_clau_molt_secreta_i_llarga'
DATABASE = 'app_database.db'

PREDEFINED_ADMINS = ['admin', 'Comfrey']
MODEL_PREMIUM = "gpt-3.5-turbo"
MODEL_FREE = "deepseek/deepseek-chat-v3-0324"

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    try:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            is_premium INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS premium_keys (
            key TEXT PRIMARY KEY,
            used INTEGER DEFAULT 0,
            uses_left INTEGER DEFAULT 10,
            expires_at TEXT
        );
        ''')
        db.commit()
    except sqlite3.Error as e:
        print(f"DB error during init_db: {e}")

def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt)

def check_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed)
    except:
        return False

def is_admin(username):
    if username in PREDEFINED_ADMINS:
        return True
    try:
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        return bool(user and user['is_admin'])
    except sqlite3.Error as e:
        print(f"DB error in is_admin: {e}")
        return False

def load_json(filename):
    # Mantingut per altres dades no migrades
    if not os.path.exists(filename):
        return {}
    with open(filename, 'r') as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def generate_premium_key(length=30):
    alphabet = string.ascii_letters + string.digits + "-_"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

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
        try:
            db = get_db()
            user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            if user:
                flash('Aquest usuari ja existeix')
                return redirect(url_for('register'))
            hashed = hash_password(password)
            db.execute(
                'INSERT INTO users (username, password, is_premium, is_admin, is_active) VALUES (?, ?, 0, 0, 1)',
                (username, hashed)
            )
            db.commit()
            flash('Registre completat! Ara pots iniciar sessió.')
        except sqlite3.Error as e:
            flash('Error a la base de dades.')
            print(f"DB error in register: {e}")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        try:
            db = get_db()
            user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            if user and check_password(password, user['password']):
                session['username'] = username
                flash('Login efectuat!')
                return redirect(url_for('index'))
        except sqlite3.Error as e:
            print(f"DB error in login: {e}")
        flash('Credencials incorrectes')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Sessió tancada')
    return redirect(url_for('login'))

def get_conversations(username):
    conversations = load_json(CONVERSATIONS_FILE)
    return conversations.get(username, [])

def save_conversation(username, line):
    conversations = load_json(CONVERSATIONS_FILE)
    if username not in conversations:
        conversations[username] = []
    conversations[username].append(line)
    conversations[username] = conversations[username][-20:]
    save_json(CONVERSATIONS_FILE, conversations)

@app.route('/api/chat', methods=['POST'])
def chat():
    if 'username' not in session:
        return jsonify({"error": "No has iniciat sessió"}), 401
    data = request.get_json(force=True)
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({"error": "Cal enviar un missatge"}), 400
    model = data.get('model')
    db = get_db()
    current_user = session['username']
    user = db.execute('SELECT * FROM users WHERE username = ?', (current_user,)).fetchone()
    user_data = dict(user) if user else {}
    if model not in [MODEL_PREMIUM, MODEL_FREE]:
        model = MODEL_PREMIUM if user_data.get('is_premium', False) else MODEL_FREE

    history = get_conversations(current_user)
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
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
    db = get_db()
    premium_keys = db.execute('SELECT * FROM premium_keys').fetchall()
    keys = {k['key']: dict(k) for k in premium_keys}
    now = datetime.utcnow()

    if key not in keys:
        flash('Clau no vàlida')
        return redirect(url_for('premium'))

    key_data = keys[key]

    if key_data['used']:
        flash('Clau ja utilitzada')
        return redirect(url_for('premium'))
    if now > datetime.fromisoformat(key_data['expires_at']):
        flash('Clau caducada')
        return redirect(url_for('premium'))

    db.execute('UPDATE premium_keys SET used = 1 WHERE key = ?', (key,))
    db.commit()

    current_user = session['username']
    db.execute('UPDATE users SET is_premium = 1 WHERE username = ?', (current_user,))
    db.commit()

    flash('Compte premium activat!')
    return redirect(url_for('index'))

@app.route('/admin/keys', methods=['GET', 'POST'])
def admin_keys():
    if 'username' not in session or not is_admin(session['username']):
        flash("No tens permisos d'administrador.")
        return redirect(url_for('login'))
    db = get_db()
    premium_keys = db.execute('SELECT * FROM premium_keys').fetchall()
    keys = {k['key']: dict(k) for k in premium_keys}
    users = db.execute('SELECT * FROM users').fetchall()
    users_dict = {u['username']: dict(u) for u in users}

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            period = request.form.get('period')
            days = 30 if period == 'month' else 365
            new_key = generate_premium_key(30)
            expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()
            db.execute('INSERT INTO premium_keys (key, used, uses_left, expires_at) VALUES (?, 0, 10, ?)',
                       (new_key, expires_at))
            db.commit()
            flash(f"Nova clau generada: {new_key}")
        elif action == 'revoke':
            key_to_revoke = request.form.get('key')
            db.execute('UPDATE premium_keys SET used = 1 WHERE key = ?', (key_to_revoke,))
            db.commit()
            flash(f"Clau revocada: {key_to_revoke}")
        elif action == 'add_admin':
            admin_user = request.form.get('admin_user', '').strip()
            if admin_user in users_dict:
                db.execute('UPDATE users SET is_admin = 1 WHERE username = ?', (admin_user,))
                db.commit()
                flash(f"Usuari {admin_user} ara és administrador")
            else:
                flash("Usuari no trobat")
        elif action == 'remove_admin':
            admin_user = request.form.get('admin_user', '').strip()
            if admin_user in users_dict:
                db.execute('UPDATE users SET is_admin = 0 WHERE username = ?', (admin_user,))
                db.commit()
                flash(f"Usuari {admin_user} ja no és administrador")
            else:
                flash("Usuari no trobat")

    return render_template('admin_keys.html', keys=keys, users=users_dict)

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', user=session['username'])

if __name__ == "__main__":
    with app.app_context():
        init_db()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)


