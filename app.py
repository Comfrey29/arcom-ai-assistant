# app.py
from flask import Flask, request, jsonify
from transformers import pipeline

app = Flask(__name__)

# --------------------------
# CONFIGURACIÓ DEL MODEL
# --------------------------
MODEL_NAME = "gpt2"  # Pots canviar a "distilgpt2" per menys pes
MAX_LENGTH = 100      # Nombre màxim de tokens generats
TEMPERATURE = 0.7     # Aleatorietat de la generació
TOP_K = 50            # Top-k sampling
TOP_P = 0.95          # Top-p sampling

# Pipeline de generació
generator = pipeline(
    "text-generation",
    model=MODEL_NAME,
)

# --------------------------
# ENDPOINTS
# --------------------------
@app.route("/")
def index():
    return "Servidor GPT-2 Mini actiu! Utilitza POST a /api/generate"

@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json()
    if not data or "prompt" not in data:
        return jsonify({"error": "No s'ha proporcionat 'prompt'"}), 400
    
    prompt = data["prompt"]
    
    # Generació del text
    output = generator(
        prompt,
        max_length=MAX_LENGTH,
        do_sample=True,
        temperature=TEMPERATURE,
        top_k=TOP_K,
        top_p=TOP_P,
        num_return_sequences=1
    )

    # Retornem només el text generat
    return jsonify({"text": output[0]["generated_text"]})

# --------------------------
# ARRANCADA
# --------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
