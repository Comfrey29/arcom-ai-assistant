import os
import zipfile
from io import BytesIO
from flask import Flask, jsonify, request
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
MODEL_ID = "1USzqA-lmhhJtZuBdgaFjqYeMzMlO70IQ"
MODEL_ZIP_PATH = "models/model.zip"
MODEL_DIR = "models/distilgpt2"

creds = None
model = None
tokenizer = None

def get_drive_service():
    global creds
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('drive', 'v3', credentials=creds)

def download_model_zip():
    service = get_drive_service()
    request_drive = service.files().get_media(fileId=MODEL_ID)
    fh = BytesIO()
    downloader = MediaIoBaseDownload(fh, request_drive)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            print(f"Descàrrega: {int(status.progress() * 100)}%")
    fh.seek(0)
    os.makedirs(os.path.dirname(MODEL_ZIP_PATH), exist_ok=True)
    with open(MODEL_ZIP_PATH, "wb") as f:
        f.write(fh.read())
    # Descomprimeix
    with zipfile.ZipFile(MODEL_ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(MODEL_DIR)

def load_model():
    global model, tokenizer
    if model is None or tokenizer is None:
        model = AutoModelForCausalLM.from_pretrained(MODEL_DIR)
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
        model.eval()

@app.route('/model/download', methods=['GET'])
def model_download():
    try:
        download_model_zip()
        return jsonify({"message": "Model descarregat i descomprès correctament"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/model/infer', methods=['POST'])
def model_infer():
    try:
        data = request.json
        text_input = data.get('input', '')
        if not text_input:
            return jsonify({"error": "Cal enviar text d'entrada"}), 400
        load_model()
        inputs = tokenizer.encode(text_input, return_tensors='pt')
        outputs = model.generate(inputs, max_length=50)
        result = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return jsonify({"generated_text": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return "Servidor actiu"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
