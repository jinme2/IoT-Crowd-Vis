function buildHourlySeries(records, fixedLabels) {
  if (!Array.isArray(records)) {
    const labels = fixedLabels ?? [];
    return { labels, data: labels.map(() => null) };
  }

  const hourlyMap = new Map();

  for (const item of records) {
    if (!item?.timestamp) continue;
    const date = new Date(item.timestamp);
    if (Number.isNaN(date.getTime())) continue;

    const hour = date.getUTCHours();
    const hourLabel = `${hour.toString().padStart(2, "0")}:00`;
    const keyTime = date.getTime();
    const existing = hourlyMap.get(hourLabel);

    // 같은 시간대에 여러 값 존재 -> 최신 값 사용
    if (!existing || existing.time < keyTime) {
      hourlyMap.set(hourLabel, { time: keyTime, count: Number(item.people_count) || 0 });
    }
  }

  const sorted = [...hourlyMap.entries()].sort((a, b) => a[1].time - b[1].time);
  const labels = sorted.map(([label]) => label);
  const data = sorted.map(([, value]) => value.count);

  // 시간축 고정이 있으면 그 순서에 맞춰 데이터 배열 생성
  if (Array.isArray(fixedLabels) && fixedLabels.length) {
    let lastSeen = null;
    const currentHour = new Date().getHours();

    return {
      labels: fixedLabels,
      data: fixedLabels.map(label => {
        const labelHour = Number(label.split(":")[0]);

        // 미래 시각(현재 시각 이후)은 채우지 않음
        if (!Number.isFinite(labelHour) || labelHour > currentHour) {
          return null;
        }

        const entry = hourlyMap.get(label);
        if (entry) {
          lastSeen = entry.count;
          return entry.count;
        }
        return lastSeen; // reuse previous hour; stays null if none yet
      }),
    };
  }

  return { labels, data };
}

function buildFixedHourLabels(startHour = 8, endHour = 18) {
  const labels = [];
  for (let h = startHour; h <= endHour; h++) {
    labels.push(`${h.toString().padStart(2, "0")}:00`);
  }
  return labels;
}

// 시간대별 인원수를 선 그래프로 생성
function renderLineChart(ctx, records, options = {}) {
  if (!ctx || typeof Chart === "undefined") return;

  const { roomKey, capacity, fixedHourRange } = options;
  const filtered = roomKey
    ? (Array.isArray(records) ? records.filter(item => item?.room === roomKey) : [])
    : records;

  const fixedLabels = fixedHourRange
    ? buildFixedHourLabels(fixedHourRange.start ?? 8, fixedHourRange.end ?? 18)
    : undefined;

  const { labels, data } = buildHourlySeries(filtered, fixedLabels);
  const chartLabels = labels.length ? labels : ["--"];
  const chartData = labels.length ? data : [0];

  const numericData = chartData.filter(v => typeof v === "number" && !Number.isNaN(v));
  const maxData = numericData.length ? Math.max(...numericData) : 0;
  const capMax = typeof capacity === "number" ? capacity : undefined;
  const yMax = capMax !== undefined ? Math.max(capMax, maxData) : maxData;

  const existing = ctx.canvas?.id ? Chart.getChart(ctx.canvas.id) : null;
  if (existing) existing.destroy();

  const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height || 160);
  gradient.addColorStop(0, "rgba(37,99,235,0.30)");
  gradient.addColorStop(1, "rgba(37,99,235,0.05)");

  new Chart(ctx, {
    type: "line",
    data: {
      labels: chartLabels,
      datasets: [{
        label: "People by hour",
        data: chartData,
        borderColor: "#2563eb",
        backgroundColor: gradient,
        fill: true,
        tension: 0.35,
        pointRadius: 3,
        pointBackgroundColor: "#1d4ed8",
        spanGaps: false,
      }]
    },
    options: {
      scales: {
        x: {
          title: { display: true, text: "Time" },
          ticks: { maxRotation: 0, autoSkipPadding: 12 },
          grid: { display: false }
        },
        y: {
          beginAtZero: true,
          title: { display: true, text: "People" },
          max: Number.isFinite(yMax) ? yMax : undefined
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.parsed.y ?? 0} people`
          }
        }
      }
    }
  });
}

window.CrowdApi = window.CrowdApi || {};
window.CrowdApi.renderLineChart = renderLineChart;
