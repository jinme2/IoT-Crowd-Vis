from flask import Flask, request, jsonify 
#request: 클라이언트가 보낸 데이터 읽을 때 사용
#jsonify: python Dict -> JSON으로 변환해서 응답할 때 사용
import time 
#tiem: 현재 시간 기록용

app = Flask(__name__)

data_store= [] # 임시 저장(SQLite 교체 전까지)

#'/': 기본 주소, 단순히 서버 상태를 확인하는 테스트용 
@app.route('/')
def home():
    return "hello Flask! 서버가 잘 작동합니다 🚀"

#POST 요청이 들어오면 실행되는 함수
@app.route('/upload', methods=['POST']) 
def upload():
    try:
        content = request.json #클라이언트가 보낸 JSO데이터 python dict로 불러옴

        #유효성 검사와 기본 값 설정
        room = content.get('room', 'unknown') #측정 장소
        count = int(content.get('count',0)) #감지된 인원수
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S') #저장 시각

        #감지된 데이터를 메모리 리스트에 저장. 나중에 DB에 INSERT
        data_store.append({'room' : room, 'count':count, 'time':timestamp})
        #디버깅용
        print(f"[업로드 성공] {room}: {count}명 ({timestamp})")

        #클라이언트에게 JSON응답을 돌려줌
        return jsonify({'status': 'ok', 'massage': f'{room} 인원 {count}명 저장됨'})
    except Exception as e:
        return jsonify({'status': 'error', 'massage': str(e)}), 400

#GET 요청이 오명 최근 데이터를 반환
@app.route('/api/data', methods=['GET'])
def api_data():
    return jsonify(data_store[-20:]) # 최근 20개만 반환
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)