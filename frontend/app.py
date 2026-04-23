from flask import Flask, render_template, url_for

app = Flask(__name__, static_folder="static")  # 정적 파일 폴더 지정

@app.route("/")
def home():
    return render_template("campusMap.html") 

@app.route("/itcampus/")
def it_campus():
    return render_template("itcampus.html")

@app.route("/solmaru/")
def solmaru():
    return render_template("solmaru.html")

@app.route("/test/")
def test():
    return render_template("test.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)

