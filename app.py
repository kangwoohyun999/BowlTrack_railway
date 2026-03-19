import os
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'bowling_secret_key_2025')

# ── DB 연결 ──────────────────────────────────────────────

def get_db_url():
    url = os.environ.get('DATABASE_URL', '')
    # Railway는 postgres:// 로 주는 경우가 있어 psycopg2용으로 변환
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url

def get_db():
    url = get_db_url()
    if not url:
        raise RuntimeError("DATABASE_URL 환경변수가 없습니다.")
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def init_db():
    """테이블이 없으면 생성"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id        SERIAL PRIMARY KEY,
            username  TEXT UNIQUE NOT NULL,
            password  TEXT NOT NULL,
            nickname  TEXT NOT NULL,
            style     TEXT NOT NULL DEFAULT 'dumless',
            status    TEXT NOT NULL DEFAULT '볼링이 좋아 🎳',
            dark_mode BOOLEAN NOT NULL DEFAULT FALSE,
            strikes   INTEGER NOT NULL DEFAULT 0,
            spares    INTEGER NOT NULL DEFAULT 0,
            misses    INTEGER NOT NULL DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id       SERIAL PRIMARY KEY,
            username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
            date     TEXT NOT NULL,
            score    INTEGER,
            note     TEXT DEFAULT '',
            strikes  INTEGER NOT NULL DEFAULT 0,
            spares   INTEGER NOT NULL DEFAULT 0,
            misses   INTEGER NOT NULL DEFAULT 0,
            UNIQUE (username, date)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("[DB] 테이블 초기화 완료")

def get_user(username):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        cur.close(); conn.close()
        return dict(row) if row else None
    except Exception as e:
        print(f"[get_user 오류] {e}")
        return None

# ── 앱 시작 시 테이블 생성 ───────────────────────────────

@app.before_request
def ensure_db():
    """첫 요청 전 DB 초기화 (gunicorn 멀티워커 안전)"""
    if request.path == '/health':
        return  # 헬스체크는 패스
    if not getattr(app, '_db_initialized', False):
        try:
            init_db()
            app._db_initialized = True
        except Exception as e:
            print(f"[DB 초기화 실패] {e}")
            return render_template('db_error.html'), 500

# ── Routes ──────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('home') if 'username' in session else url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        try:
            user = get_user(username)
        except Exception as e:
            print(f"[login 오류] {e}")
            return render_template('login.html', error='서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.')
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
        style    = request.form.get('style', 'dumless')

        if not username or not password:
            return render_template('register.html', error='아이디와 비밀번호를 입력해주세요.')

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (username, password, nickname, style) VALUES (%s, %s, %s, %s)",
                (username, password, nickname, style)
            )
            conn.commit()
            cur.close(); conn.close()
            session['username'] = username
            return redirect(url_for('home'))
        except psycopg2.errors.UniqueViolation:
            conn.rollback(); cur.close(); conn.close()
            return render_template('register.html', error='이미 존재하는 아이디입니다.')
        except Exception as e:
            print(f"[register 오류] {e}")
            return render_template('register.html', error=f'서버 오류: {str(e)}')
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = get_user(session['username'])
    if not user:
        session.pop('username', None)
        return redirect(url_for('login'))
    return render_template('home.html', user=user)

@app.route('/calendar')
def calendar():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = get_user(session['username'])
    if not user:
        return redirect(url_for('login'))
    return render_template('calendar.html', user=user)

@app.route('/stats')
def stats():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = get_user(session['username'])
    if not user:
        return redirect(url_for('login'))
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
    user = get_user(session['username'])
    if not user:
        return redirect(url_for('login'))
    return render_template('info.html', user=user)

@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = get_user(session['username'])
    if not user:
        return redirect(url_for('login'))
    return render_template('profile.html', user=user)

@app.route('/settings')
def settings():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = get_user(session['username'])
    if not user:
        return redirect(url_for('login'))
    return render_template('settings.html', user=user)

# ── API ─────────────────────────────────────────────────

@app.route('/api/save_record', methods=['POST'])
def save_record():
    if 'username' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    try:
        body     = request.get_json()
        username = session['username']
        date     = body.get('date')
        score    = body.get('score') or None
        note     = body.get('note', '')
        strikes  = int(body.get('strikes', 0))
        spares   = int(body.get('spares', 0))
        misses   = int(body.get('misses', 0))

        conn = get_db(); cur = conn.cursor()

        # 기존 기록 확인 (누적값 보정용)
        cur.execute("SELECT strikes, spares, misses FROM records WHERE username=%s AND date=%s",
                    (username, date))
        old = cur.fetchone()
        old_s  = old['strikes'] if old else 0
        old_sp = old['spares']  if old else 0
        old_m  = old['misses']  if old else 0

        cur.execute("""
            INSERT INTO records (username, date, score, note, strikes, spares, misses)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (username, date) DO UPDATE
            SET score=%s, note=%s, strikes=%s, spares=%s, misses=%s
        """, (username, date, score, note, strikes, spares, misses,
              score, note, strikes, spares, misses))

        cur.execute("""
            UPDATE users
            SET strikes = strikes - %s + %s,
                spares  = spares  - %s + %s,
                misses  = misses  - %s + %s
            WHERE username = %s
        """, (old_s, strikes, old_sp, spares, old_m, misses, username))

        conn.commit(); cur.close(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        print(f"[save_record 오류] {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_records')
def get_records():
    if 'username' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            "SELECT date, score, note, strikes, spares, misses FROM records WHERE username=%s",
            (session['username'],)
        )
        rows = cur.fetchall()
        cur.close(); conn.close()
        return jsonify({r['date']: dict(r) for r in rows})
    except Exception as e:
        print(f"[get_records 오류] {e}")
        return jsonify({}), 500

@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    if 'username' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    try:
        body = request.get_json()
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE users SET nickname=%s, status=%s WHERE username=%s",
                    (body.get('nickname'), body.get('status'), session['username']))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        print(f"[update_profile 오류] {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/update_settings', methods=['POST'])
def update_settings():
    if 'username' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    try:
        body = request.get_json()
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE users SET style=%s, dark_mode=%s WHERE username=%s",
                    (body.get('style'), body.get('dark_mode'), session['username']))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        print(f"[update_settings 오류] {e}")
        return jsonify({'error': str(e)}), 500

# ── 디버그용 헬스체크 ────────────────────────────────────

@app.route('/health')
def health():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close(); conn.close()
        return jsonify({'status': 'ok', 'db': 'connected'})
    except Exception as e:
        return jsonify({'status': 'error', 'db': str(e)}), 500

# ── 실행 ─────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
