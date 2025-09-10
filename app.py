import os
import zipfile
import requests
from flask import Flask, request, jsonify
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# ---------------------------
# CONFIGURACIÓ
# ---------------------------
MODEL_DRIVE_ID = "1NKLojHuwv3VKvjO_dSwkujMBrI_kjeGH"
MODEL_URL = f"https://drive.google.com/uc?export=download&id={MODEL_DRIVE_ID}"
MODEL_ZIP_PATH = "gpt2-spanish.zip"
MODEL_DIR = "gpt2-spanish"

# ---------------------------
# FUNCIONS
# ---------------------------
def download_and_extract_model():
    """Descarrega el model del Drive i el descomprimeix si cal."""
    if not os.path.exists(MODEL_DIR):
        print("Descarregant el model del Drive...")
        response = requests.get(MODEL_URL, stream=True)
        with open(MODEL_ZIP_PATH, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Descomprimit...")
        with zipfile.ZipFile(MODEL_ZIP_PATH, "r") as zip_ref:
            zip_ref.extractall(MODEL_DIR)
        print("Model llest!")

# ---------------------------
# INICIALITZACIÓ
# ---------------------------
download_and_extract_model()

print("Carregant tokenizer i model...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForCausalLM.from_pretrained(MODEL_DIR)
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)
print("Model carregat!")

# ---------------------------
# FLASK APP
# ---------------------------
app = Flask(__name__)

@app.route("/ask", methods=["POST"])
def ask():
    """Endpoint per fer preguntes al model."""
    data = request.json
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "No question provided"}), 400

    inputs = tokenizer(question, return_tensors="pt").to(device)
    outputs = model.generate(**inputs, max_new_tokens=100, pad_token_id=tokenizer.eos_token_id)
    answer = tokenizer.decode(outputs[0], skip_special_tokens=True)

    return jsonify({"question": question, "answer": answer})

@app.route("/healthz", methods=["GET"])
def health():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
