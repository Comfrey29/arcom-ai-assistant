import os
import zipfile
import requests
from flask import Flask, render_template, request

app = Flask(__name__)

# ID del fitxer gran a Google Drive
FILE_ID = "1b935e39cf9893108bd2f4fb5317f48ae1c3ab5e"
ZIP_DEST = "model.zip"
MODEL_DIR = "model"

def download_and_extract_large_file(file_id, destination):
    URL = "https://drive.google.com/uc?export=download"
    session = requests.Session()
    response = session.get(URL, params={"id": file_id}, stream=True)

    # Cerca la cookie de confirmació
    confirm_token = None
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            confirm_token = value
            break

    if confirm_token:
        response = session.get(URL, params={"id": file_id, "confirm": confirm_token}, stream=True)

    # Escriu el fitxer
    with open(destination, "wb") as f:
        for chunk in response.iter_content(32768):
            if chunk:
                f.write(chunk)

    print("Descarregat! Comprovant fitxer...")
    if os.path.getsize(destination) < 100:
        raise ValueError("Fitxer massa petit, descàrrega fallida")

    # Descomprimir
    print("Descomprimit...")
    with zipfile.ZipFile(destination, 'r') as zip_ref:
        zip_ref.extractall(MODEL_DIR)
    print("Model llest a", MODEL_DIR)

# Comprova si ja està descarregat i descomprimit
if not os.path.exists(MODEL_DIR):
    print("Descarregant model del Drive...")
    download_and_extract_large_file(FILE_ID, ZIP_DEST)

@app.route("/")
def index():
    return "<h1>Model carregat i llest per usar!</h1>"

@app.route("/predict", methods=["POST"])
def predict():
    text = request.form.get("text")
    # Aquí afegeix la lògica de predicció amb el teu model
    return {"input": text, "prediction": "aquí la resposta del model"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
