# app.py
# Per a Render: start command: gunicorn app:app --bind 0.0.0.0:$PORT --workers 1
import os
import io
import zipfile
import requests
import time
import threading
from functools import partial
from flask import Flask, request, jsonify, Response, send_from_directory, render_template_string

# Mode i paràmetres via env
MODEL_LOCAL_DIR = os.environ.get("MODEL_LOCAL_DIR")  # exemple: "./models"
HF_API_TOKEN = os.environ.get("HF_API_TOKEN")        # token per Hugging Face Inference API (si fas servir remota)
HF_MODEL = os.environ.get("HF_MODEL", "gpt2")        # model remòt si no carregues local (ex: "gpt2" o "DeepESP/gpt2-spanish")
DRIVE_FILE_ID = os.environ.get("DRIVE_FILE_ID")      # (opcional) google drive file id d'un .zip amb el model
DRIVE_DEST_ZIP = "/tmp/model_from_drive.zip"
PORT = int(os.environ.get("PORT", 5000))

app = Flask(__name__, static_folder="static", template_folder="templates")

# --- Optional: Download from Google Drive (supports large file confirm token flow) ---
def download_file_from_google_drive(id, destination):
    """
    Baixa fitxer públic de Google Drive tractant el confirm token (fitxers grans que Google no escaneja).
    """
    URL = "https://docs.google.com/uc?export=download"
    session = requests.Session()
    response = session.get(URL, params={'id': id}, stream=True)
    token = None
    for k, v in response.cookies.items():
        if k.startswith("download_warning"):
            token = v
            break
    if token:
        response = session.get(URL, params={'id': id, 'confirm': token}, stream=True)
    CHUNK_SIZE = 32768
    with open(destination, "wb") as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk:
                f.write(chunk)
    return destination

def extract_zip_to_dir(zip_path, target_dir):
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(target_dir)

# --- Model loading (lazy) ---
use_local = False
model = None
tokenizer = None

def try_prepare_local_model():
    global use_local, model, tokenizer
    if not MODEL_LOCAL_DIR:
        return False
    # only try once
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer
        import torch
    except Exception as e:
        app.logger.warning("Transformers/torch no instal·lats o no disponibles: %s", e)
        return False

    # Si DRIVE_FILE_ID existeix i el directori no conté fitxers, intenta descarregar
    if DRIVE_FILE_ID and (not os.path.isdir(MODEL_LOCAL_DIR) or len(os.listdir(MODEL_LOCAL_DIR)) == 0):
        app.logger.info("Descarregant model des de Google Drive...")
        try:
            download_file_from_google_drive(DRIVE_FILE_ID, DRIVE_DEST_ZIP)
            extract_zip_to_dir(DRIVE_DEST_ZIP, MODEL_LOCAL_DIR)
            app.logger.info("Descarregat i descomprimid al directori %s", MODEL_LOCAL_DIR)
        except Exception as e:
            app.logger.exception("Error baixant/descompriment model Drive: %s", e)
            return False

    # comprovem que hi ha fitxers necessaris
    required = ["config.json"]
    if not os.path.isdir(MODEL_LOCAL_DIR):
        app.logger.warning("MODEL_LOCAL_DIR no existeix: %s", MODEL_LOCAL_DIR)
        return False
    files = os.listdir(MODEL_LOCAL_DIR)
    if not any(name in files for name in required):
        app.logger.warning("MODEL_LOCAL_DIR no sembla contenir el model (no hi ha config.json). Contingut: %s", files)
        return False

    app.logger.info("Carregant model local des de %s ... (pot trigar un moment)", MODEL_LOCAL_DIR)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_LOCAL_DIR)
    model = AutoModelForCausalLM.from_pretrained(MODEL_LOCAL_DIR)
    use_local = True
    app.logger.info("Model local carregat correctament.")
    return True

# Intentem carregar local al startup si hi ha MODEL_LOCAL_DIR
try:
    if MODEL_LOCAL_DIR:
        try_prepare_local_model()
except Exception as e:
    app.logger.exception("Error pre-carant model local: %s", e)

# If not local, check if HF_API_TOKEN is present -> we will use InferenceClient
use_remote = False
inference_client = None
if not use_local and HF_API_TOKEN:
    try:
        from huggingface_hub import InferenceClient
        inference_client = InferenceClient(token=HF_API_TOKEN, model=HF_MODEL)
        use_remote = True
        app.logger.info("Usant Hugging Face Inference API (model=%s)", HF_MODEL)
    except Exception as e:
        app.logger.exception("No s'ha pogut crear InferenceClient: %s", e)

# --- Utility: stream response as SSE ---
def sse_format(data: str, event: str = None):
    """Format per SSE: 'data: ...\\n\\n' i opcional event"""
    lines = data.splitlines()
    payload = ""
    if event:
        payload += f"event: {event}\n"
    for line in lines:
        payload += f"data: {line}\n"
    payload += "\n"
    return payload

# --- Generation backends ---
def stream_from_remote_chat(messages, max_tokens=256, temperature=0.7, top_p=0.95):
    """
    Utilitza Hugging Face InferenceClient.chat_completion amb stream=True
    i yielda tokens en text pla per SSE.
    """
    if not inference_client:
        yield sse_format("Error: InferenceClient no inicialitzat.", "error")
        return
    try:
        for chunk in inference_client.chat_completion(messages, max_tokens=max_tokens, stream=True, temperature=temperature, top_p=top_p):
            # chunk.choices[0].delta.content podria existir
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            token = ""
            try:
                # structure similar to OpenAI delta
                token = choices[0].delta.content or ""
            except Exception:
                token = ""
            if token:
                yield sse_format(token)
    except Exception as e:
        yield sse_format(f"\n[ERROR REMOTE] {e}", "error")

def stream_from_local(prompt, max_new_tokens=128, temperature=0.7, top_p=0.95):
    """
    Utilitza transformers.TextIteratorStreamer per stream de tokens.
    """
    try:
        from transformers import TextIteratorStreamer
        import torch
    except Exception as e:
        yield sse_format(f"Error: transformers/TextIteratorStreamer no disponible: {e}", "error")
        return

    # prepare input
    inputs = tokenizer(prompt, return_tensors="pt")
    input_ids = inputs["input_ids"]
    # Move model to CPU/GPU automatic (render typical is CPU)
    device = next(model.parameters()).device
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

    generation_kwargs = dict(
        input_ids=input_ids,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        temperature=temperature,
        top_p=top_p,
        streamer=streamer,
    )

    # run generation in thread
    def run_gen():
        try:
            model.generate(**generation_kwargs)
        except Exception as e:
            app.logger.exception("Error en generate(): %s", e)

    thread = threading.Thread(target=run_gen)
    thread.start()

    # iterate streamer
    for chunk in streamer:
        # each chunk typically is a str token
        yield sse_format(chunk)

    thread.join()

# --- Flask routes ---
INDEX_HTML = """
<!doctype html>
<html lang="ca">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Arcom AI — Chat</title>
<style>
body{font-family:system-ui, Arial, sans-serif;background:#0b1221;color:#e6eef8;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.container{width:820px;background:#081029;border-radius:8px;padding:20px;box-shadow:0 10px 30px rgba(0,0,0,.6)}
#chat{height:480px;overflow:auto;border:1px solid rgba(255,255,255,0.04);padding:12px;border-radius:6px;background:#061024}
.msg{margin:8px 0;padding:8px;border-radius:6px}
.user{background:#093554;text-align:right}
.bot{background:#132034}
.controls{display:flex;gap:8px;margin-top:10px}
input[type=text]{flex:1;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.06);background:#02101a;color:#fff}
button{padding:10px 14px;border-radius:6px;border:none;background:#1b6fb3;color:#fff;cursor:pointer}
small{color:#99a0b0}
.param{display:inline-block;margin-right:12px}
</style>
</head>
<body>
<div class="container">
  <h2>Arcom AI — Chat</h2>
  <div id="chat"></div>
  <div class="controls">
    <input id="input" type="text" placeholder="Escriu la teva pregunta..." />
    <button id="send">Envia</button>
    <button id="clear">Neteja</button>
  </div>
  <div style="margin-top:8px">
    <label class="param">Max tokens <input id="max" type="number" value="256" min="1" max="2048" /></label>
    <label class="param">Temp <input id="temp" type="number" value="0.7" step="0.1" min="0.1" max="2" /></label>
    <label class="param">Top-p <input id="top" type="number" value="0.95" step="0.05" min="0.1" max="1" /></label>
  </div>
  <p style="margin-top:10px"><small>Mode: <strong>{{ mode }}</strong> — {{ note }}</small></p>
</div>

<script>
const chat = document.getElementById("chat");
const input = document.getElementById("input");
const send = document.getElementById("send");
const clear = document.getElementById("clear");
const maxEl = document.getElementById("max");
const tempEl = document.getElementById("temp");
const topEl = document.getElementById("top");

function appendMessage(text, cls="bot"){
  const d = document.createElement("div");
  d.className = "msg " + cls;
  d.textContent = text;
  chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight;
}

send.onclick = () => { sendMessage(); }
input.addEventListener("keydown", (e)=>{ if(e.key === "Enter") sendMessage(); });

clear.onclick = ()=>{ chat.innerHTML = ""; };

function sendMessage(){
  const text = input.value.trim();
  if(!text) return;
  appendMessage(text, "user");
  input.value = "";
  // placeholder for bot answer
  const botPlaceholder = document.createElement("div");
  botPlaceholder.className = "msg bot";
  botPlaceholder.textContent = "";
  chat.appendChild(botPlaceholder);
  chat.scrollTop = chat.scrollHeight;

  const params = {
    prompt: text,
    max_tokens: parseInt(maxEl.value||256),
    temperature: parseFloat(tempEl.value||0.7),
    top_p: parseFloat(topEl.value||0.95)
  };

  const evtSource = new EventSource("/api/generate/stream?" + new URLSearchParams(params));
  evtSource.onmessage = (e) => {
    // data is the token chunk
    botPlaceholder.textContent += e.data;
    chat.scrollTop = chat.scrollHeight;
  };
  evtSource.addEventListener("error", (e)=>{
    // show error
    botPlaceholder.textContent += "\\n[ERROR]";
    evtSource.close();
  });
  evtSource.addEventListener("end", (e)=>{
    // finished
    evtSource.close();
  });
}

</script>
</body>
</html>
"""

@app.route("/")
def index():
    mode = "local" if use_local else ("remote-HF" if use_remote else "none")
    note = ""
    if use_local:
        note = f"Local model carregat a {MODEL_LOCAL_DIR}"
    elif use_remote:
        note = f"Usant Hugging Face Inference API: {HF_MODEL}"
    else:
        note = "Cap model disponible: configura MODEL_LOCAL_DIR o HF_API_TOKEN"
    return render_template_string(INDEX_HTML, mode=mode, note=note)

@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json()
    prompt = data.get("prompt", "")
    max_tokens = int(data.get("max_tokens", 256))
    temperature = float(data.get("temperature", 0.7))
    top_p = float(data.get("top_p", 0.95))
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    # Simple synchronous call returning final text (non-streaming)
    if use_local:
        # local naive generation (non-streaming fallback)
        inputs = tokenizer(prompt, return_tensors="pt")
        outputs = model.generate(**inputs, max_new_tokens=max_tokens, do_sample=True, temperature=temperature, top_p=top_p)
        text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return jsonify({"response": text})
    elif use_remote:
        # remote non-streaming via InferenceClient
        messages = [{"role":"user","content": prompt}]
        result = inference_client.chat_completion(messages, max_tokens=max_tokens, temperature=temperature, top_p=top_p, stream=False)
        # result may be an object; convert to string
        try:
            text = result.choices[0].message.content
        except Exception:
            text = str(result)
        return jsonify({"response": text})
    else:
        return jsonify({"error":"No backend model configured"}), 500

@app.route("/api/generate/stream")
def api_generate_stream():
    # SSE streaming endpoint; query params used
    prompt = request.args.get("prompt") or ""
    max_tokens = int(request.args.get("max_tokens", 256))
    temperature = float(request.args.get("temperature", 0.7))
    top_p = float(request.args.get("top_p", 0.95))
    if not prompt:
        return Response(sse_format("Error: no prompt"), mimetype="text/event-stream")

    def gen():
        try:
            if use_local:
                for chunk in stream_from_local(prompt, max_new_tokens=max_tokens, temperature=temperature, top_p=top_p):
                    yield chunk
            elif use_remote:
                # prepare messages array for chat_completion
                messages = [{"role":"user","content": prompt}]
                for chunk in stream_from_remote_chat(messages, max_tokens=max_tokens, temperature=temperature, top_p=top_p):
                    yield chunk
            else:
                yield sse_format("No backend model configurat.", "error")
            # signal end
            yield sse_format("[DONE]", "end")
        except GeneratorExit:
            app.logger.info("Client tancat la connexió SSE")
        except Exception as e:
            app.logger.exception("Error streaming: %s", e)
            yield sse_format(f"[ERROR] {e}", "error")

    return Response(gen(), mimetype="text/event-stream")

@app.route("/healthz")
def health():
    return jsonify({"ok": True, "mode": "local" if use_local else ("remote" if use_remote else "none")})

if __name__ == "__main__":
    # debug local
    app.run(host="0.0.0.0", port=PORT, debug=False)
