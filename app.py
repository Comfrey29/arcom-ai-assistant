import os
import json
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session

app = Flask(__name__)
app.config['SECRET_KEY'] = 'una_clau_molt_secreta_i_llarga'

USERS_FILE = 'users.json'

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Omple tots els camps')
            return redirect(url_for('register'))
        users = load_users()
        if username in users:
            flash('Aquest usuari ja existeix')
            return redirect(url_for('register'))
        users[username] = {"password": password}  # Guardar password en pla (millor xifrat)
        save_users(users)
        flash('Registre completat! Ara pots iniciar sessió.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_users()
        if username in users and users[username]['password'] == password:
            session['username'] = username
            flash('Login efectuat!')
            return redirect(url_for('index'))
        flash('Credencials incorrectes')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Sessió tancada')
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return f"Benvingut/da, {session['username']}!"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), debug=True)
