document.addEventListener("DOMContentLoaded", () => {
  const pieCanvas = document.getElementById("PieChart");
  const pieCtx = pieCanvas ? pieCanvas.getContext("2d") : null;
  const chartBox = pieCanvas ? pieCanvas.closest(".box") : null;
  const lineCanvas = document.getElementById("LineChart");
  const lineCtx = lineCanvas ? lineCanvas.getContext("2d") : null;
  const predict = document.getElementById("predict");
  const mostCrowd = document.getElementById("mostCrowd");

  // 각 방의 기본 수용 인원 (API 실패 시 사용)
  const fallbackMetrics = {
    lobby: { current: 30, capacity: 30 },
    sspace: { current: 30, capacity: 46 },
    espace: { current: 74, capacity: 80 },
    tdmspace: { current: 20, capacity: 32 },
    mspace: { current: 22, capacity: 24 },
  };
  const start = 8;
  const end = 18;

  function getLatestCount(roomKey) {
    if (!Array.isArray(rawData)) return null;
    const filtered = rawData.filter(item => item.room === roomKey);
    if (!filtered.length) return null;
    return filtered.reduce((latest, cur) =>
      new Date(cur.timestamp) > new Date(latest.timestamp) ? cur : latest
    );
  }

  function renderPie(key) {
    const latest = getLatestCount(key);
    const current = latest?.people_count ?? fallbackMetrics[key]?.current ?? 0;
    const capacity = fallbackMetrics[key]?.capacity ?? Math.max(current, 30);

    if (pieCtx) {
      chartBox?.classList.remove("hidden");
      const existingPie = Chart.getChart(pieCanvas.id);
      if (existingPie) existingPie.destroy();
      renderPieChart(pieCtx, current, capacity);
    }
  }

  // 시간대 평균 API 기반 라인 그래프
  async function renderLine(key) {
    let avgRecords = [];
    try {
      if (window.CrowdApi?.getAvgData) {
        const hourlyAvg = await window.CrowdApi.getAvgData(key);
        const today = new Date();
        avgRecords = Object.entries(hourlyAvg || {})
          .map(([hourStr, count]) => {
            const hour = Number(hourStr);
            if (!Number.isFinite(hour)) return null;
            const ts = new Date(today);
            ts.setUTCHours(hour, 0, 0, 0);
            return {
              room: key,
              people_count: Math.round(count ?? 0),
              timestamp: ts.toISOString(),
            };
          })
          .filter(Boolean);
      }
    } catch (e) {
      console.error("getAvgData failed, fallback to existing data", e);
    }

    const fallbackLine = [{
      room: key,
      people_count: getLatestCount(key)?.people_count ?? 0,
      timestamp: new Date(new Date().setHours(start, 0, 0, 0)).toISOString(),
    }];

    const lineRecords = avgRecords.length ? avgRecords : fallbackLine;

    if (lineCtx && typeof renderLineChart === "function") {
      const existingLine = lineCanvas.id ? Chart.getChart(lineCanvas.id) : null;
      if (existingLine) existingLine.destroy();
      renderLineChart(lineCtx, lineRecords, {
        roomKey: key,
        capacity: fallbackMetrics[key]?.capacity ?? 30,
        fixedHourRange: { start, end },
      });
    }
  }

  async function updateNextWeekPredict(key) {
    if (!predict || !window.CrowdApi?.loadPrediction) return 0;
    try {
      const { futureTime, predicted, fallback } = await window.CrowdApi.loadPrediction(key);
      const hourPart = futureTime?.split(" ")[1]?.split(":")[0];
      const displayTime = hourPart ? `${Number(hourPart)}시` : futureTime;
      const rounded = Math.round(Number(predicted));
      const baseText = `${displayTime} 예상 인원 ${rounded}명`;

      predict.textContent = fallback
        ? `${baseText} (데이터 부족으로 보수 예측)`
        : baseText;
    } catch (e) {
      console.error("prediction fetch failed", e);
      predict.textContent = "예측값을 불러오지 못했어요";
    }
  }

  async function updateMostCrowdedTime(key) {
    if (!mostCrowd || !window.CrowdApi?.getAvgData) return;

    try {
      const hourlyAvg = await window.CrowdApi.getAvgData(key);
      const entries = Object.entries(hourlyAvg || [])
        .map(([hourStr, cnt]) => [Number(hourStr), Number(cnt)])
        .filter(([h, c]) => Number.isFinite(h) && Number.isFinite(c));

      if (!entries.length) {
        mostCrowd.textContent = "혼잡 시간 정보를 불러오지 못했어요.";
        return;
      }

      const [maxHour] = entries.reduce((max, cur) => (cur[1] > max[1] ? cur : max));
      mostCrowd.textContent = `${maxHour}시 ~ ${maxHour + 1}시가 가장 혼잡해요.`;
    } catch (e) {
      console.error("updateMostCrowdedTime failed", e);
      mostCrowd.textContent = "혼잡 시간 정보를 불러오지 못했어요.";
    }
  }

  document.addEventListener("roomSelected", async (event) => {
    const key = event.detail?.key;
    if (!key) return;

    const fetchPromise = typeof startRawDataPolling === "function"
      ? startRawDataPolling(key, 60_000)
      : loadRawData?.(key);

    await fetchPromise?.catch(() => {});

    renderPie(key);

    predict.textContent = "데이터 불러오는 중...";
    mostCrowd.textContent = "데이터 불러오는 중...";

    await renderLine(key);
    await updateNextWeekPredict(key);
    await updateMostCrowdedTime(key);
  });

  const initial = typeof startRawDataPolling === "function"
    ? null
    : loadRawData?.();
});
