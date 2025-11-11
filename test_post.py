import requests
#requests: 파이썬에서 HTTP 요청(POST, GET 등)을 쉽게 보낼 수 있게 해주는 라이브러리

url = "http://127.0.0.1:5000/upload" #데이터를 보낼 Flask 주소
data = {"room": "강의실", "count": 6} #보낼 JSON 데이터

#requests.post()는 Flask 서버의 /upload경로로 데이터를 보내는 함수
response = requests.post(url, json=data) #자동으로 JSON형식으로 변환 후 전송

#print("응답 상태:", response.status_code)
#print("응답 본문:", response.text)
print(response.json()) #서버가 돌려준 JSON응답을 python dict로 바꿔서 콘솔에 출력