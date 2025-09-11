import os
from flask import Flask, request, render_template
from transformers import pipeline, set_seed

# Inicialització Flask
app = Flask(__name__)

# Llegim variables d'entorn
HF_API_TOKEN = os.getenv("HF_API_TOKEN")
HF_MODEL = os.getenv("HF_MODEL", "gpt2")  # Si no hi ha, agafa gpt2 per defecte

# Inicialitzem el model Hugging Face amb token
try:
    generator = pipeline(
        "text-generation",
        model=HF_MODEL,
        device=-1,  # CPU
        use_auth_token=HF_API_TOKEN
    )
except Exception as e:
    print("[ERROR] No s'ha pogut carregar el model:", e)
    generator = None

@app.route("/", methods=["GET", "POST"])
def index():
    output = ""
    if request.method == "POST":
        prompt = request.form.get("prompt", "")
        if generator:
            try:
                set_seed(42)  # opcional: per reproduïbilitat
                result = generator(prompt, max_length=100, do_sample=True)
                output = result[0]["generated_text"]
            except Exception as e:
                output = f"[ERROR] {e}"
        else:
            output = "[ERROR] Model no carregat"
    return render_template("index.html", output=output)

if __name__ == "__main__":
    # Port 10000 per defecte, Render usarà PORT a l'entorn
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
