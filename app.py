import os
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# ─────────────────────────────
# Configuració
# ─────────────────────────────
HF_API_TOKEN = os.environ.get("HF_API_TOKEN")  # defineix-ho a Render (Secret)
MODEL_NAME = os.environ.get("MODEL_NAME", "EleutherAI/gpt-neo-125M")

API_URL = f"https://api-inference.huggingface.co/models/{MODEL_NAME}"
HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"}

# Emmagatzemem historial de converses (en memòria)
conversations = {}


# ─────────────────────────────
# Funció auxiliar per cridar Hugging Face
# ─────────────────────────────
def query_huggingface(prompt, max_new_tokens=80, temperature=0.7, top_p=0.9):
    try:
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "return_full_text": False
            }
        }
        response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=60)

        if response.status_code == 404:
            return "⚠️ El model no existeix o no està carregat a Hugging Face."

        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
            return data[0]["generated_text"].strip()

        return "⚠️ No he pogut generar resposta, torna-ho a provar."

    except requests.exceptions.Timeout:
        return "⚠️ Temps d'espera esgotat amb Hugging Face."
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

        # Cridem Hugging Face
        bot_reply = query_huggingface(prompt)

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
