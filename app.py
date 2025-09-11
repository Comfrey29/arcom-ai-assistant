from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

load_dotenv()  # Carrega variables del .env

HF_API_TOKEN = os.getenv("HF_API_TOKEN")
HF_MODEL = "gpt2"  # Pots canviar a qualsevol model de Hugging Face

HEADERS = {
    "Authorization": f"Bearer {HF_API_TOKEN}"
}

app = Flask(__name__)

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    prompt = data.get("prompt", "")
    max_length = data.get("max_length", 50)

    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": max_length}
    }

    response = requests.post(
        f"https://api-inference.huggingface.co/models/{HF_MODEL}",
        headers=HEADERS,
        json=payload
    )

    if response.status_code != 200:
        return jsonify({"error": response.text}), response.status_code

    result = response.json()
    generated_text = result[0]["generated_text"] if isinstance(result, list) else str(result)
    return jsonify({"generated_text": generated_text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

