import os
from flask import Flask, request, jsonify, stream_with_context, Response
import requests

app = Flask(__name__)

# Configuració Hugging Face
HF_API_TOKEN = os.getenv("HF_API_TOKEN")
HF_MODEL = "gpt2"  # pots canviar a un model més petit si vols

HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"}
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"


def query_hf(prompt, max_tokens=256, temperature=0.7, top_p=0.95):
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "return_full_text": False,
        },
        "options": {"wait_for_model": True},
    }
    response = requests.post(HF_API_URL, headers=HEADERS, json=payload)
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, list) and "generated_text" in data[0]:
            return data[0]["generated_text"]
        else:
            return str(data)
    else:
        return f"[ERROR HF API] {response.status_code}: {response.text}"


@app.route("/api/generate/stream")
def generate_stream():
    prompt = request.args.get("prompt", "")
    max_tokens = int(request.args.get("max_tokens", 256))
    temperature = float(request.args.get("temperature", 0.7))
    top_p = float(request.args.get("top_p", 0.95))

    def generate():
        # crida única a HF API per cada prompt
        text = query_hf(prompt, max_tokens, temperature, top_p)
        yield text

    return Response(stream_with_context(generate()), mimetype="text/plain")


@app.route("/")
def home():
    return app.send_static_file("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

