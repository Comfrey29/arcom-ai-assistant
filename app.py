import os
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# ─────────────────────────────
# Configuració OpenRouter.ai amb debug i models configurables
# ─────────────────────────────
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
print("Clau OpenRouter carregada?", bool(OPENROUTER_API_KEY))
OPENROUTER_API_URL = "https://openrouter.ai/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json"
}

# Noms dels models, ajusta segons disponibilitat
MODEL_PREMIUM = "openai/gpt-3.5-turbo"       # Ex: model de pagament
MODEL_FREE = "openai/deepseek-chat"          # Ex: model gratuït o d’assaig

# Emmagatzematge memòria conversa per usuari
conversations = {}

def query_openrouter(prompt, model):
    try:
        if not OPENROUTER_API_KEY:
            return "⚠️ La clau OPENROUTER_API_KEY no està configurada."
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 80
        }
        response = requests.post(OPENROUTER_API_URL, headers=HEADERS, json=payload, timeout=30)
        # Debug resposta raw
        print(f"[DEBUG] Codi resposta: {response.status_code}")
        print(f"[DEBUG] Resposta text: {repr(response.text)}")

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


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        user_id = data.get("user_id", "default")
        user_message = data.get("message", "").strip()
        user_type = data.get("user_type", "free")

        if not user_message:
            return jsonify({"error": "Cal enviar un missatge"}), 400

        # Selecció model segons user_type
        model = MODEL_PREMIUM if user_type == "premium" else MODEL_FREE

        history = conversations.get(user_id, [])
        history.append(f"Usuari: {user_message}")
        prompt = "\n".join(history) + "\nAssistència:"

        bot_reply = query_openrouter(prompt, model)

        history.append(f"Assistència: {bot_reply}")
        conversations[user_id] = history[-10:]

        return jsonify({"reply": bot_reply, "history": history})

    except Exception as e:
        print(f"[ERROR] Exception en /api/chat: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
