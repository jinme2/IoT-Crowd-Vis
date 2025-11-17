from flask import Flask, request, jsonify
import os
import time
import threading
import pandas as pd
import sqlite3
import pymysql

app = Flask(__name__)

# ======================================================
# 🔥 1. 환경 기반 DB 모드 선택 (MySQL / SQLite 자동 전환)
# ======================================================

USE_MYSQL = os.environ.get("MYSQLHOST") is not None  # Render면 자동 True

if USE_MYSQL:
    # Railway MySQL 사용
    DB_CONFIG = {
        "host": os.environ["MYSQLHOST"],
        "port": int(os.environ["MYSQLPORT"]),
        "user": os.environ["MYSQLUSER"],
        "password": os.environ["MYSQLPASSWORD"],
        "database": os.environ["MYSQLDATABASE"],
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }

    def get_conn():
        return pymysql.connect(**DB_CONFIG)

else:
    # 로컬 SQLite + CSV 백업 사용
    DB_PATH = 'crowd.db'
    CSV_PATH = 'crowd_backup.csv'

    def get_conn():
        return sqlite3.connect(DB_PATH)


# ======================================================
# 🔥 2. DB 초기화
# ======================================================

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    if USE_MYSQL:
        # MySQL 테이블 생성
        cur.execute("""
            CREATE TABLE IF NOT EXISTS crowd (
                id INT AUTO_INCREMENT PRIMARY KEY,
                room VARCHAR(50),
                count INT,
                time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ MySQL DB 준비 완료")

    else:
        # SQLite 테이블 생성
        cur.execute("""
            CREATE TABLE IF NOT EXISTS crowd(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room TEXT,
                count INTEGER,
                time TEXT
            )
        """)
        print("✅ SQLite DB 초기화 완료")

        # CSV → DB 복구 (SQLite일 때만)
        if os.path.exists(DB_PATH) and os.path.exists(CSV_PATH):
            try:
                df = pd.read_csv(CSV_PATH)
                df.to_sql('crowd', conn, if_exists='append', index=False)
                print(f"🔄 CSV → DB 복구 완료 ({len(df)}행)")
            except Exception as e:
                print(f"❌ CSV 복구 중 오류: {e}")

    conn.commit()
    conn.close()


# ======================================================
# 🔥 3. 데이터 삽입
# ======================================================

def insert_data(room, count):
    conn = get_conn()
    cur = conn.cursor()

    now_time = time.strftime('%Y-%m-%d %H:%M:%S')

    if USE_MYSQL:
        cur.execute(
            "INSERT INTO crowd (room, count, time) VALUES (%s, %s, %s)",
            (room, count, now_time)
        )
    else:
        cur.execute(
            "INSERT INTO crowd (room, count, time) VALUES (?, ?, ?)",
            (room, count, now_time)
        )

    conn.commit()
    conn.close()


# ======================================================
# 🔥 4. 최근 데이터 조회
# ======================================================

def get_recent_data(limit=20):
    conn = get_conn()
    cur = conn.cursor()

    if USE_MYSQL:
        cur.execute(
            "SELECT room, count, time FROM crowd ORDER BY id DESC LIMIT %s",
            (limit,)
        )
    else:
        cur.execute(
            "SELECT room, count, time FROM crowd ORDER BY id DESC LIMIT ?",
            (limit,)
        )

    rows = cur.fetchall()
    conn.close()

    if USE_MYSQL:
        return rows  # MySQL은 dict로 반환됨
    else:
        return [{'room': r, 'count': c, 'time': t} for (r, c, t) in rows]


# ======================================================
# 🔥 5. CSV 백업 (SQLite 전용)
# ======================================================

def backup_csv():
    if USE_MYSQL:
        return  # Render에서는 CSV 의미 없음

    try:
        conn = get_conn()
        df = pd.read_sql_query("SELECT * FROM crowd", conn)
        df.to_csv("crowd_backup.csv", index=False)
        print(f"💾 CSV 백업 완료 ({len(df)}행)")
    except Exception as e:
        print(f"❌ CSV 백업 오류: {e}")


def backup_loop():
    while True:
        backup_csv()
        time.sleep(300)


# ======================================================
# 🔥 6. API 라우트
# ======================================================

@app.route('/')
def home():
    if USE_MYSQL:
        return "📡 Flask + Railway MySQL 서버 작동 중!"
    else:
        return "📡 Flask + SQLite + CSV 백업 서버 작동 중!"


@app.route('/upload', methods=['POST'])
def upload():
    try:
        content = request.json or {}
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


# SQLite 전용 초기화
@app.route('/reset', methods=['POST'])
def reset_db():
    if USE_MYSQL:
        return {"status": "error", "message": "MySQL 모드에서는 reset 불가"}

    try:
        if os.path.exists('crowd.db'):
            os.remove('crowd.db')
        if os.path.exists('crowd_backup.csv'):
            os.remove('crowd_backup.csv')

        init_db()
        return {"status": "ok", "message": "SQLite DB + CSV 초기화 완료"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ======================================================
# 🔥 7. 메인 실행
# ======================================================

if __name__ == '__main__':
    init_db()

    if not USE_MYSQL:
        threading.Thread(target=backup_loop, daemon=True).start()

    app.run(host='0.0.0.0', port=5000)
