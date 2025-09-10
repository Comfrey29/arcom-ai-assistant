import os
import zipfile
import requests
from flask import Flask, request, jsonify
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

app = Flask(__name__)

# --------------------------
# Configuració del model
# --------------------------
DRIVE_LINK = os.getenv("MODEL_DRIVE_LINK", "https://drive.google.com/uc?export=download&id=1NKLojHuwv3VKvjO_dSwkujMBrI_kjeGH")
MODEL_PATH = "gpt2-spanish"
CORP_NAME = os.getenv("CORPORATION_NAME", "ArCom Corporation")

# --------------------------
# Funció per descarregar i descomprimir
# --------------------------
def download_and_extract_model():
    if not os.path.exists(MODEL_PATH):
        print("Descarregant el model del Drive...")
        r = requests.get(DRIVE_LINK, stream=True)
        zip_file = "gpt2-spanish.zip"
        with open(zip_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Descomprimit...")
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall(MODEL_PATH)
        print("Model llest!")

# --------------------------
# Inicialitzar model
# --------------------------
download_and_extract_model()

print("Carregant tokenizer i model...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForCausalLM.from_pretrained(MODEL_PATH)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
print(f"{CORP_NAME} AI Ready!")

# --------------------------
# Endpoint principal
# --------------------------
@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "No question provided"}), 400

    inputs = tokenizer.encode(question, return_tensors="pt").to(device)
    outputs = model.generate(inputs, max_length=200, pad_token_id=tokenizer.eos_token_id)
    answer = tokenizer.decode(outputs[0], skip_special_tokens=True)

    return jsonify({
        "corporation": CORP_NAME,
        "question": question,
        "answer": answer
    })

# --------------------------
# Ruta de test
# --------------------------
@app.route("/", methods=["GET"])
def index():
    return f"Benvingut a l'assistent d'IA de {CORP_NAME}!"

# --------------------------
# Iniciar Flask
# --------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
