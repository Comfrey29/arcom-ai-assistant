import os
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# ─────────────────────────────
# Configuració OpenRouter.ai
# ─────────────────────────────
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")  # defineix-ho a Render (Secret)
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json"
}

# Emmagatzemem historial de converses (en memòria)
conversations = {}

# ─────────────────────────────
# Funció auxiliar per cridar OpenRouter.ai GPT-3.5
# ─────────────────────────────
def query_openrouter(prompt):
    try:
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 80
        }
        response = requests.post(OPENROUTER_API_URL, headers=HEADERS, json=payload, timeout=60)
        if response.status_code == 401:
            return "⚠️ Clau API no vàlida o no configurada."
        response.raise_for_status()
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        return "⚠️ No he pogut generar resposta, torna-ho a provar."
    except requests.exceptions.Timeout:
        return "⚠️ Temps d'espera esgotat amb OpenRouter.ai."
    except Exception as e:
        return f"⚠️ Error inesperat: {str(e)}"

# ─────────────────────────────
# Endpoint de xat
# ─────────────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        user_id = data.get("user_id", "default")
        user_message = data.get("message", "").strip()
        if not user_message:
            return jsonify({"error": "Cal enviar un missatge"}), 400

        # Recuperem historial
        history = conversations.get(user_id, [])
        history.append(f"Usuari: {user_message}")

        # Construïm prompt
        prompt = "\n".join(history) + "\nAssistència:"

        # Cridem OpenRouter.ai
        bot_reply = query_openrouter(prompt)

        # Afegim resposta a historial
        history.append(f"Assistència: {bot_reply}")
        conversations[user_id] = history[-10:]  # només últimes 10 interaccions

        return jsonify({"reply": bot_reply, "history": history})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────
# UI bàsica (frontend estil ChatGPT)
# ─────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# ─────────────────────────────
# Inici app
# ─────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
