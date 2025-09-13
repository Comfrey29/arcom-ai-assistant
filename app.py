import os
import pickle
import requests
from flask import Flask, request, jsonify, render_template
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from io import BytesIO
from googleapiclient.http import MediaIoBaseDownload

app = Flask(__name__, template_folder="templates", static_folder="static")

# Google Drive API config
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = None

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

# Endpoint per llistar fitxers a Drive
@app.route("/drive/files", methods=["GET"])
def list_files():
    try:
        service = get_drive_service()
        results = service.files().list(pageSize=10, fields="files(id, name)").execute()
        items = results.get('files', [])
        return jsonify({"files": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint per descarregar fitxer de Drive per id
@app.route("/drive/download/<file_id>", methods=["GET"])
def download_file(file_id):
    try:
        service = get_drive_service()
        request_drive = service.files().get_media(fileId=file_id)
        downloader = MediaIoBaseDownload(BytesIO(), request_drive)
        done = False
        fh = BytesIO()
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"Download {int(status.progress() * 100)}%.")
        fh.seek(0)
        os.makedirs('models', exist_ok=True)
        local_path = os.path.join('models', f"{file_id}.bin")
        with open(local_path, "wb") as f:
            f.write(fh.read())
        return jsonify({"message": f"File {file_id} downloaded to {local_path}."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Hugging Face API config per inferència remota
HF_API_TOKEN = os.environ.get("HF_API_TOKEN")
MODEL_NAME = "distilgpt2"
API_URL = f"https://api-inference.huggingface.co/models/{MODEL_NAME}"
HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"}

def query_huggingface(prompt, max_new_tokens=80, temperature=0.7, top_p=0.95):
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "return_full_text": False,
        }
    }
    response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list) and "generated_text" in data[0]:
        return data[0]["generated_text"].strip()
    return "[Sense resposta]"

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        user_id = data.get("user_id", "default")
        user_message = data.get("message", "").strip()
        if not user_message:
            return jsonify({"error": "Cal enviar un missatge"}), 400
        prompt = f"Usuari: {user_message}\nAssistència:"
        bot_reply = query_huggingface(prompt)
        return jsonify({"reply": bot_reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
