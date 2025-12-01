from flask import Flask, request, jsonify, send_file
import os
import csv
import pymysql
from datetime import datetime, time, timedelta
from flask_cors import CORS
import pytz
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

KST = pytz.timezone("Asia/Seoul")

app = Flask(__name__)

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

    if not file_exists:
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["camera_id", "room", "people_count", "timestamp"])

    with open(csv_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([camera_id, room, people_count, timestamp])


# ======================================
# 📌 업로드 API
# ======================================
@app.route('/upload', methods=['POST'])
def upload():
    try:
        data = request.get_json()

        camera_id = data.get("camera_id")
        room = data.get("room")
        people_count = data.get("people_count")
        timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

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
            "message": "Saved to MySQL",
            "received": data
        })

    except Exception as e:
        print("Upload Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ======================================
# 📌 최근 데이터 조회
# ======================================
@app.route('/people', methods=['GET'])
def get_people():
    try:
        limit = int(request.args.get('limit', 5))

        conn = connect_mysql()
        if conn is None:
            return jsonify({"status": "error", "message": "DB connect error"}), 500

        with conn.cursor() as cur:
            sql = "SELECT * FROM people_log ORDER BY id DESC LIMIT %s"
            cur.execute(sql, (limit,))
            rows = cur.fetchall()

        return jsonify({"status": "ok", "count": len(rows), "data": rows})

    except Exception as e:
        print("GetPeople Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ======================================
# 📌 날짜 기반 조회
# ======================================
@app.route('/people/date', methods=['GET'])
def get_people_by_date():
    try:
        date_str = request.args.get('date')

        if not date_str:
            return jsonify({
                "status": "error",
                "message": "date 파라미터 필요 (/people/date?date=YYYY-MM-DD)"
            }), 400

        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        start_dt = KST.localize(datetime.combine(date_obj, time.min))
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
# 📌 간단 CSV 다운로드
# ======================================
@app.route('/export_csv_simple', methods=['GET'])
def export_csv_simple():
    try:
        conn = connect_mysql()
        if conn is None:
            return jsonify({"status": "error", "message": "DB connect error"}), 500

        with conn.cursor() as cur:
            cur.execute("SELECT timestamp, people_count FROM people_log ORDER BY timestamp ASC")
            rows = cur.fetchall()

        if not rows:
            return jsonify({"status": "error", "message": "데이터 없음"}), 404

        filename = f"people_simple_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}.csv"

        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "time", "people_count"])

            for row in rows:
                ts = pd.to_datetime(row["timestamp"]).tz_localize("UTC").tz_convert(KST)
                writer.writerow([ts.strftime("%Y-%m-%d"), ts.strftime("%H:%M:%S"), row["people_count"]])

        return send_file(filename, mimetype="text/csv", as_attachment=True, download_name=filename)

    except Exception as e:
        print("ExportCSV Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ======================================
# 📌 시간대별 평균
# ======================================
@app.route('/analytics/hourly')
def hourly():
    try:
        conn = connect_mysql()
        if conn is None:
            return jsonify({"status": "error"}), 500

        with conn.cursor() as cur:
            cur.execute("SELECT timestamp, people_count FROM people_log ORDER BY timestamp ASC")
            rows = cur.fetchall()

        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["hour"] = df["timestamp"].dt.hour

        hourly_avg = df.groupby("hour")["people_count"].mean().to_dict()

        return jsonify({"status": "ok", "hourly_avg": hourly_avg})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ======================================
# 📌 요일별 평균
# ======================================
@app.route('/analytics/weekday')
def weekday():
    try:
        conn = connect_mysql()
        with conn.cursor() as cur:
            cur.execute("SELECT timestamp, people_count FROM people_log ORDER BY timestamp ASC")
            rows = cur.fetchall()

        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["weekday"] = df["timestamp"].dt.weekday

        weekday_avg = df.groupby("weekday")["people_count"].mean().to_dict()

        return jsonify({"status": "ok", "weekday_avg": weekday_avg})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ======================================
# 📌 예측 API
# ======================================
@app.route("/analytics/predict", methods=["GET"])
def predict_next_week():
    try:
        conn = connect_mysql()
        with conn.cursor() as cursor:
            query = """
                SELECT timestamp, people_count
                FROM people
                ORDER BY timestamp ASC
            """
            cursor.execute(query)
            rows = cursor.fetchall()
        conn.close()

        # 데이터 없으면 fallback 처리
        if not rows or len(rows) < 5:
            future_time = datetime.now() + timedelta(days=7)
            return jsonify({
                "status": "ok",
                "fallback": True,
                "predict_next_week": 0,
                "future_time": future_time.strftime("%Y-%m-%d %H:%M:%S")
            })

        # DataFrame 변환
        df = pd.DataFrame(rows)

        # timestamp를 datetime으로 변환 + 타임존 제거
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)

        # null timestamp 삭제
        df = df.dropna(subset=["timestamp"])

        # 최근 1주 데이터만 사용
        seven_days_ago = df["timestamp"].max() - pd.Timedelta(days=7)
        df_week = df[df["timestamp"] >= seven_days_ago]

        if df_week.empty:
            df_week = df.copy()

        # ---------------------------
        #  옵션 C — 요일 + 시간대 평균 예측
        # ---------------------------
        df_week["weekday"] = df_week["timestamp"].dt.weekday   # 월=0, 일=6
        df_week["hour"] = df_week["timestamp"].dt.hour

        now = datetime.now()
        target_weekday = now.weekday()
        target_hour = now.hour

        # 요일 & 시간대가 같은 데이터만 추출
        group = df_week[
            (df_week["weekday"] == target_weekday) &
            (df_week["hour"] == target_hour)
        ]

        if group.empty:
            # 동일 시간대 없으면 전체 평균으로 fallback
            predicted = float(df_week["people_count"].mean())
            fallback = True
        else:
            predicted = float(group["people_count"].mean())
            fallback = False

        # 미래 시간 = 현재 + 7일
        future_time = now + timedelta(days=7)

        return jsonify({
            "status": "ok",
            "fallback": fallback,
            "predict_next_week": round(predicted, 2),
            "future_time": future_time.strftime("%Y-%m-%d %H:%M:%S")
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })


# ======================================
# 📌 MySQL 연결 테스트
# ======================================
@app.route('/test_mysql')
def test_mysql():
    conn = connect_mysql()
    if conn is None:
        return jsonify({"status": "error"})

    with conn.cursor() as cur:
        cur.execute("SELECT 1 AS result")
        res = cur.fetchone()

    return jsonify({"status": "ok", "result": res})


@app.route('/')
def home():
    return "<h2>Flask + MySQL + CSV 자동 백업 서버 작동 중!</h2>"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
