import os
import requests
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user,
                         logout_user, login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash

# Configura ruta absoluta base
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

app.config['SECRET_KEY'] = 'una_clau_molt_secreta_i_llarga'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_premium = db.Column(db.Boolean, default=False)

    @property
    def password(self):
        raise AttributeError('No es pot llegir la password')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    line = db.Column(db.Text, nullable=False)

class PremiumKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(32), unique=True, nullable=False)
    used = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# OpenRouter API key i configuració
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost"  # Ajusta a domini en producció
}

MODEL_PREMIUM = "gpt-3.5-turbo"
MODEL_FREE = "deepspeek"

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
    response = requests.post(OPENROUTER_API_URL, headers=HEADERS, json=payload, timeout=30)
    if response.status_code != 200:
        return f"⚠️ Error OpenRouter: {response.status_code}"
    data = response.json()
    if "choices" in data and len(data["choices"]) > 0:
        return data["choices"][0]["message"]["content"].strip()
    return "⚠️ No he pogut generar resposta."

# Rutes d'autenticació

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
        new_user = User(username=username)
        new_user.password = password
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
        if user and user.verify_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Credencials incorrectes')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sessió tancada')
    return redirect(url_for('login'))

# Endpoint API de xat

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    data = request.get_json(force=True)
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({"error": "Cal enviar un missatge"}), 400

    model = data.get('model')
    if model not in [MODEL_PREMIUM, MODEL_FREE]:
        model = MODEL_PREMIUM if current_user.is_premium else MODEL_FREE

    # Recuperar últims 10 missatges
    history_rows = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.id.desc()).limit(10).all()
    history = [row.line for row in reversed(history_rows)]

    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    for line in history:
        if line.startswith("Usuari: "):
            messages.append({"role": "user", "content": line[len("Usuari: "):]})
        elif line.startswith("Assistència: "):
            messages.append({"role": "assistant", "content": line[len("Assistència: "):]})

    messages.append({"role": "user", "content": user_message})
    bot_reply = query_openrouter(messages, model)

    db.session.add(Conversation(user_id=current_user.id, line=f"Usuari: {user_message}"))
    db.session.add(Conversation(user_id=current_user.id, line=f"Assistència: {bot_reply}"))
    db.session.commit()

    return jsonify({"reply": bot_reply})

# Activar premium amb clau

@app.route('/premium/activate', methods=['POST'])
@login_required
def premium_activate():
    key = request.form.get('key', '').strip()
    premium_key = PremiumKey.query.filter_by(key=key, used=False).first()
    if premium_key:
        premium_key.used = True
        current_user.is_premium = True
        db.session.commit()
        flash("Compte premium activat!")
        return redirect(url_for('index'))
    flash('Clau no vàlida o ja usada')
    return redirect(url_for('index'))

# Pàgina principal protegida

@app.route('/')
@login_required
def index():
    return render_template('index.html', user=current_user)

# Ruta per veure taules (debug)

@app.route('/db-tables')
def db_tables():
    tables = db.engine.table_names()
    return '<br>'.join(tables)

# Creació taules fora de __main__ per funcionament amb Gunicorn

print("Creant taules a la base de dades...")
with app.app_context():
    db.create_all()
print("Taules creades")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
