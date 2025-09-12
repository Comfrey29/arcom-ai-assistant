import os
import requests
from flask import Flask, request, jsonify

# Flask app
app = Flask(__name__)

# Configuració Hugging Face API
HF_API_TOKEN = os.environ.get("HF_API_TOKEN")  # defineix-ho a Render com secret
MODEL_NAME = "gpt2"  # GPT-2 Mini (lleuger)

API_URL = f"https://api-inference.huggingface.co/models/{MODEL_NAME}"
HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"}

# Emmagatzematge de converses en memòria (per usuari si cal)
conversations = {}


def query_huggingface(prompt, max_new_tokens=60, temperature=0.7, top_p=0.95):
    """Envia un prompt a la Hugging Face API i retorna la resposta"""
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
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and "generated_text" in data[0]:
            return data[0]["generated_text"].strip()
        return "[Sense resposta]"
    except Exception as e:
        return f"Error en la generació: {str(e)}"


@app.route("/api/chat", methods=["POST"])
def chat():
    """Endpoint de xat (com ChatGPT) amb context de conversa"""
    try:
        data = request.json
        user_id = data.get("user_id", "default")  # permet separar converses per usuari
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"error": "Cal enviar un missatge"}), 400

        # Recuperem la conversa anterior
        history = conversations.get(user_id, [])

        # Afegim el nou missatge de l'usuari
        history.append(f"Usuari: {user_message}")

        # Construïm el prompt amb context
        prompt = "\n".join(history) + "\nAssistència:"

        # Generem resposta amb HF
        bot_reply = query_huggingface(prompt)

        # Afegim resposta de l'assistent a l'historial
        history.append(f"Assistència: {bot_reply}")
        conversations[user_id] = history[-10:]  # limitem a les últimes 10 interaccions

        return jsonify({
            "reply": bot_reply,
            "history": history
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "Servidor GPT-2 Mini actiu!"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
