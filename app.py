from flask import Flask, request, jsonify
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

app = Flask(__name__)

# --- CONFIGURACIÓ DEL MODEL ---
MODEL_NAME = "distilgpt2"  # més lleuger que gpt2, ideal per 512MB
MAX_LENGTH = 100            # longitud màxima de la resposta
TEMPERATURE = 0.7           # controla la creativitat

# Carreguem model i tokenizer una sola vegada
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

# Historial curt per xat (només últim prompt)
last_prompt = ""

@app.route("/")
def index():
    return "Servidor GPT-2 Mini funcionant!"

@app.route("/api/generate", methods=["POST"])
def generate():
    global last_prompt
    data = request.get_json()

    if not data or "prompt" not in data:
        return jsonify({"error": "No s'ha proporcionat cap prompt"}), 400

    prompt = data["prompt"]
    last_prompt = prompt  # opcional: guardar últim prompt

    # Tokenització
    inputs = tokenizer.encode(prompt, return_tensors="pt").to(device)

    # Generació de text
    with torch.no_grad():
        outputs = model.generate(
            inputs,
            max_length=MAX_LENGTH,
            do_sample=True,
            temperature=TEMPERATURE,
            pad_token_id=tokenizer.eos_token_id
        )

    text = tokenizer.decode(outputs[0], skip_special_tokens=True)

    return jsonify({"response": text})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
