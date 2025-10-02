import os
import json
import requests
import secrets
import string
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session

app = Flask(__name__)
app.config['SECRET_KEY'] = 'una_clau_molt_secreta_i_llarga'

USERS_FILE = 'users.json'
CONVERSATIONS_FILE = 'conversations.json'
PREMIUM_KEYS_FILE = 'premium_keys.json'

# OpenRouter API config
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost"
}

MODEL_PREMIUM = "gpt-3.5-turbo"
MODEL_FREE = "deepseek/deepseek-chat-v3-0324"

def load_json(filename):
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

def is_admin(username):
    # Definició d'administradors simple
    return username == "admin"

def query_openrouter(messages, model):
    if not OPENROUTER_API_KEY:
        return "⚠️ API key OpenRouter no configurada"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 150,
        "stream": False
    }
    print("OpenRouter payload:", json.dumps(payload, indent=2))
    response = requests.post(OPENROUTER_API_URL, headers=HEADERS, json=payload, timeout=30)
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
        users = load_json(USERS_FILE)
        if username in users:
            flash('Aquest usuari ja existeix')
            return redirect(url_for('register'))
        users[username] = {"password": password, "is_premium": False}
        save_json(USERS_FILE, users)
        flash('Registre completat! Ara pots iniciar sessió.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_json(USERS_FILE)
        if username in users and users[username]['password'] == password:
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
    users = load_json(USERS_FILE)
    current_user = session['username']
    user_data = users.get(current_user, {})
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
    premium_keys = load_json(PREMIUM_KEYS_FILE)
    now = datetime.utcnow()

    if key not in premium_keys:
        flash('Clau no vàlida')
        return redirect(url_for('premium'))

    key_data = premium_keys[key]

    if key_data['used']:
        flash('Clau ja utilitzada')
        return redirect(url_for('premium'))
    if now > datetime.fromisoformat(key_data['expires_at']):
        flash('Clau caducada')
        return redirect(url_for('premium'))

    key_data['used'] = True
    premium_keys[key] = key_data
    save_json(PREMIUM_KEYS_FILE, premium_keys)

    users = load_json(USERS_FILE)
    current_user = session['username']
    user_data = users.get(current_user, {})
    user_data['is_premium'] = True
    users[current_user] = user_data
    save_json(USERS_FILE, users)

    flash('Compte premium activat!')
    return redirect(url_for('index'))

@app.route('/admin/keys', methods=['GET', 'POST'])
def admin_keys():
    if 'username' not in session or not is_admin(session['username']):
        flash("No tens permisos d'administrador.")
        return redirect(url_for('login'))
    premium_keys = load_json(PREMIUM_KEYS_FILE)

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            period = request.form.get('period')
            days = 30 if period == 'month' else 365
            new_key = generate_premium_key(30)
            expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()
            premium_keys[new_key] = {
                "used": False,
                "uses_left": 10,
                "expires_at": expires_at
            }
            flash(f"Nova clau generada: {new_key}")
        elif action == 'revoke':
            key_to_revoke = request.form.get('key')
            if key_to_revoke in premium_keys:
                premium_keys[key_to_revoke]['used'] = True
                flash(f"Clau revocada: {key_to_revoke}")
        save_json(PREMIUM_KEYS_FILE, premium_keys)

    html = "<h1>Admin de claus Premium</h1>"
    html += '''
      <form method="POST">
        <select name="period">
          <option value="month">1 mes</option>
          <option value="year">1 any</option>
        </select>
        <button name="action" value="add">Afegeix nova clau</button>
      </form><br>
    '''
    html += "<table border='1'><tr><th>Clau</th><th>Usada</th><th>Usos restants</th><th>Caducitat</th><th>Acció</th></tr>"
    for k, v in premium_keys.items():
        html += f"<tr><td>{k}</td><td>{v['used']}</td><td>{v['uses_left']}</td><td>{v['expires_at']}</td><td>"
        if not v['used']:
            html += f'''
            <form method="POST" style="display:inline">
                <input type="hidden" name="key" value="{k}">
                <button name="action" value="revoke">Revocar</button>
            </form>
            '''
        html += "</td></tr>"
    html += "</table>"
    return html

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', user=session['username'])

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
