/* GLI COMPASS — daily global liquidity proxy dashboard. */
(() => {
  "use strict";
  const D = window.GLI_DATA;
  if (!D) return;
  const $ = (id) => document.getElementById(id);
  const num = (v, d = 1) => (v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(d));
  const signed = (v, d = 1) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${Number(v).toFixed(d)}`);
  const COLORS = { s: "#e3b46a", m: "#55c7b2", blue: "#6aa7ef", neg: "#e06767", pos: "#54b78b" };
  const RANGE_YEARS = { "1y": 1, "2y": 2, "3y": 3, "5y": 5, "8y": 8, "10y": 10 };
  let chart = null;
  let quad = null;
  let ndxChart = null;
  let ndxCorrChart = null;
  let cashChart = null;
  let cashMode = new URLSearchParams(window.location.search).get("cash") === "estimated" ? "estimated" : "official";
  let cashRange = "all";
  const CASH_YEARS = { "1y": 1, "3y": 3, "5y": 5, "10y": 10, "20y": 20 };
  let yieldChart = null, peChart = null;
  let yieldRange = "all", peRange = "all";
  const yieldVisible = { y1: true, y5: true, y10: true, y20: true, y30: true, median: true };
  const peVisible = { pe: true, cape: true };
  const YIELD_COLORS = { y1: "#6aa7ef", y5: "#55c7b2", y10: "#e3b46a", y20: "#e06767", y30: "#a897e8", median: "#dbe2ec" };

  $("asOf").textContent = D.meta.as_of.replaceAll("-", ".");
  $("gliS").textContent = num(D.current.gli_s, 1);
  $("gliM").textContent = num(D.current.gli_m, 1);
  $("regime").textContent = D.current.regime;
  $("regime").className = `regime ${D.current.regime_en}`;
  $("oneM").textContent = signed(D.current.one_m, 1);
  $("threeM").textContent = signed(D.current.three_m, 1);

  const sVals = D.series.map((r) => r.s);
  const pctS = Math.round(sVals.filter((v) => v <= D.current.gli_s).length / sVals.length * 100);
  $("pctS").textContent = `${pctS}%`;

  function quadrantName(s, m) {
    if (s >= 50 && m >= 50) return "全面宽松";
    if (s >= 50) return "高位收缩";
    if (m >= 50) return "流动性复苏";
    return "低位收缩";
  }
  const qName = quadrantName(D.current.gli_s, D.current.gli_m);
  $("heroQuad").textContent = `${qName} · GLI-S ${num(D.current.gli_s, 1)} / GLI-M ${num(D.current.gli_m, 1)}；存量在 50 下方，边际也偏弱。`;
  $("quadTitle").textContent = qName;
  $("quadS").textContent = num(D.current.gli_s, 1);
  $("quadM").textContent = num(D.current.gli_m, 1);
  $("quad1M").textContent = signed(D.current.one_m, 1);
  $("quad3M").textContent = signed(D.current.three_m, 1);
  $("quadBody").textContent = `GLI-S 处于历史 ${pctS}% 分位，GLI-M 低于 50，说明流动性存量偏弱且边际没有改善。四象限只描述状态，不构成择时信号。`;

  /* ---------------- chart ---------------- */
  const zones = [
    [0, 30, "rgba(224,103,103,.10)"],
    [30, 45, "rgba(221,145,89,.075)"],
    [45, 55, "rgba(255,255,255,.018)"],
    [55, 70, "rgba(84,183,139,.07)"],
    [70, 100, "rgba(85,199,178,.085)"],
  ];
  const zonePlugin = {
    id: "gliZones",
    beforeDatasetsDraw(chart) {
      const y = chart.scales.y, area = chart.chartArea;
      if (!area) return;
      zones.forEach(([a, b, color]) => {
        const top = y.getPixelForValue(b), bottom = y.getPixelForValue(a);
        chart.ctx.fillStyle = color;
        chart.ctx.fillRect(area.left, top, area.right - area.left, bottom - top);
      });
    },
    afterDatasetsDraw(chart) {
      const y = chart.scales.y.getPixelForValue(50), area = chart.chartArea;
      if (!Number.isFinite(y)) return;
      chart.ctx.save();
      chart.ctx.setLineDash([5, 5]);
      chart.ctx.strokeStyle = "rgba(255,255,255,.28)";
      chart.ctx.lineWidth = 1;
      chart.ctx.beginPath(); chart.ctx.moveTo(area.left, y); chart.ctx.lineTo(area.right, y); chart.ctx.stroke();
      chart.ctx.restore();
    },
  };
  const quadPlugin = {
    id: "quadZones",
    beforeDatasetsDraw(chart) {
      const x = chart.scales.x, y = chart.scales.y, a = chart.chartArea;
      if (!a) return;
      const mx = x.getPixelForValue(50), my = y.getPixelForValue(50);
      chart.ctx.fillStyle = "rgba(224,103,103,.055)"; chart.ctx.fillRect(a.left, a.top, mx - a.left, my - a.top);
      chart.ctx.fillStyle = "rgba(84,183,139,.06)"; chart.ctx.fillRect(mx, a.top, a.right - mx, my - a.top);
      chart.ctx.fillStyle = "rgba(224,103,103,.075)"; chart.ctx.fillRect(a.left, my, mx - a.left, a.bottom - my);
      chart.ctx.fillStyle = "rgba(106,167,239,.055)"; chart.ctx.fillRect(mx, my, a.right - mx, a.bottom - my);
      chart.ctx.save();
      chart.ctx.setLineDash([5, 5]);
      chart.ctx.strokeStyle = "rgba(255,255,255,.2)";
      chart.ctx.beginPath(); chart.ctx.moveTo(mx, a.top); chart.ctx.lineTo(mx, a.bottom); chart.ctx.stroke();
      chart.ctx.beginPath(); chart.ctx.moveTo(a.left, my); chart.ctx.lineTo(a.right, my); chart.ctx.stroke();
      chart.ctx.restore();
    },
  };
  Chart.register(zonePlugin, quadPlugin);

  function rangeStart(range) {
    if (range === "all") return D.series[0].d;
    const end = new Date(D.series[D.series.length - 1].d).getTime();
    const years = RANGE_YEARS[range] || 5;
    const cutoff = end - years * 365.25 * 86400000;
    return (D.series.find((r) => new Date(r.d).getTime() >= cutoff) || D.series[0]).d;
  }
  function rowsFor(range) {
    const start = rangeStart(range);
    return D.series.filter((r) => r.d >= start);
  }

  function drawChart(range) {
    const rows = rowsFor(range);
    const data = {
      labels: rows.map((r) => r.d),
      datasets: [
        { label: "GLI-S", data: rows.map((r) => r.s), borderColor: COLORS.s, backgroundColor: "transparent", borderWidth: 2, tension: .16, pointRadius: 0, pointHitRadius: 8 },
        { label: "GLI-M", data: rows.map((r) => r.m), borderColor: COLORS.m, backgroundColor: "transparent", borderWidth: 1.6, borderDash: [5, 4], tension: .16, pointRadius: 0, pointHitRadius: 8 },
      ],
    };
    const options = {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: "index", intersect: false },
      layout: { padding: { top: 10, right: 5, left: 0, bottom: 0 } },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(8,13,19,.97)", borderColor: "rgba(255,255,255,.12)", borderWidth: 1,
          padding: 10, displayColors: true, boxWidth: 8, boxHeight: 8,
          titleColor: "#e9eef5", bodyColor: "#a7b5c5",
          titleFont: { family: "Inter, sans-serif", size: 10, weight: "600" },
          bodyFont: { family: "Bahnschrift, sans-serif", size: 10 },
          callbacks: { label: (ctx) => `  ${ctx.dataset.label}  ${num(ctx.raw, 1)}` },
        },
      },
      scales: {
        x: { type: "category", grid: { display: false }, border: { display: false }, ticks: { color: "#687789", maxTicksLimit: 8, maxRotation: 0, autoSkip: true, font: { family: "Bahnschrift, sans-serif", size: 9 } } },
        y: { min: 0, max: 100, position: "right", grid: { color: "rgba(255,255,255,.05)", drawTicks: false }, border: { display: false }, ticks: { color: "#687789", padding: 8, stepSize: 20, font: { family: "Bahnschrift, sans-serif", size: 9 } } },
      },
    };
    if (!chart) chart = new Chart($("gliChart"), { type: "line", data, options });
    else { chart.data = data; chart.update("none"); }
    $("chartFoot").textContent = `${rows[0].d} → ${rows[rows.length - 1].d} · ${rows.length} 个交易日`;
  }

  /* ---------------- US Treasury yields ---------------- */
  function sliceYears(rows, range, map) {
    if (range === "all") return rows;
    const last = new Date(rows[rows.length - 1].d).getTime();
    return rows.filter((r) => new Date(r.d).getTime() >= last - (map[range] || 10) * 365.25 * 86400000);
  }
  function drawYieldChart(range = yieldRange) {
    const Y = window.YIELDS;
    if (!Y) return;
    yieldRange = range;
    const rows = sliceYears(Y.series, range, { "5y": 5, "10y": 10, "20y": 20 });
    const specs = [["y1", "1Y"], ["y5", "5Y"], ["y10", "10Y"], ["y20", "20Y"], ["y30", "30Y"], ["median", "中线"]];
    const datasets = specs.filter(([k]) => yieldVisible[k]).map(([k, label]) => ({
      label, data: rows.map((r) => r[k]),
      borderColor: YIELD_COLORS[k], backgroundColor: "transparent",
      borderWidth: k === "median" ? 1.4 : 1.7, borderDash: k === "median" ? [5, 4] : [],
      tension: .12, pointRadius: 0, pointHitRadius: 6,
    }));
    if (!yieldChart) {
      yieldChart = new Chart($("yieldChart"), {
        type: "line",
        data: { labels: rows.map((r) => r.d), datasets },
        options: {
          responsive: true, maintainAspectRatio: false, animation: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { display: false },
            tooltip: { backgroundColor: "rgba(8,13,19,.97)", borderColor: "rgba(255,255,255,.12)", borderWidth: 1, padding: 9, titleColor: "#e9eef5", bodyColor: "#a7b5c5", callbacks: { label: (ctx) => `  ${ctx.dataset.label}  ${num(ctx.raw, 2)}%` } },
          },
          scales: {
            x: { type: "category", grid: { display: false }, border: { display: false }, ticks: { color: "#687789", maxTicksLimit: 9, maxRotation: 0, autoSkip: true, font: { family: "Bahnschrift, sans-serif", size: 8 } } },
            y: { position: "right", grid: { color: "rgba(255,255,255,.05)", drawTicks: false }, border: { display: false }, ticks: { color: "#687789", callback: (v) => `${v}%`, font: { family: "Bahnschrift, sans-serif", size: 8 } } },
          },
        },
      });
    } else {
      yieldChart.data.labels = rows.map((r) => r.d);
      yieldChart.data.datasets = datasets;
      yieldChart.update("none");
    }
    const s = Y.meta.stats;
    $("y10Now").textContent = `${num(s.y10.current, 2)}%`;
    $("yMedNow").textContent = `${num(rows[rows.length - 1].median, 2)}%`;
    $("y10Pct").textContent = `${num(s.y10.percentile, 1)}%`;
    $("yieldFoot").textContent = `${rows[0].d} → ${rows[rows.length - 1].d} · ${rows.length} 个交易日`;
    $("yieldStats").innerHTML = ["y1", "y5", "y10", "y20", "y30"].map((k) => {
      const a = s[k];
      return `<tr><td>${a.label}</td><td>${num(a.current, 2)}%</td><td>${num(a.median, 2)}%</td><td>${num(a.p20, 2)}%</td><td>${num(a.p80, 2)}%</td><td>${num(a.percentile, 1)}%</td></tr>`;
    }).join("");
  }

  /* ---------------- S&P 500 PE ---------------- */
  function drawPeChart(range = peRange) {
    const P = window.PE_DATA;
    if (!P) return;
    peRange = range;
    const rows = sliceYears(P.series, range, { "10y": 10, "20y": 20 });
    const s = P.meta.stats;
    const medPlugin = {
      id: "peMedians",
      afterDatasetsDraw(chart) {
        const y = chart.scales.y, a = chart.chartArea;
        if (!a) return;
        chart.ctx.save();
        [["pe", s.pe.median, "#55c7b2"], ["cape", s.cape.median, "#e3b46a"]].forEach(([k, v, c]) => {
          if (!peVisible[k]) return;
          const py = y.getPixelForValue(v);
          chart.ctx.setLineDash([4, 4]); chart.ctx.strokeStyle = c; chart.ctx.globalAlpha = .45;
          chart.ctx.beginPath(); chart.ctx.moveTo(a.left, py); chart.ctx.lineTo(a.right, py); chart.ctx.stroke();
          chart.ctx.globalAlpha = 1; chart.ctx.setLineDash([]);
          chart.ctx.fillStyle = c; chart.ctx.font = "7px Bahnschrift, sans-serif";
          chart.ctx.fillText(`中位 ${num(v, 1)}`, a.right - 48, py - 3);
        });
        chart.ctx.restore();
      },
    };
    const datasets = [
      { key: "pe", label: "滚动 PE", color: "#55c7b2" },
      { key: "cape", label: "席勒 PE", color: "#e3b46a" },
    ].filter((d) => peVisible[d.key]).map((d) => ({
      label: d.label, data: rows.map((r) => r[d.key]), borderColor: d.color, backgroundColor: "transparent", borderWidth: 1.8, tension: .12, pointRadius: 0, pointHitRadius: 7,
    }));
    if (!peChart) {
      peChart = new Chart($("peChart"), {
        type: "line", data: { labels: rows.map((r) => r.d), datasets },
        options: {
          responsive: true, maintainAspectRatio: false, animation: false,
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { display: false }, tooltip: { backgroundColor: "rgba(8,13,19,.97)", borderColor: "rgba(255,255,255,.12)", borderWidth: 1, padding: 9, titleColor: "#e9eef5", bodyColor: "#a7b5c5", callbacks: { label: (ctx) => `  ${ctx.dataset.label}  ${num(ctx.raw, 1)}` } } },
          scales: {
            x: { type: "category", grid: { display: false }, border: { display: false }, ticks: { color: "#687789", maxTicksLimit: 8, maxRotation: 0, autoSkip: true, font: { family: "Bahnschrift, sans-serif", size: 8 } } },
            y: { position: "right", grid: { color: "rgba(255,255,255,.05)", drawTicks: false }, border: { display: false }, ticks: { color: "#687789", font: { family: "Bahnschrift, sans-serif", size: 8 } } },
          },
        },
        plugins: [medPlugin],
      });
    } else {
      peChart.data.labels = rows.map((r) => r.d);
      peChart.data.datasets = datasets;
      peChart.update("none");
    }
    $("peNow").textContent = num(s.pe.current, 1);
    $("capeNow").textContent = num(s.cape.current, 1);
    $("capePct").textContent = `${num(s.cape.percentile, 1)}%`;
    $("peFoot").textContent = `${rows[0].d} → ${rows[rows.length - 1].d} · ${rows.length} 个月`;
    $("peStats").innerHTML = [["pe", "滚动 PE"], ["cape", "席勒 PE"]].map(([k, label]) => {
      const a = s[k];
      return `<tr><td>${label}</td><td>${num(a.current, 1)}</td><td>${num(a.median, 1)}</td><td>${num(a.p20, 1)}</td><td>${num(a.p80, 1)}</td><td>${num(a.percentile, 1)}%</td></tr>`;
    }).join("");
  }

  /* ---------------- cash / equities ---------------- */
  function drawCashChart(mode = cashMode, range = cashRange) {
    const C = window.CASH_EQUITY;
    if (!C || !C.series || !C.series.length) return;
    cashMode = mode; cashRange = range;
    const est = mode === "estimated";
    const source = est ? (C.weekly || []) : C.series;
    const last = source.length ? new Date(source[source.length - 1].d).getTime() : Date.now();
    const years = CASH_YEARS[range] || 0;
    const rows = range === "all" ? source : source.filter((r) => new Date(r.d).getTime() >= last - years * 365.25 * 86400000);
    if (!rows.length) return;

    const labels = rows.map((r) => r.d);
    const avgKey = est ? "avg13" : "avg4";
    const avgLabel = est ? "13 周均值" : "4 季度均值";
    const ratios = rows.map((r) => r.ratio).filter((v) => v != null);
    const spyVals = rows.map((r) => r.spy).filter((v) => v != null);
    const yMin = Math.max(0, Math.min(...ratios) * .88);
    const yMax = Math.max(...ratios) * 1.08;
    const spyMax = spyVals.length ? Math.max(...spyVals) * 1.1 : 900;

    $("cashModeBadge").textContent = est ? "ESTIMATED 周频" : "官方季度";
    $("cashModeBadge").className = `mode-badge ${est ? "estimated" : "official"}`;
    $("cashLatest").textContent = num(est ? C.estimated.latest_ratio : C.meta.latest_ratio, 3);
    $("cashAvg").textContent = num(est ? C.estimated.latest_avg13 : C.meta.latest_avg4, 3);
    $("cashAvgLabel").textContent = avgLabel;
    $("cashLegendRatio").textContent = est ? "估算现金 / 股票市值" : "现金 / 股票市值";
    $("cashLegendAvg").textContent = avgLabel;
    $("cashFoot").textContent = `${rows[0].d} → ${rows[rows.length - 1].d} · ${rows.length} ${est ? "周" : "季度"} · ${est ? "ESTIMATED" : "官方 Z.1/H.8"}`;
    $("cashFootNote").textContent = est
      ? "估算周频 · MMF 季度插值 + H.8 存款 + 市值按周收益外推 · 不是官方周度序列"
      : "季度 · 现金 = MMF + 银行存款 · 官方 Z.1/H.8";

    const marks = [
      { d: "1982-09-30", text: "1982 牛市起点" },
      { d: "2000-03-31", text: "2000 科网低点" },
      { d: "2009-03-31", text: "2009 危机峰值" },
    ];
    const markPlugin = {
      id: "cashMarks",
      afterDatasetsDraw(chart) {
        const x = chart.scales.x, a = chart.chartArea;
        const chartLabels = chart.data.labels || [];
        if (!a) return;
        chart.ctx.save();
        marks.forEach((m) => {
          let i = chartLabels.indexOf(m.d);
          if (i < 0) i = chartLabels.findIndex((d) => d >= m.d);
          if (i < 0) return;
          const px = x.getPixelForValue(i);
          chart.ctx.setLineDash([3, 4]);
          chart.ctx.strokeStyle = "rgba(255,255,255,.22)";
          chart.ctx.lineWidth = 1;
          chart.ctx.beginPath(); chart.ctx.moveTo(px, a.top); chart.ctx.lineTo(px, a.bottom); chart.ctx.stroke();
          chart.ctx.setLineDash([]);
          chart.ctx.fillStyle = "rgba(154,169,187,.68)";
          chart.ctx.font = "7px Bahnschrift, sans-serif";
          chart.ctx.fillText(m.text, Math.min(px + 4, a.right - 64), a.top + 10);
        });
        chart.ctx.restore();
      },
    };

    if (cashChart) cashChart.destroy();
    cashChart = new Chart($("cashChart"), {
      type: "line",
      data: {
        labels,
        datasets: [
          { label: est ? "估算现金 / 股票" : "现金 / 股票", data: rows.map((r) => r.ratio), borderColor: "#4fae8a", backgroundColor: "transparent", borderWidth: 1.9, tension: .15, pointRadius: 0, pointHitRadius: 6, yAxisID: "y" },
          { label: avgLabel, data: rows.map((r) => r[avgKey]), borderColor: "#8796a8", backgroundColor: "transparent", borderWidth: 1.3, borderDash: [4, 3], tension: .15, pointRadius: 0, pointHitRadius: 6, yAxisID: "y" },
          { label: "SPY", data: rows.map((r) => r.spy), borderColor: "#7b8899", backgroundColor: "transparent", borderWidth: 1.1, tension: .1, pointRadius: 0, pointHitRadius: 6, yAxisID: "y1", spanGaps: true },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(8,13,19,.97)", borderColor: "rgba(255,255,255,.12)", borderWidth: 1,
            padding: 10, displayColors: true, boxWidth: 7, boxHeight: 7,
            titleColor: "#e9eef5", bodyColor: "#a7b5c5",
            callbacks: {
              label: (ctx) => ctx.datasetIndex === 2 ? `  SPY  ${num(ctx.raw, 1)}` : `  ${ctx.dataset.label}  ${num(ctx.raw, 3)}`,
            },
          },
        },
        scales: {
          x: { type: "category", grid: { display: false }, border: { display: false }, ticks: { color: "#687789", maxTicksLimit: 9, maxRotation: 0, autoSkip: true, font: { family: "Bahnschrift, sans-serif", size: 8 } } },
          y: { min: yMin, max: yMax, position: "left", grid: { color: "rgba(255,255,255,.05)", drawTicks: false }, border: { display: false }, ticks: { color: "#687789", font: { family: "Bahnschrift, sans-serif", size: 8 } } },
          y1: { min: 0, max: spyMax, position: "right", grid: { display: false }, border: { display: false }, ticks: { color: "#687789", maxTicksLimit: 4, font: { family: "Bahnschrift, sans-serif", size: 8 } } },
        },
      },
      plugins: [markPlugin],
    });
  }

  /* ---------------- GLI vs Nasdaq 100 ---------------- */
  function zs(vals) {
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
    const sd = Math.sqrt(vals.reduce((a, b) => a + (b - mean) ** 2, 0) / vals.length) || 1;
    return vals.map((v) => (v - mean) / sd);
  }
  function pearson(a, b) {
    const n = Math.min(a.length, b.length);
    const x = a.slice(-n), y = b.slice(-n);
    const mx = x.reduce((s, v) => s + v, 0) / n;
    const my = y.reduce((s, v) => s + v, 0) / n;
    let num = 0, dx = 0, dy = 0;
    for (let i = 0; i < n; i++) {
      num += (x[i] - mx) * (y[i] - my);
      dx += (x[i] - mx) ** 2;
      dy += (y[i] - my) ** 2;
    }
    return dx && dy ? num / Math.sqrt(dx * dy) : null;
  }
  function monthlyCorr(rows) {
    const buckets = new Map();
    rows.forEach((r) => {
      const k = r.d.slice(0, 7);
      buckets.set(k, r);
    });
    const vals = [...buckets.values()];
    const a = [], b = [];
    for (let i = 1; i < vals.length; i++) {
      a.push(vals[i].s - vals[i - 1].s);
      b.push(vals[i].n / vals[i - 1].n - 1);
    }
    return a.length > 3 ? pearson(a, b) : null;
  }

  function drawNdxCharts(range = "all") {
    const rows = rowsFor(range).filter((r) => r.s != null && r.n != null);
    const zS = zs(rows.map((r) => r.s));
    const zN = zs(rows.map((r) => Math.log(r.n)));
    const data = {
      labels: rows.map((r) => r.d),
      datasets: [
        { label: "GLI-S", data: zS, borderColor: COLORS.s, backgroundColor: "transparent", borderWidth: 1.9, tension: .16, pointRadius: 0, pointHitRadius: 8 },
        { label: "TQQQ", data: zN, borderColor: COLORS.blue, backgroundColor: "transparent", borderWidth: 1.6, tension: .16, pointRadius: 0, pointHitRadius: 8 },
      ],
    };
    const options = {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(8,13,19,.97)", borderColor: "rgba(255,255,255,.12)", borderWidth: 1,
          padding: 9, displayColors: true, boxWidth: 7, boxHeight: 7,
          titleColor: "#e9eef5", bodyColor: "#a7b5c5",
          callbacks: {
            label: (ctx) => {
              const row = rows[ctx.dataIndex];
              const raw = ctx.datasetIndex === 0 ? `GLI-S ${num(row.s, 1)}` : `TQQQ ${num(row.n, 0)}`;
              return `  ${ctx.dataset.label}  Z ${num(ctx.raw, 2)}  ·  ${raw}`;
            },
          },
        },
      },
      scales: {
        x: { type: "category", grid: { display: false }, border: { display: false }, ticks: { color: "#687789", maxTicksLimit: 7, maxRotation: 0, autoSkip: true, font: { family: "Bahnschrift, sans-serif", size: 8 } } },
        y: { position: "right", suggestedMin: -3, suggestedMax: 3, grid: { color: "rgba(255,255,255,.05)", drawTicks: false }, border: { display: false }, ticks: { color: "#687789", maxTicksLimit: 5, font: { family: "Bahnschrift, sans-serif", size: 8 } } },
      },
    };
    if (!ndxChart) ndxChart = new Chart($("ndxChart"), { type: "line", data, options });
    else { ndxChart.data = data; ndxChart.update("none"); }

    const corrRows = rows.filter((r) => r.rc != null);
    const corrData = {
      labels: corrRows.map((r) => r.d),
      datasets: [{ label: "60日相关", data: corrRows.map((r) => r.rc), borderColor: COLORS.m, backgroundColor: "rgba(85,199,178,.08)", borderWidth: 1.4, fill: true, tension: .15, pointRadius: 0, pointHitRadius: 6 }],
    };
    const corrOptions = {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: "rgba(8,13,19,.97)", borderColor: "rgba(255,255,255,.12)", borderWidth: 1, padding: 8, displayColors: false, titleColor: "#e9eef5", bodyColor: "#a7b5c5", callbacks: { label: (ctx) => `  60日相关  ${num(ctx.raw, 2)}` } },
      },
      scales: {
        x: { type: "category", grid: { display: false }, border: { display: false }, ticks: { display: false } },
        y: { min: -1, max: 1, position: "right", grid: { color: "rgba(255,255,255,.04)", drawTicks: false }, border: { display: false }, ticks: { color: "#687789", stepSize: .5, font: { family: "Bahnschrift, sans-serif", size: 8 } } },
      },
    };
    if (!ndxCorrChart) ndxCorrChart = new Chart($("ndxCorrChart"), { type: "line", data: corrData, options: corrOptions });
    else { ndxCorrChart.data = corrData; ndxCorrChart.update("none"); }

    const dayA = [], dayB = [];
    for (let i = 1; i < rows.length; i++) { dayA.push(rows[i].s - rows[i - 1].s); dayB.push(Math.log(rows[i].n / rows[i - 1].n)); }
    const daily = pearson(dayA, dayB);
    const monthly = monthlyCorr(rows);
    const corr60 = corrRows.length ? corrRows[corrRows.length - 1].rc : null;
    $("ndxDaily").textContent = num(daily, 2);
    $("ndxMonthly").textContent = num(monthly, 2);
    $("ndx60").textContent = num(corr60, 2);
    $("ndxFoot").textContent = `${rows[0].d} → ${rows[rows.length - 1].d} · Z-Score 标准化 · 日相关 ${num(daily, 2)} · 月相关 ${num(monthly, 2)}`;
  }

  /* ---------------- modules ---------------- */
  function renderModules() {
    $("moduleRows").innerHTML = D.current.modules.map((m) => {
      const w = (m.weight * 100).toFixed(0) + "%";
      const cls = m.points >= 0 ? "pos" : "neg";
      const width = Math.min(100, Math.abs(m.points) / 3 * 100);
      return `<div class="module-row">
        <div class="module-name">${m.name}<small>${m.key === "policy" ? "利率 / TLT" : m.key === "usd" ? "DXY / UUP" : m.key === "credit" ? "HYG/LQD · KRE/SPY" : m.key === "cross" ? "EEM/SPY · DXY" : "VIX / MOVE / HYG"}</small><span class="module-bar ${cls}"><i style="width:${width}%"></i></span></div>
        <div class="module-weight">${w}</div>
        <div class="module-z">${signed(m.z, 2)}</div>
        <div class="module-points ${cls}">${m.points >= 0 ? "+" : ""}${num(m.points, 2)}</div>
      </div>`;
    }).join("");
    $("moduleNotes").innerHTML = D.meta.notes.slice(1, 4).map((n) => `<div>${n}</div>`).join("");
  }

  /* ---------------- quadrant ---------------- */
  function drawQuadrant() {
    const rows = D.quadrant;
    const points = rows.map((r) => ({ x: r.x, y: r.y }));
    const data = {
      datasets: [
        { label: "近2年轨迹", data: points, backgroundColor: "rgba(227,180,106,.18)", borderColor: "rgba(227,180,106,.32)", borderWidth: 1, pointRadius: 1.6, pointHoverRadius: 4 },
        { label: "当前", data: [{ x: D.current.gli_s, y: D.current.gli_m }], backgroundColor: "#f2f6fb", borderColor: "#080d13", borderWidth: 2, pointRadius: 7, pointHoverRadius: 9 },
      ],
    };
    const options = {
      responsive: true, maintainAspectRatio: false, animation: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(8,13,19,.97)", borderColor: "rgba(255,255,255,.12)", borderWidth: 1,
          titleColor: "#e9eef5", bodyColor: "#a7b5c5", displayColors: false,
          callbacks: { label: (ctx) => `  GLI-S ${num(ctx.raw.x, 1)} · GLI-M ${num(ctx.raw.y, 1)}` },
        },
      },
      scales: {
        x: { min: 0, max: 100, grid: { color: "rgba(255,255,255,.05)" }, border: { display: false }, title: { display: true, text: "GLI-S 存量", color: "#687789", font: { size: 9 } }, ticks: { color: "#687789", stepSize: 20, font: { family: "Bahnschrift, sans-serif", size: 9 } } },
        y: { min: 0, max: 100, position: "right", grid: { color: "rgba(255,255,255,.05)" }, border: { display: false }, title: { display: true, text: "GLI-M 边际", color: "#687789", font: { size: 9 } }, ticks: { color: "#687789", stepSize: 20, font: { family: "Bahnschrift, sans-serif", size: 9 } } },
      },
    };
    quad = new Chart($("quadChart"), { type: "scatter", data, options });
    $("quadFoot").textContent = `${rows[0].d} → ${rows[rows.length - 1].d} · 当前 ${D.meta.as_of}`;
  }

  /* ---------------- assets ---------------- */
  function corrWord(v) {
    if (v >= .35) return "同向偏强";
    if (v >= .15) return "弱同向";
    if (v <= -.35) return "反向偏强";
    if (v <= -.15) return "弱反向";
    return "接近无关";
  }
  function renderAssets() {
    $("assetBody").innerHTML = D.assets.map((a) => {
      const one = a.one_y.startsWith("+") ? "up" : "down";
      const corr = a.corr >= 0 ? "corr-pos" : "corr-neg";
      return `<tr><td>${a.name}</td><td>${num(a.price, 2)}</td><td class="${one}">${a.one_y}</td><td class="${corr}">${signed(a.corr, 2)}</td><td>${corrWord(a.corr)}</td></tr>`;
    }).join("");
  }

  /* ---------------- monthly log ---------------- */
  function renderLog() {
    const rows = (D.monthly || []).slice().reverse();
    $("logBody").innerHTML = rows.map((r) => {
      const tq = r.tqqq == null ? "—" : `${r.tqqq >= 0 ? "+" : ""}${num(r.tqqq, 1)}%`;
      const tqCls = r.tqqq > 0 ? "up" : r.tqqq < 0 ? "down" : "";
      const chg = r.chg == null ? "—" : signed(r.chg, 1);
      return `<tr><td>${r.m}</td><td>${num(r.s, 1)}</td><td>${num(r.m, 1)}</td><td><span class="regime ${r.regime_en}">${r.regime}</span></td><td class="${tqCls}">${tq}</td><td class="${r.chg > 0 ? "up" : r.chg < 0 ? "down" : ""}">${chg}</td></tr>`;
    }).join("");
    if (rows.length) $("logFoot").textContent = `${rows[rows.length - 1].m} → ${rows[0].m} · 月末值 · ${rows.length} 个月`;
  }

  /* ---------------- method ---------------- */
  function renderMethod() {
    $("methodModules").innerHTML = D.current.modules.map((m) => `<div><b>${m.name} · ${m.weight * 100}%</b> &nbsp; ${m.key === "policy" ? "3M/10Y 利率反向 + TLT" : m.key === "usd" ? "DXY / UUP 反向" : m.key === "credit" ? "HYG/LQD、KRE/SPY" : m.key === "cross" ? "EEM/SPY + DXY 反向" : "VIX / MOVE 反向 + HYG"}</div>`).join("");
    $("sourceList").innerHTML = D.meta.sources.map((s) => `<a href="${s.url}" target="_blank" rel="noopener">${s.label} ↗</a>`).join("");
    $("audit").textContent = `数据日 ${D.meta.as_of} · 页面生成 ${D.meta.generated_at} · ${D.meta.observations} 个共同交易日 · ${D.meta.source_note}`;
  }

  function boot() {
    drawYieldChart("all");
    drawPeChart("all");
    drawCashChart();
    drawChart("all");
    drawNdxCharts();
    renderModules();
    drawQuadrant();
    renderAssets();
    renderLog();
    renderMethod();

    document.querySelectorAll("#rangeTabs button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#rangeTabs button").forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        drawChart(btn.dataset.range);
      });
    });
    document.querySelectorAll("#ndxRangeTabs button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#ndxRangeTabs button").forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        drawNdxCharts(btn.dataset.range);
      });
    });

    document.querySelectorAll("#yieldToggles .series-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.key;
        yieldVisible[key] = !yieldVisible[key];
        btn.classList.toggle("active", yieldVisible[key]);
        drawYieldChart(yieldRange);
      });
    });
    document.querySelectorAll("#peToggles .series-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.key;
        peVisible[key] = !peVisible[key];
        btn.classList.toggle("active", peVisible[key]);
        drawPeChart(peRange);
      });
    });
    document.querySelectorAll("#yieldRangeTabs button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#yieldRangeTabs button").forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        drawYieldChart(btn.dataset.range);
      });
    });
    document.querySelectorAll("#peRangeTabs button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#peRangeTabs button").forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        drawPeChart(btn.dataset.range);
      });
    });
    document.querySelectorAll("#cashMode button").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.mode === cashMode);
    });
    document.querySelectorAll("#cashMode button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#cashMode button").forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        cashMode = btn.dataset.mode;
        drawCashChart(cashMode, cashRange);
      });
    });
    document.querySelectorAll("#cashRangeTabs button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#cashRangeTabs button").forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        cashRange = btn.dataset.range;
        drawCashChart(cashMode, cashRange);
      });
    });

    function bindWheel(canvasId, tabsId) {
      const canvas = document.getElementById(canvasId);
      if (!canvas) return;
      canvas.addEventListener("wheel", (e) => {
        const tabs = [...document.querySelectorAll(`#${tabsId} button`)];
        const active = tabs.findIndex((b) => b.classList.contains("is-active"));
        if (active < 0) return;
        e.preventDefault();
        // Scroll down = zoom out (longer range), scroll up = zoom in.
        const next = Math.max(0, Math.min(tabs.length - 1, active + (e.deltaY > 0 ? 1 : -1)));
        if (next !== active) tabs[next].click();
      }, { passive: false });
    }
    bindWheel("gliChart", "rangeTabs");
    bindWheel("ndxChart", "ndxRangeTabs");
    bindWheel("cashChart", "cashRangeTabs");
    bindWheel("yieldChart", "yieldRangeTabs");
    bindWheel("peChart", "peRangeTabs");

    const links = [...document.querySelectorAll(".page-nav a")];
    const sections = links.map((a) => document.querySelector(a.getAttribute("href"))).filter(Boolean);
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        links.forEach((a) => a.classList.toggle("active", a.getAttribute("href") === `#${e.target.id}`));
      });
    }, { rootMargin: "-20% 0px -65% 0px" });
    sections.forEach((s) => io.observe(s));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
