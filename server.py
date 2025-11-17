from flask import Flask, request, jsonify
import sqlite3, pandas as pd, time, threading, os

app = Flask(__name__)

DB_PATH = 'crowd.db'
CSV_PATH = 'crowd_backup.csv'

# ------------------------------
# CSV → DB 복구 함수
# ------------------------------
def restore_db_from_csv():
    if not os.path.exists(CSV_PATH):
        print("⚠ CSV 백업 파일 없음 → 복구 스킵")
        return

    try:
        df = pd.read_csv(CSV_PATH)

        conn = sqlite3.connect(DB_PATH)
        df.to_sql('crowd', conn, if_exists='append', index=False)
        conn.close()
        print(f"🔄 CSV → DB 복구 완료 ({len(df)}행 복구됨)")

    except Exception as e:
        print(f"❌ CSV 복구 중 오류 발생: {e}")


# ------------------------------
# DB 초기화
# ------------------------------
def init_db():
    db_exists = os.path.exists(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS crowd(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT,
            count INTEGER,
            time TEXT
        )
    ''')
    conn.commit()
    conn.close()

    # DB가 새로 만들어졌고 CSV가 있다면 복구
    if not db_exists and os.path.exists(CSV_PATH):
        print("📁 DB 없음 + CSV 존재 → DB 복구 시작")
        restore_db_from_csv()
    else:
        print("✅ DB 초기화 완료")


# ------------------------------
#  데이터 삽입
# ------------------------------
def insert_data(room, count):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO crowd (room, count, time) VALUES (?, ?, ?)',
              (room, count, time.strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()


# ------------------------------
# 최근 데이터 조회
# ------------------------------
def get_recent_data(limit=20):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT room, count, time FROM crowd ORDER BY id DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    return [{'room': r, 'count': c, 'time': t} for (r, c, t) in rows]


# ------------------------------
# CSV 백업
# ------------------------------
def backup_csv():
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query('SELECT * FROM crowd', conn)
        df.to_csv(CSV_PATH, index=False)
        conn.close()
        print(f"💾 CSV 백업 완료 ({len(df)}행 저장)")
    except Exception as e:
        print(f"❌ CSV 백업 오류: {e}")


def backup_loop():
    while True:
        backup_csv()
        time.sleep(300)  # 5분마다 자동 백업


# ------------------------------
# 라우트
# ------------------------------
@app.route('/')
def home():
    return "📡 Flask + SQLite 서버 작동 중! (CSV 자동 복구 기능 포함)"


@app.route('/upload', methods=['POST'])
def upload():
    try:
        content = request.json
        room = content.get('room', 'unknown')
        count = int(content.get('count', 0))

        insert_data(room, count)
        print(f"[DB저장] {room}: {count}명")

        return jsonify({'status': 'ok', 'message': f'{room} 인원 {count}명 저장됨'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/data', methods=['GET'])
def api_data():
    return jsonify(get_recent_data())


# ------------------------------
# DB/CSV 초기화
# ------------------------------
@app.route('/reset', methods=['POST'])
def reset_db():
    try:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        if os.path.exists(CSV_PATH):
            os.remove(CSV_PATH)
        init_db()  # 새로 생성
        return {"status": "ok", "message": "DB + CSV 초기화 완료"}
    except Exception as e:
        return {"status": "error", "message": str(e)}



# ------------------------------
# 메인 실행
# ------------------------------
if __name__ == '__main__':
    init_db()
    threading.Thread(target=backup_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
