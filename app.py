import os
import requests
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user,
                         logout_user, login_required, current_user)
from flask_dance.contrib.google import make_google_blueprint, google
import secrets

app = Flask(__name__)

# Configuració bàsica Flask i Flask-SQLAlchemy
app.config['SECRET_KEY'] = 'una_clau_molt_secreta_i_llarga'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Config Google OAuth (modifica aquests valors)
google_bp = make_google_blueprint(
    client_id="EL_TEVE_CLIENT_ID",
    client_secret="EL_TEVE_CLIENT_SECRET",
    scope=["profile", "email"],
    redirect_url="/google_login/callback"
)
app.register_blueprint(google_bp, url_prefix="/login")

# ─────────────────────────────
# Models
# ─────────────────────────────

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)  # email Gmail o usuari creat
    password = db.Column(db.String(128), default="")  # per comptes locals (opc.)
    is_premium = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    line = db.Column(db.Text, nullable=False)

class PremiumKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(32), unique=True, nullable=False)
    used = db.Column(db.Boolean, default=False)

# ─────────────────────────────
# Gestió Flask-Login
# ─────────────────────────────

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ─────────────────────────────
# OpenRouter config
# ─────────────────────────────

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
print("Clau OpenRouter carregada?", bool(OPENROUTER_API_KEY))

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json"
}

MODEL_PREMIUM = "gpt-3.5-turbo"
MODEL_FREE = "deepspeek"

def query_openrouter(messages, model):
    try:
        if not OPENROUTER_API_KEY:
            return "⚠️ La clau OPENROUTER_API_KEY no està configurada."
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 150,
            "stream": False
        }
        response = requests.post(OPENROUTER_API_URL, headers=HEADERS, json=payload, timeout=30)
        print(f"[DEBUG] Codi resposta: {response.status_code}")
        if response.status_code == 401:
            return "⚠️ Clau API no vàlida o no configurada."
        if response.status_code == 429:
            return "⚠️ Límit de taxa excedit, espera i torna-ho a provar."
        if response.status_code >= 400:
            return f"⚠️ Error servidor: {response.status_code}"
        response.raise_for_status()
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        return "⚠️ No he pogut generar resposta, torna-ho a provar."
    except requests.exceptions.Timeout:
        return "⚠️ Temps d'espera esgotat amb OpenRouter.ai."
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return f"⚠️ Error inesperat: {str(e)}"

# ─────────────────────────────
# Rutes login/logout tradicional i /api/chat
# ─────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.json.get('username')
        password = request.json.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:  # A producció: fer hash i verificar
            login_user(user)
            return jsonify({"status": "ok", "message": "Login correcte"})
        return jsonify({"status": "error", "message": "Usuari o contrasenya incorrecta"}), 401
    return render_template("login.html")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return jsonify({"status": "ok", "message": "Logout fet"})

@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    try:
        user = current_user
        data = request.json
        user_message = data.get("message", "").strip()
        if not user_message:
            return jsonify({"error": "Cal enviar un missatge"}), 400

        model = data.get("model")
        if model not in [MODEL_PREMIUM, MODEL_FREE]:
            # Assignem model segons rol
            model = MODEL_PREMIUM if user.is_premium else MODEL_FREE

        # Recupera últims 10 missatges de la conversa de base de dades
        history_rows = Conversation.query.filter_by(user_id=user.id).order_by(Conversation.id.desc()).limit(10).all()
        history = [row.line for row in reversed(history_rows)]

        messages_list = [{"role": "system", "content": "You are a helpful assistant."}]
        for line in history:
            if line.startswith("Usuari: "):
                messages_list.append({"role": "user", "content": line[len("Usuari: "):]})
            elif line.startswith("Assistència: "):
                messages_list.append({"role": "assistant", "content": line[len("Assistència: "):]})

        messages_list.append({"role": "user", "content": user_message})

        bot_reply = query_openrouter(messages_list, model)

        db.session.add(Conversation(user_id=user.id, line=f"Usuari: {user_message}"))
        db.session.add(Conversation(user_id=user.id, line=f"Assistència: {bot_reply}"))
        db.session.commit()

        return jsonify({"reply": bot_reply, "history": history + [
            f"Usuari: {user_message}", f"Assistència: {bot_reply}"
        ]})
    except Exception as e:
        print(f"[ERROR] Exception en /api/chat: {e}")
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────
# Rutes autenticació amb Google Gmail (Flask-Dance)
# ─────────────────────────────

@app.route("/google_login/callback")
def google_login_callback():
    if not google.authorized:
        return redirect(url_for("google.login"))
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        flash("Error accedint a Google profile")
        return redirect(url_for("index"))
    info = resp.json()
    email = info["email"]

    user = User.query.filter_by(username=email).first()
    if not user:
        user = User(username=email, password="", is_premium=False)
        db.session.add(user)
        db.session.commit()

    login_user(user)
    flash("Login correcte amb Gmail!")
    return redirect(url_for("index"))

# ─────────────────────────────
# Rutes per activar premium amb clau
# ─────────────────────────────

@app.route("/premium/generate_key")
@login_required
def premium_generate_key():
    # Protegeix aquesta ruta per admin si vols
    key = secrets.token_hex(16)
    premium_key = PremiumKey(key=key)
    db.session.add(premium_key)
    db.session.commit()
    return jsonify({"generated_key": key})

@app.route("/premium/activate", methods=["POST"])
@login_required
def premium_activate():
    data = request.json
    key = data.get("key", "")
    premium_key = PremiumKey.query.filter_by(key=key, used=False).first()
    if premium_key:
        premium_key.used = True
        current_user.is_premium = True
        db.session.commit()
        return jsonify({"status": "ok", "message": "Compte premium activat!"})
    else:
        return jsonify({"status": "error", "message": "Clau invàlida o ja usada."}), 400

# ─────────────────────────────
# Ruta principal i creador taules DB
# ─────────────────────────────

@app.route("/", methods=["GET"])
@login_required
def index():
    # Carrega converses últimes 10 missatges de current_user per la vista inicial
    history_rows = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.id.desc()).limit(10).all()
    history = [row.line for row in reversed(history_rows)]
    return render_template("index.html", history=history)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
