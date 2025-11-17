from flask import Flask, request, jsonify
import pymysql
import time

app = Flask(__name__)

# ------------------------------
# 1. MariaDB 연결 설정
# ------------------------------
DB_CONFIG = {
    "host": "127.0.0.1",       # 로컬이므로 localhost 또는 127.0.0.1
    "user": "root",            # 본인 설정
    "password": "sanhae",  # 설치 시 설정한 root 비밀번호
    "database": "crowd_db",    # 아까 만든 DB 이름
    "port": 3306,
    "charset": "utf8mb4"
}

def get_conn():
    return pymysql.connect(**DB_CONFIG)

# ------------------------------
# 2. 테이블 생성
# ------------------------------
def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS crowd (
            id INT AUTO_INCREMENT PRIMARY KEY,
            room VARCHAR(50),
            count INT,
            time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ MariaDB 테이블 초기화 완료")

# ------------------------------
# 3. 데이터 삽입
# ------------------------------
def insert_data(room, count):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO crowd (room, count) VALUES (%s, %s)", (room, count))
    conn.commit()
    cur.close()
    conn.close()

# ------------------------------
# 4. 최근 데이터 조회
# ------------------------------
def get_recent_data(limit=20):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT room, count, time FROM crowd ORDER BY id DESC LIMIT %s", (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"room": r, "count": c, "time": str(t)} for (r, c, t) in rows]

# ------------------------------
# 5. Flask 라우트
# ------------------------------
@app.route('/')
def home():
    return "📡 Flask + MariaDB 서버 작동 중!"

@app.route('/upload', methods=['POST'])
def upload():
    try:
        content = request.json
        room = content.get('room', 'unknown')
        count = int(content.get('count', 0))
        insert_data(room, count)
        print(f"[DB저장] {room}: {count}명 ({time.strftime('%Y-%m-%d %H:%M:%S')})")
        return jsonify({'status': 'ok', 'message': f'{room} 인원 {count}명 저장됨'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/data')
def api_data():
    return jsonify(get_recent_data())

# ------------------------------
# 6. 실행
# ------------------------------
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
