from flask import Flask, request, jsonify 
#request: 클라이언트가 보낸 데이터 읽을 때 사용
#jsonify: python Dict -> JSON으로 변환해서 응답할 때 사용
import sqlite3, pandas as pd, time, threading
#tiem: 현재 시간 기록용

app = Flask(__name__)
DB_PATH = 'crowd.db'
CSV_PATH = 'crowd_backup.csv'

# ------------------------------
# 1. DB 초기화 (테이블 없으면 생성)
# ------------------------------
def init_db():
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
    print("✅ SQLite DB 초기화 완료")

# ------------------------------
# 2. 데이터 삽입 함수
# ------------------------------
def insert_data(room, count):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO crowd (room, count, time) VALUES (?, ?, ?)',
              (room, count, time.strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

# ------------------------------
# 3. 최근 데이터 조회
# ------------------------------
def get_recent_data(limit=20):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT room, count, time FROM crowd ORDER BY id DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    return [{'room': r, 'count': c, 'time': t} for (r, c, t) in rows]

# ------------------------------
# 4. CSV 백업 함수
# ------------------------------
def backup_csv():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query('SELECT * FROM crowd', conn)
    df.to_csv(CSV_PATH, index=False)
    conn.close()
    print(f"💾 CSV 백업 완료 ({len(df)}행 저장)")

def backup_loop():
    while True:
        backup_csv()
        time.sleep(300)  # 5분마다 자동 백업

# ------------------------------
# 5. Flask 라우트
# ------------------------------
#'/': 기본 주소, 단순히 서버 상태를 확인하는 테스트용 
@app.route('/')
def home():
    return "📡 Flask + SQLite 서버 작동 중!"

#POST 요청이 들어오면 실행되는 함수
@app.route('/upload', methods=['POST']) 
def upload():
    try:
        content = request.json #클라이언트가 보낸 JSON데이터 python dict로 불러옴

        #유효성 검사와 기본 값 설정
        room = content.get('room', 'unknown') #측정 장소
        count = int(content.get('count',0)) #감지된 인원수
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S') #저장 시각

        #감지된 데이터를 SQLite DB에 저장
        insert_data(room, count)
        print(f"[DB저장] {room}: {count}명 ({timestamp})")

        #클라이언트에게 JSON응답을 돌려줌
        return jsonify({'status': 'ok', 'message': f'{room} 인원 {count}명 저장됨'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

#GET 요청이 오명 최근 데이터를 반환
@app.route('/api/data', methods=['GET'])
def api_data():
    return jsonify(get_recent_data())

# ------------------------------
# 6. 메인 실행
# ------------------------------
if __name__ == '__main__':
    init_db()
    threading.Thread(target=backup_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)