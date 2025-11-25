from flask import Flask, request, jsonify
import os
import csv
import pymysql
from datetime import datetime, timedelta
from flask_cors import CORS
from flask import send_file
import pytz
import pandas as pd
KST = pytz.timezone("Asia/Seoul")

app = Flask(__name__)
#CORS(app)

CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "https://iot-11project.onrender.com/itcampus",
            "https://iot-11project.onrender.com"
        ]
    }
})


# ======================================
# 📌 MySQL 연결
# ======================================
def connect_mysql():
    try:
        conn = pymysql.connect(
            host=os.environ.get("MYSQLHOST"),
            user=os.environ.get("MYSQLUSER"),
            password=os.environ.get("MYSQLPASSWORD"),
            database=os.environ.get("MYSQLDATABASE"),
            port=int(os.environ.get("MYSQLPORT")),
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except Exception as e:
        print("MySQL Connect Error:", e)
        return None


# ======================================
# 📌 CSV 자동 백업 함수
# ======================================
def save_csv(camera_id, room, people_count, timestamp):
    csv_file = "backup.csv"
    file_exists = os.path.isfile(csv_file)

    # CSV 파일 없으면 헤더 추가하여 생성
    if not file_exists:
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["camera_id", "room", "people_count", "timestamp"])

    # 새 데이터 한 줄 append
    with open(csv_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([camera_id, room, people_count, timestamp])


# ======================================
# 📌 업로드 API (MySQL + CSV 동시 저장)
# ======================================
@app.route('/upload', methods=['POST'])
def upload():
    try:
        data = request.get_json()

        camera_id = data.get("camera_id")
        room = data.get("room")
        people_count = data.get("people_count")
        timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

        # CSV 백업 필요하면 사용
        # save_csv(camera_id, room, people_count, timestamp)

        conn = connect_mysql()
        if conn is None:
            return jsonify({"status": "error", "message": "DB connect error"}), 500

        with conn.cursor() as cur:
            sql = """
                INSERT INTO people_log (camera_id, room, people_count, timestamp)
                VALUES (%s, %s, %s, %s)
            """
            cur.execute(sql, (camera_id, room, people_count, timestamp))
            conn.commit()

        return jsonify({
            "status": "ok",
            "message": "Saved to MySQL + CSV",
            "received": data
        })

    except Exception as e:
        print("Upload Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

# ======================================
# 📌 인원 기록 조회 API
#     - GET /people
#     - 요청한 개수의 데이터 조회 또는 날짜 필터로 조회 가능 (예: /people?limit=5)
# ======================================
@app.route('/people', methods=['GET'])
def get_people():
    try:
        limit = int(request.args.get('limit', 5))  # 기본 5개

        conn = connect_mysql()
        if conn is None:
            return jsonify({"status": "error", "message": "DB connect error"}), 500

        with conn.cursor() as cur:
            sql = "SELECT * FROM people_log ORDER BY id DESC LIMIT %s"
            cur.execute(sql, (limit,))
            rows = cur.fetchall()

        return jsonify({
            "status": "ok",
            "count": len(rows),
            "data": rows
        })

    except Exception as e:
        print("GetPeople Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ======================================
# 📌 날짜 기반 조회 API
#     - GET /people/date?date=2025-11-24
#     - 해당 날짜의 00:00~현재시간(KST)까지 데이터 조회
# ======================================
@app.route('/people/date', methods=['GET'])
def get_people_by_date():
    try:
        date_str = request.args.get('date')  # YYYY-MM-DD 필수
        
        if not date_str:
            return jsonify({"status": "error", "message": "date 파라미터가 필요합니다. 예: /people/date?date=2025-11-24"}), 400

        # 날짜 파싱
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")

        # 해당 날짜의 00:00 (KST)
        start_dt = KST.localize(datetime.combine(date_obj, time.min))

        # 현재 시간 (KST)
        end_dt = datetime.now(KST)

        conn = connect_mysql()
        if conn is None:
            return jsonify({"status": "error", "message": "DB connect error"}), 500

        with conn.cursor() as cur:
            sql = """
                SELECT * FROM people_log
                WHERE timestamp BETWEEN %s AND %s
                ORDER BY id DESC
            """
            cur.execute(sql, (start_dt, end_dt))
            rows = cur.fetchall()

        return jsonify({
            "status": "ok",
            "count": len(rows),
            "data": rows,
            "range": {
                "start": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "end": end_dt.strftime("%Y-%m-%d %H:%M:%S")
            }
        })

    except Exception as e:
        print("GetPeopleByDate Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

# ======================================
# 📌 DB → CSV 백업 파일 다운로드 API
#     - GET /export_csv
#     - MySQL 전체 로그를 CSV로 파일 생성 후 다운로드
# ======================================

@app.route('/export_csv_simple', methods=['GET'])
def export_csv_simple():
    try:
        conn = connect_mysql()
        if conn is None:
            return jsonify({"status": "error", "message": "DB connect error"}), 500

        with conn.cursor() as cur:
            sql = "SELECT timestamp, people_count FROM people_log ORDER BY timestamp ASC"
            cur.execute(sql)
            rows = cur.fetchall()

        if not rows:
            return jsonify({"status": "error", "message": "데이터가 없습니다."}), 404

        # 파일명
        filename = f"people_simple_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}.csv"

        # CSV 생성
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "time", "people_count"])  # 헤더

            for row in rows:
                ts = row["timestamp"]

                # timestamp를 datetime으로 변환
                if isinstance(ts, str):
                    ts = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")

                ts_kst = ts.astimezone(KST)

                date_str = ts_kst.strftime("%Y-%m-%d")
                time_str = ts_kst.strftime("%H:%M:%S")
                count = row["people_count"]

                writer.writerow([date_str, time_str, count])

        # 파일 다운로드
        return send_file(
            filename,
            mimetype="text/csv",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        print("ExportCSV Simple Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

# ======================================
# 📌 시간대별 평균 (0~23시)
#     - GET /analytics/hourly
# ======================================
@app.route('/analytics/hourly', methods=['GET'])
def get_hourly_avg():
    try:
        conn = connect_mysql()
        if conn is None:
            return jsonify({"status": "error", "message": "DB connect error"}), 500
        
        with conn.cursor() as cur:
            sql = "SELECT timestamp, people_count FROM people_log ORDER BY timestamp ASC"
            cur.execute(sql)
            rows = cur.fetchall()
        
        if not rows:
            return jsonify({"status": "error", "message": "데이터 없음"}), 404
        
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["hour"] = df["timestamp"].dt.hour
        
        # 시간별 평균
        hourly_avg = df.groupby("hour")["people_count"].mean().to_dict()
        
        return jsonify({
            "status": "ok",
            "hourly_avg": hourly_avg
        })
    
    except Exception as e:
        print("Hourly Avg Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ======================================
# 📌 요일별 평균 (월=0 ~ 일=6)
#     - GET /analytics/weekday
# ======================================
@app.route('/analytics/weekday', methods=['GET'])
def get_weekday_avg():
    try:
        conn = connect_mysql()
        if conn is None:
            return jsonify({"status": "error", "message": "DB connect error"}), 500
        
        with conn.cursor() as cur:
            sql = "SELECT timestamp, people_count FROM people_log ORDER BY timestamp ASC"
            cur.execute(sql)
            rows = cur.fetchall()
        
        if not rows:
            return jsonify({"status": "error", "message": "데이터 없음"}), 404
        
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["weekday"] = df["timestamp"].dt.weekday
        
        weekday_avg = df.groupby("weekday")["people_count"].mean().to_dict()
        
        return jsonify({
            "status": "ok",
            "weekday_avg": weekday_avg
        })
    
    except Exception as e:
        print("Weekday Avg Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ======================================
# 📌 다음주 같은 시간대 예측
#     - GET /analytics/predict
# ======================================
from sklearn.linear_model import LinearRegression
import numpy as np

@app.route('/analytics/predict', methods=['GET'])
def get_prediction():
    try:
        conn = connect_mysql()
        if conn is None:
            return jsonify({"status": "error", "message": "DB connect error"}), 500
        
        with conn.cursor() as cur:
            sql = "SELECT timestamp, people_count FROM people_log ORDER BY timestamp ASC"
            cur.execute(sql)
            rows = cur.fetchall()
        
        if not rows or len(rows) < 20:
            return jsonify({"status": "error", "message": "학습 데이터 부족"}), 400
        
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        # 학습용 feature
        df["minute"] = df["timestamp"].astype(np.int64) // 10**9
        df["hour"] = df["timestamp"].dt.hour
        df["weekday"] = df["timestamp"].dt.weekday
        
        X = df[["minute", "hour", "weekday"]]
        y = df["people_count"]
        
        model = LinearRegression()
        model.fit(X, y)
        
        # 미래 7일 뒤
        future = datetime.now(KST) + timedelta(days=7)
        future_data = [
            int(future.timestamp()),
            future.hour,
            future.weekday()
        ]
        
        pred = float(model.predict([future_data])[0])
        
        return jsonify({
            "status": "ok",
            "predict_next_week": pred,
            "future_time": future.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    except Exception as e:
        print("Prediction Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ======================================
# 📌 MySQL 연결 테스트
# ======================================
@app.route('/test_mysql')
def test_mysql():
    conn = connect_mysql()
    if conn is None:
        return jsonify({"status": "error", "message": "MySQL connect failed"})

    with conn.cursor() as cur:
        cur.execute("SELECT 1 AS result")
        result = cur.fetchone()

    return jsonify({"status": "ok", "result": result})


@app.route('/')
def home():
    return "<h2>Flask + MySQL + CSV 자동 백업 서버 작동 중!</h2>"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
