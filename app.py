
import os
from fastapi import FastAPI
from pydantic import BaseModel
import torch
from transformers import GPT2LMHeadModel, GPT2Tokenizer
import gdown

app = FastAPI()

# ---------- CONFIGURACIÓ MODEL ----------
MODEL_ID = "TU_ID_DEL_MODEL"  # Substitueix amb l'ID del fitxer a Google Drive
MODEL_PATH = "models/gpt2-117M"

# ---------- DESCARREGA MODEL SI NO EXISTEIX ----------
if not os.path.exists(MODEL_PATH):
    os.makedirs(MODEL_PATH)
    url = f"https://drive.google.com/uc?id={MODEL_ID}"
    zip_file = os.path.join(MODEL_PATH, "gpt2-117M.zip")
    print("Descarregant model des de Google Drive...")
    gdown.download(url, zip_file, quiet=False)
    os.system(f"unzip {zip_file} -d {MODEL_PATH}")

# ---------- CARREGAR MODEL ----------
tokenizer = GPT2Tokenizer.from_pretrained(MODEL_PATH)
model = GPT2LMHeadModel.from_pretrained(MODEL_PATH)

# ---------- DEFINIR L’ESQUEMA DE PREGUNTA ----------
class Question(BaseModel):
    text: str

# ---------- ENDPOINT API ----------
@app.post("/ask")
def ask(q: Question):
    inputs = tokenizer.encode(q.text, return_tensors="pt")
    outputs = model.generate(inputs, max_length=100, do_sample=True)
    answer = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return {"answer": answer}
