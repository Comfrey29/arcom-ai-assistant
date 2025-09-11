import os
from flask import Flask, request, jsonify, render_template
from transformers import pipeline, set_seed

app = Flask(__name__)

# Configuració Hugging Face
HF_API_TOKEN = os.getenv("HF_API_TOKEN")
HF_MODEL = "gpt2"  # Pots posar qualsevol model de Hugging Face

# Inicialitzem generator com a None; el carregarem sota demanda
generator = None

def load_model():
    global generator
    if generator is None:
        generator = pipeline(
            "text-generation",
            model=HF_MODEL,
            use_auth_token=HF_API_TOKEN,
            device=-1  # CPU, important per tenir poca RAM
        )

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        data = request.get_json()
        prompt = data.get("prompt", "")
        output = "[ERROR] Model no carregat"

        if prompt:
            try:
                load_model()  # Carreguem el model només aquí
                set_seed(42)
                result = generator(prompt, max_length=100, do_sample=True)
                output = result[0]["generated_text"]
            except Exception as e:
                output = f"[ERROR] {e}"
        return jsonify({"output": output})

    # GET: retornem la pàgina HTML
    return render_template("index.html")

if __name__ == "__main__":
    # Port i host per Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
