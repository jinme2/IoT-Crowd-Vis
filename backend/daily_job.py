import os
import csv
import pandas as pd
import pymysql
from datetime import datetime, time, timedelta
import pytz

KST = pytz.timezone("Asia/Seoul")

# MySQL 연결
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


# 1) MySQL → Daily CSV 백업
def export_daily_csv():
    today = datetime.now(KST).strftime("%Y-%m-%d")
    filename = f"daily_backup/people_{today}.csv"
    os.makedirs("daily_backup", exist_ok=True)

    conn = connect_mysql()
    if not conn:
        print("DB 연결 실패 (백업 중단)")
        return None

    with conn.cursor() as cur:
        sql = """
        SELECT timestamp, people_count
        FROM people_log
        ORDER BY timestamp ASC
        """
        cur.execute(sql)
        rows = cur.fetchall()

    if not rows:
        print("오늘 데이터 없음")
        return None

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "people_count"])
        for row in rows:
            writer.writerow([row["timestamp"], row["people_count"]])

    print("백업 완료:", filename)
    return filename


# 2) CSV integrity 체크
def validate_csv(filepath):
    if not filepath or not os.path.exists(filepath):
        return False
        
    df = pd.read_csv(filepath)
    if len(df) < 10:
        return False
    return True


# 3) all_data.csv 업데이트
def merge_all_data(daily_path):
    all_path = "all_data.csv"

    df_daily = pd.read_csv(daily_path)

    if os.path.exists(all_path):
        df_all = pd.read_csv(all_path)
        df_merge = pd.concat([df_all, df_daily]).drop_duplicates()
    else:
        df_merge = df_daily

    df_merge.to_csv(all_path, index=False, encoding="utf-8-sig")
    print("누적 데이터 업데이트 완료.")
    return all_path


# 5) 분석 – 시간별 평균
def hourly_avg(df):
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["hour"] = df["timestamp"].dt.hour
    return df.groupby("hour")["people_count"].mean().to_dict()


# 6) 분석 – 요일별 패턴
def weekday_profile(df):
    df["weekday"] = df["timestamp"].dt.weekday
    return df.groupby("weekday")["people_count"].mean().to_dict()


# 7) 예측
from sklearn.linear_model import LinearRegression

def predict_next_week(df):
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["minute"] = df["timestamp"].astype("int64") // 10**9
    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.weekday

    X = df[["minute", "hour", "weekday"]]
    y = df["people_count"]

    model = LinearRegression()
    model.fit(X, y)

    future = datetime.now(KST) + timedelta(days=7)
    future_minute = int(future.timestamp())
    hour = datetime.now(KST).hour
    weekday = datetime.now(KST).weekday()

    pred = model.predict([[future_minute, hour, weekday]])[0]
    return float(pred)


# ⭐ 여기 clear_mysql() 추가됨
def clear_mysql():
    conn = connect_mysql()
    if conn is None:
        print("MySQL 연결 실패 → 데이터 삭제 건너뜀")
        return
    with conn.cursor() as cur:
        cur.execute("DELETE FROM people_log")
        conn.commit()
    print("MySQL 데이터 전체 삭제 완료")


# 메인 실행 함수
def run_daily_job():
    print("==== DAILY JOB START ====")

    daily_file = export_daily_csv()
    if not validate_csv(daily_file):
        print("CSV 검증 실패 → MySQL 삭제 중단")
        return

    all_csv = merge_all_data(daily_file)

    df = pd.read_csv(all_csv)
    hour_avg = hourly_avg(df)
    weekday_avg = weekday_profile(df)
    next_week_prediction = predict_next_week(df)

    result = {
        "hour_avg": hour_avg,
        "weekday_avg": weekday_avg,
        "next_week_predict": next_week_prediction,
        "timestamp": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    }

    with open("nightly_result.json", "w", encoding="utf-8") as f:
        f.write(str(result))

    print("예측 및 분석 완료:", result)
    print("==== DAILY JOB END ====")


if __name__ == "__main__":
    run_daily_job()
    clear_mysql()  # ✔ 백업 및 분석 완료 후 전체 삭제
