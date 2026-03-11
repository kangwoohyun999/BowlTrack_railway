from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'bowling_secret_key_2025'

DATA_FILE = 'data.json'

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_data():
    data = load_data()
    username = session.get('username')
    if not username or username not in data['users']:
        return None
    return data['users'][username]

def save_user_data(user_data):
    data = load_data()
    username = session.get('username')
    data['users'][username] = user_data
    save_data(data)

# ── Routes ──────────────────────────────────────────────

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        data = load_data()
        user = data['users'].get(username)
        if user and user['password'] == password:
            session['username'] = username
            return redirect(url_for('home'))
        return render_template('login.html', error='아이디 또는 비밀번호가 틀렸습니다.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        nickname = request.form.get('nickname', '').strip() or username
        data = load_data()
        if username in data['users']:
            return render_template('register.html', error='이미 존재하는 아이디입니다.')
        data['users'][username] = {
            'password': password,
            'nickname': nickname,
            'style': 'dumless',
            'status': '볼링이 좋아 🎳',
            'dark_mode': False,
            'records': {},
            'strikes': 0,
            'spares': 0,
            'misses': 0,
        }
        save_data(data)
        session['username'] = username
        return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = get_user_data()
    return render_template('home.html', user=user, username=session['username'])

@app.route('/calendar')
def calendar():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = get_user_data()
    return render_template('calendar.html', user=user)

@app.route('/stats')
def stats():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = get_user_data()
    total = user['strikes'] + user['spares'] + user['misses']
    def pct(v): return round(v / total * 100, 1) if total > 0 else 0
    return render_template('stats.html', user=user,
        strike_pct=pct(user['strikes']),
        spare_pct=pct(user['spares']),
        miss_pct=pct(user['misses']))

@app.route('/info')
def info():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = get_user_data()
    return render_template('info.html', user=user)

@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = get_user_data()
    return render_template('profile.html', user=user)

@app.route('/settings')
def settings():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = get_user_data()
    return render_template('settings.html', user=user)

# ── API ─────────────────────────────────────────────────

@app.route('/api/save_record', methods=['POST'])
def save_record():
    if 'username' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    body = request.get_json()
    date  = body.get('date')
    score = body.get('score')
    note  = body.get('note', '')
    strikes = int(body.get('strikes', 0))
    spares  = int(body.get('spares', 0))
    misses  = int(body.get('misses', 0))
    user = get_user_data()
    user['records'][date] = {'score': score, 'note': note,
        'strikes': strikes, 'spares': spares, 'misses': misses}
    user['strikes'] += strikes
    user['spares']  += spares
    user['misses']  += misses
    save_user_data(user)
    return jsonify({'ok': True})

@app.route('/api/get_records')
def get_records():
    if 'username' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    user = get_user_data()
    return jsonify(user.get('records', {}))

@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    if 'username' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    body = request.get_json()
    user = get_user_data()
    if 'nickname' in body: user['nickname'] = body['nickname']
    if 'status'   in body: user['status']   = body['status']
    save_user_data(user)
    return jsonify({'ok': True})

@app.route('/api/update_settings', methods=['POST'])
def update_settings():
    if 'username' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    body = request.get_json()
    user = get_user_data()
    if 'style'     in body: user['style']     = body['style']
    if 'dark_mode' in body: user['dark_mode'] = body['dark_mode']
    save_user_data(user)
    return jsonify({'ok': True})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
