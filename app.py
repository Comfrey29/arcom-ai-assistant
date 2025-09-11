from flask import Flask, request, jsonify, Response
import requests
import os
import json
import time

app = Flask(__name__)

# ======================================================
# CONFIGURACIÓ DE L'API DE HUGGING FACE
# ======================================================
HF_API_TOKEN = os.getenv("HF_API_TOKEN")  # Posa aquí el teu token Hugging Face
HF_MODEL = "gpt2"  # Pots canviar-ho pel model que vulguis

HF_HEADERS = {
    "Authorization": f"Bearer {HF_API_TOKEN}",
    "Content-Type": "application/json"
}

# ======================================================
# PÀGINA PRINCIPAL
# ======================================================
@app.route("/", methods=["GET"])
def index():
    return "<h1>Servidor AI Actiu!</h1><p>Prova la ruta /api/generate amb POST.</p>"

# ======================================================
# GENERACIÓ DE TEXT NORMAL
# ======================================================
@app.route("/api/generate", methods=["POST"])
def generate_text():
    data = request.json
    prompt = data.get("prompt", "")
    max_length = data.get("max_length", 100)

    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": max_length},
    }

    response = requests.post(
        f"https://api-inference.huggingface.co/models/{HF_MODEL}",
        headers=HF_HEADERS,
        data=json.dumps(payload)
    )

    if response.status_code != 200:
        return jsonify({"error": response.text}), response.status_code

    result = response.json()
    # Hugging Face retorna l'output a result[0]['generated_text'] per GPT-2
    text = result[0]["generated_text"] if isinstance(result, list) else str(result)
    return jsonify({"response": text})

# ======================================================
# STREAMING SIMPLIFICAT
# ======================================================
@app.route("/api/generate/stream", methods=["POST"])
def generate_stream():
    data = request.json
    prompt = data.get("prompt", "")
    max_length = data.get("max_length", 100)

    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": max_length},
    }

    # Crida a Hugging Face
    response = requests.post(
        f"https://api-inference.huggingface.co/models/{HF_MODEL}",
        headers=HF_HEADERS,
        data=json.dumps(payload)
    )

    if response.status_code != 200:
        return jsonify({"error": response.text}), response.status_code

    result = response.json()
    text = result[0]["generated_text"] if isinstance(result, list) else str(result)

    # Funció generadora per fer streaming
    def generate_chunks(text, chunk_size=20):
        for i in range(0, len(text), chunk_size):
            yield text[i:i+chunk_size]
            time.sleep(0.1)  # Simula streaming

    return Response(generate_chunks(text), mimetype="text/plain")

# ======================================================
# EXECUCIÓ DEL SERVIDOR
# ======================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
.0.0", port=port)
