const API_BASE = "https://iot11-backend.onrender.com";
const API_URL = `${API_BASE}/people`;
const API_hour = `${API_BASE}/analytics/hourly`;
const API_week = `${API_BASE}/analytics/weekday`;
const API_pred = `${API_BASE}/analytics/predict`;

// UI 키를 API room 파라미터로 매핑 (필요 시 확장)
const ROOM_PARAM_MAP = {
  lobby: "lobby",
  sspace: "sspace",
  espace: "espace",
  tdmspace: "tdmspace",
  mspace: "mspace",
};
 
function getRoomParam(roomKey) {
  return ROOM_PARAM_MAP[roomKey] || roomKey || "";
}

// const today = new Date().toISOString().split("T")[0];

// fetch(`/people/date?date=${today}`)
//   .then(res => res.json())
//   .then(console.log)
//   .catch(console.error);

let rawData = [
  { camera_id: 1, id: 65, people_count: 15, room: "mspace", timestamp: "Tue, 18 Nov 2025 09:31:28 GMT" },
  { camera_id: 1, id: 65, people_count: 14, room: "tdmspace", timestamp: "Tue, 18 Nov 2025 09:31:28 GMT" },
  { camera_id: 1, id: 65, people_count: 13, room: "espace", timestamp: "Tue, 18 Nov 2025 09:31:28 GMT" },
  { camera_id: 1, id: 65, people_count: 12, room: "sspace", timestamp: "Tue, 18 Nov 2025 09:31:28 GMT" },
  { camera_id: 1, id: 65, people_count: 30, room: "lobby", timestamp: "Tue, 18 Nov 2025 09:31:28 GMT" },
]

//꺾은선 그래프에 사용할 데이터
let dayData = [
  { camera_id: 1, id: 65, people_count: 17, room: "lobby", timestamp: "Wed, 27 Nov 2025 08:31:28 GMT" },
  { camera_id: 1, id: 65, people_count: 25, room: "lobby", timestamp: "Wed, 27 Nov 2025 11:31:28 GMT" },
  { camera_id: 1, id: 65, people_count: 20, room: "lobby", timestamp: "Wed, 27 Nov 2025 13:31:28 GMT" },
  { camera_id: 1, id: 65, people_count: 15, room: "lobby", timestamp: "Wed, 27 Nov 2025 14:31:28 GMT" },
  { camera_id: 1, id: 65, people_count: 11, room: "lobby", timestamp: "Wed, 27 Nov 2025 15:31:28 GMT" },
  { camera_id: 1, id: 65, people_count: 11, room: "lobby", timestamp: "Wed, 27 Nov 2025 17:31:28 GMT" },
  { camera_id: 1, id: 65, people_count: 11, room: "lobby", timestamp: "Wed, 27 Nov 2025 18:31:28 GMT" },
]
let pollingTimer = null;
let isFetching = false;
let latestFetchPromise = null;

//실시간 파이 그래프에 사용할 데이터 갱신
async function loadRawData(roomKey, limit = 5) {
  if (isFetching && latestFetchPromise) return latestFetchPromise;

  isFetching = true;
  latestFetchPromise = (async () => {
  try {
    const params = new URLSearchParams();
    if (Number.isFinite(limit)) params.set("limit", limit);
    const roomParam = getRoomParam(roomKey);
    if (roomParam) params.set("room", roomParam);

    const res = await fetch(`${API_URL}?${params.toString()}`);
    if (!res.ok) throw new Error("bad response");
    const data = await res.json();
    rawData = Array.isArray(data) ? data : Array.isArray(data?.data) ? data.data : [];
      console.table(rawData);
  } catch (e) {
    console.error("fetch failed, keep old rawData or fallback", e);
      } finally {
        isFetching = false;
  }
  return rawData;
    })();

  return latestFetchPromise;
}

// //시간별 인원(라인 그래프)에 사용할 데이터 갱신
// async function loadDayData(dateStr) {
//   const targetDate = dateStr || new Date().toISOString().slice(0, 10);
//   const url = `https://iot11-backend.onrender.com/people/date?date=${targetDate}`;
//   try {
//     const res = await fetch(url);
//     if (!res.ok) throw new Error(`Bad response ${res.status}`);
//     const data = await res.json();
//     const list = Array.isArray(data) ? data : Array.isArray(data?.data) ? data.data : [];
//     dayData = list;          // 범위 필터 없이 그대로 저장
//     return dayData;
//   } catch (e) {
//     console.error("loadDayData failed, keep existing dayData", e);
//     return dayData;
//   }
// }

// 시간대별 평균 인원 조회 (라인 그래프용)
async function getAvgData(roomKey) {
  const roomParam = getRoomParam(roomKey);
  const url = roomParam ? `${API_hour}?room=${roomParam}` : API_hour;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`hourly bad response ${res.status}`);
  const data = await res.json();
  return data?.hourly_avg || {};
}

//다음 주 인원 예측용 함수
async function loadPrediction(roomKey) {
  const roomParam = getRoomParam(roomKey);
  const url = roomParam ? `${API_pred}?room=${roomParam}` : API_pred;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`predict bad response ${res.status}`);
  const data = await res.json(); // { fallback, future_time, predict_next_week, status }
  if (data?.status !== "ok") throw new Error("predict status not ok");

  const count = Math.round(Number(data.predict_next_week));
  if (!Number.isFinite(count)) throw new Error("predict count missing");

  return {
    futureTime: data.future_time,      // "2025-12-03 16:47:34"
    predicted: count,
    fallback: Boolean(data.fallback),  // 데이터 적으면 true일 수 있음
  };
}

function startRawDataPolling(roomKey, intervalMs = 60000) {
  const safeInterval = Number.isFinite(intervalMs) && intervalMs >= 1000 ? intervalMs : 60000;
  if (pollingTimer) clearInterval(pollingTimer);
  const first = loadRawData(roomKey);
  pollingTimer = setInterval(() => {
    loadRawData(roomKey).catch(() => {});
  }, safeInterval);
  return first;
}

function stopRawDataPolling() {
  if (!pollingTimer) return;
  clearInterval(pollingTimer);
  pollingTimer = null;
}

//데이터에 필요한 정보 뽑아오는 함수
function convertRoomData(rawData) {
  const periods = []
  const counts = []
  for (const item of rawData) {
    const date = new Date(item.timestamp);
    const hours = date.getHours()
    const period =
    hours === 0
      ? '12AM'
      : hours < 12
      ? `${hours}AM`
      : hours === 12
      ? '12PM'
      : `${hours - 12}PM`

    periods.push(period)
    counts.push(item.people_count)
  }
  return { periods, people_count: counts }
}


window.CrowdApi = {
  loadRawData,
  startRawDataPolling,
  stopRawDataPolling,
  //loadDayData,
  loadPrediction,
  getAvgData
};
