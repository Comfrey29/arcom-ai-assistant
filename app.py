from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Ruta principal
@app.route("/", methods=["GET"])
def home():
    return "La teva app està funcionant amb GPT-2 Mini i Hugging Face!", 200

# Ruta per generar text amb Hugging Face
@app.route("/api/generate/stream", methods=["POST"])
def generate_stream():
    data = request.json
    prompt = data.get("prompt", "")

    if not prompt:
        return jsonify({"error": "No s'ha proporcionat cap prompt"}), 400

    hf_api_token = os.environ.get("HF_API_TOKEN")
    if not hf_api_token:
        return jsonify({"error": "No hi ha token de Hugging Face configurat"}), 500

    # Endpoint del model GPT-2 Mini de Hugging Face
    model_id = "gpt2"  # pots canviar-ho per "gpt2-mini" si existeix al HF
    url = f"https://api-inference.huggingface.co/models/{model_id}"

    headers = {
        "Authorization": f"Bearer {hf_api_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 100},
        "options": {"wait_for_model": True}
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        return jsonify({"error": "Error a Hugging Face", "details": response.text}), 500

    result = response.json()
    return jsonify(result), 200

# Arrencada de l'app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
