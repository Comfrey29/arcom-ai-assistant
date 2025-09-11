from flask import Flask, jsonify, request
import os

app = Flask(__name__)

# Ruta arrel per provar que l'app funciona
@app.route('/')
def home():
    return "La teva app està funcionant! 🎉"

# API de generació de text
@app.route('/api/generate/stream', methods=['GET'])
def generate_stream():
    # Obtenim els paràmetres de la query string
    prompt = request.args.get('prompt', '')
    max_tokens = int(request.args.get('max_tokens', 256))
    temperature = float(request.args.get('temperature', 0.7))
    top_p = float(request.args.get('top_p', 0.95))
    
    # Aquí aniria la lògica de generació real
    # Per exemple amb OpenAI o un model local
    # De moment retornem una resposta simulada
    result = f"Resposta simulada per al prompt: {prompt}"

    return jsonify({"result": result, "prompt": prompt, "max_tokens": max_tokens, "temperature": temperature, "top_p": top_p})

# Entrypoint per executar localment (i Render detecta PORT)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))  # Render passa el port aquí
    app.run(host='0.0.0.0', port=port, debug=True)
