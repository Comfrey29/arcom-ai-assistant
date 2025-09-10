from flask import Flask, request, jsonify
import torch
import os
import requests
import zipfile

app = Flask(__name__)

# --- Configuració ---
DRIVE_ZIP_URL = "https://drive.google.com/uc?id=1NKLojHuwv3VKvjO_dSwkujMBrI_kjeGH"  # Enllaç directe per descarregar
MODEL_DIR = "/tmp/model"
MODEL_PATH = os.path.join(MODEL_DIR, "gpt2-spanish.pt")  # Ajusta segons el nom dins del zip

# --- Funció per descarregar i extreure ---
def download_and_extract_model():
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)

    zip_file_path = os.path.join(MODEL_DIR, "model.zip")
    if not os.path.exists(MODEL_PATH):
        print("Descarregant model del Drive...")
        r = requests.get(DRIVE_ZIP_URL)
        with open(zip_file_path, "wb") as f:
            f.write(r.content)

        print("Descomprimit...")
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(MODEL_DIR)
        print("Model llest!")

# --- Carregar model ---
download_and_extract_model()
model = torch.load(MODEL_PATH, map_location=torch.device('cpu'))
model.eval()

# --- Endpoint per fer preguntes ---
@app.route("/ask", methods=["POST"])
def ask():
    data = request.json
    question = data.get("question", "")
    # Aquí posa la lògica per generar resposta segons el model
    # Exemple placeholder:
    answer = f"Has preguntat: {question}. [Aquí va la resposta del model]"
    return jsonify({"answer": answer})

# --- Run Flask ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
