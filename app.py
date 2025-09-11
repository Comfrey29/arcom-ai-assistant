from flask import Flask, request, jsonify
from transformers import pipeline

app = Flask(__name__)

# No carreguem el model al start, només quan arribi la primera petició
model_pipeline = None

@app.route("/")
def home():
    return "AI Web App running!"

@app.route("/generate", methods=["POST"])
def generate():
    global model_pipeline
    # Carreguem GPT-2 a demanda
    if model_pipeline is None:
        model_pipeline = pipeline("text-generation", model="gpt2", device=-1)  # device=-1 força CPU

    data = request.get_json()
    prompt = data.get("prompt", "")
    max_length = data.get("max_length", 50)

    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    try:
        output = model_pipeline(prompt, max_length=max_length, num_return_sequences=1)
        return jsonify({"generated_text": output[0]["generated_text"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

