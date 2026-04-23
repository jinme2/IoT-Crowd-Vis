let pieValueLabelPluginRegistered = false;

//그래프 위에 현재인원/정원 을 보여주기 위한 커스텀 옵션
function ensurePieValueLabelPlugin() {
  if (pieValueLabelPluginRegistered || typeof Chart === "undefined" || typeof Chart.register !== "function") {
    return;
  }

  const plugin = {
    id: "pieValueLabel",
    afterDatasetsDraw(chart, _, pluginOptions) {
      if (!pluginOptions || !pluginOptions.text) return;
      const { ctx, chartArea } = chart;
      if (!chartArea) return;

      const x = (chartArea.left + chartArea.right) / 2;
      const y = pluginOptions.y ?? Math.max(chartArea.top - 16, 12);

      ctx.save();
      ctx.font = pluginOptions.font || "600 12px 'Segoe UI'";
      ctx.fillStyle = pluginOptions.color || "#111";
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      ctx.fillText(pluginOptions.text, x, y);
      ctx.restore();
    }
  };

  Chart.register(plugin);
  pieValueLabelPluginRegistered = true;
}

function renderPieChart(ctx, current, capacity) {
  ensurePieValueLabelPlugin();

  const filled = current;
  const empty = capacity - current;
  const ratio = capacity > 0 ? filled / capacity : 0;
  let currentColor = "hsla(0, 84%, 60%, 1.00)"; // 기본 빨강
  let borderColor = "hsla(0, 84%, 30%, 1.00)"
  if (ratio < 0.5) {
    currentColor = "hsla(142, 71%, 45%, 1.00)"; // 초록
    borderColor = "hsla(142, 71%, 15%, 1.00)"
  } else if (ratio < 0.7) {
    currentColor = "hsla(48, 96%, 53%, 1.00)"; // 노랑
    borderColor = "hsla(40, 97%, 44%, 1.00)"
  }
  const tooltipTexts = [
    `이용 중: ${filled}명`,
    `잔여: ${empty}명`
  ];

  new Chart(ctx, {
    type: 'pie',
    data: {
      labels: ["현재", "남은 인원"],
      datasets: [{
        data: [filled, empty],
        backgroundColor: [
          currentColor,
          "#e5e7eb"      // 연한 회색 (남은 자리)
        ],
        borderColor: [
          borderColor,
          "#c9cbcfff" 
        ],
        borderWidth: 1,
      }]
    },
    options: {
      layout: {
        padding: { top: 20 }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: true,
          callbacks: {
            title: () => "",
            label: (context) => tooltipTexts[context.dataIndex] || ""
          }
        },
        pieValueLabel: {
          text: `현재:${current} / 정원:${capacity}`,
          color: "#0f172a",
          font: "600 12px 'Segoe UI'",
          y: 12
        }
      }
    }
  });
}

window.CrowdApi = window.CrowdApi || {};
window.CrowdApi.renderPieChart = renderPieChart;
