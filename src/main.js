import * as d3 from "d3";
import { feature } from "topojson-client";
import "./styles.css";

const BASE = import.meta.env.BASE_URL;
const dataUrl = (path) =>
  `${BASE}${String(path).replace(/^\//, "")}`;

const VIEWS = {
  monetary_transfer: {
    name: "Monetary value",
    unit: "money",
    description:
      "Estimated unequal exchange: embodied employment valued using the difference between consumer- and producer-country average labour income.",
  },
  labour_transfer: {
    name: "Labour transfer",
    unit: "persons",
    description:
      "Best-available embodied employment: OECD MRIO-backed observations where available and a calibrated open-data extension elsewhere.",
  },
};

document.querySelector("#app").innerHTML = `
<div class="shell">
  <header class="mast">
    <div>
      <div class="kicker">Global political economy explorer</div>
      <h1>Unequal Exchange Atlas</h1>
      <p class="lede">
        One methodology with transparent data quality. OECD input-output estimates form
        the high-confidence core; a calibrated open-data extension fills much of the rest
        of the world.
      </p>
    </div>
    <div class="badge" id="sourceBadge">Loading…</div>
  </header>

  <section class="toolbar">
    <div>
      <span class="control-label">View</span>
      <div class="segmented" id="viewButtons">
        <button type="button" class="active" data-view="monetary_transfer">Monetary value</button>
        <button type="button" data-view="labour_transfer">Labour transfer</button>
      </div>
    </div>
    <label>
      <span>Year</span>
      <select id="year" class="control"></select>
    </label>
    <label>
      <span>Coverage</span>
      <select id="coverage" class="control">
        <option value="all">Best available</option>
        <option value="mrio">MRIO-backed only</option>
      </select>
    </label>
    <div class="toolbar-actions">
      <button id="summaryBtn" class="control" type="button">Summary & graphs</button>
      <button id="methodologyBtn" class="control" type="button">Methodology</button>
    </div>
  </section>

  <section class="timeline card">
    <button id="playBtn" class="play" type="button" aria-label="Play timeline">▶</button>
    <div class="timeline-main">
      <div class="timeline-labels">
        <strong id="timelineYear">—</strong>
        <span id="timelineRange"></span>
      </div>
      <input id="yearSlider" type="range" min="0" max="0" value="0" step="1">
    </div>
  </section>

  <div class="qualitykey">
    <span><i class="qdot q-mrio"></i> MRIO-backed</span>
    <span><i class="qdot q-mixed"></i> Mixed</span>
    <span><i class="qdot q-extended"></i> Extended calibrated estimate</span>
  </div>

  <main class="grid">
    <section class="card mapwrap">
      <div id="loading" class="loading">Loading map and generated estimates…</div>
      <svg id="map" viewBox="0 0 1000 560" aria-label="World unequal-exchange map"></svg>
      <div class="legend">
        <div class="small muted">net supplied ← → net received</div>
        <div class="legendbar"></div>
        <div id="legendScale" class="small"></div>
      </div>
    </section>
    <aside id="details" class="card side">
      <div class="muted">Select a country.</div>
    </aside>
  </main>

  <section id="summaryPanel" class="card section" hidden>
    <div class="section-head">
      <div>
        <div class="kicker">Overview</div>
        <h2>Summary statistics & graphs</h2>
      </div>
      <button id="closeSummary" class="iconbtn" type="button">×</button>
    </div>
    <div id="summaryStats" class="summary-stats"></div>
    <div class="charts-grid">
      <div class="chart-card">
        <div class="chart-head"><strong>Global imbalance</strong><span class="small muted">Timeline</span></div>
        <svg id="globalTrend" viewBox="0 0 700 260"></svg>
      </div>
      <div class="chart-card">
        <div class="chart-head"><strong>Largest net positions</strong><span id="rankYear" class="small muted"></span></div>
        <svg id="rankChart" viewBox="0 0 700 330"></svg>
      </div>
      <div class="chart-card wide">
        <div class="chart-head"><strong id="countryTrendTitle">Selected-country trend</strong><span class="small muted">Click a country</span></div>
        <svg id="countryTrend" viewBox="0 0 900 260"></svg>
      </div>
    </div>
  </section>

  <section id="methodology" class="card section methodology">
    <div class="kicker">Methodology</div>
    <h2>One estimator, two data-quality tiers</h2>
    <div class="method-grid">
      <div>
        <h3>Tier A · MRIO-backed</h3>
        <p>For country pairs available in OECD Trade in Employment, the atlas uses the OECD supply-chain estimate directly.</p>
        <div class="formula">H<sub>i→j</sub> = employment in producer i sustained by final demand in j</div>
        <p class="small muted">These observations trace direct and indirect production through the OECD inter-country input-output system.</p>
      </div>
      <div>
        <h3>Tier B · Extended calibrated</h3>
        <p>Elsewhere, the atlas estimates export-linked employment from ILO employment and national exports/GDP, calibrates that relationship against OECD countries in the same year, and allocates the residual across partners using OECD balanced merchandise-trade shares.</p>
        <div class="formula">H̃<sub>i→j</sub> = E<sub>i</sub> · (X<sub>i</sub>/GDP<sub>i</sub>) · m<sub>region,t</sub> · s<sub>ij</sub></div>
        <p class="small muted">This is explicitly an extension model—not an MRIO observation. The map marks it separately.</p>
      </div>
      <div>
        <h3>Monetary counterfactual</h3>
        <p>Average labour income per employed person is estimated consistently across countries:</p>
        <div class="formula">w<sub>i</sub> = labour income share<sub>i</sub> · GDP<sub>i</sub> / Employment<sub>i</sub></div>
        <div class="formula">UE<sub>i→j</sub> = H<sub>i→j</sub> · (w<sub>j</sub> − w<sub>i</sub>)</div>
      </div>
      <div>
        <h3>How to read it</h3>
        <p>The empirical inputs are official/modelled statistics. The unequal-exchange value is a theoretical counterfactual inspired by Emmanuel. “MRIO-backed only” removes the extension without changing the economic definition.</p>
      </div>
    </div>
    <div class="notice">
      <strong>Important:</strong> “Extended calibrated” does not claim country-specific input-output precision.
      It exists so that countries with weaker MRIO coverage are not simply erased from a map of the world economy.
    </div>
  </section>
</div>`;

const ids = [
  "year", "coverage", "viewButtons", "playBtn", "yearSlider",
  "timelineYear", "timelineRange", "sourceBadge", "loading",
  "details", "legendScale", "summaryBtn", "summaryPanel",
  "closeSummary", "summaryStats", "globalTrend", "rankChart",
  "rankYear", "countryTrend", "countryTrendTitle", "methodologyBtn",
];

const el = Object.fromEntries(
  ids.map((id) => [id, document.getElementById(id)])
);

let view = "monetary_transfer";
let world = null;
let meta = {};
let payload = { countries: [], bilateral: [] };
let selected = null;
let cache = new Map();
let timer = null;

function years() {
  return (meta.view_years?.[view] || meta.years || [])
    .slice()
    .sort((a, b) => a - b);
}

function unit() {
  return VIEWS[view].unit;
}

function fmt(value) {
  if (value == null || !Number.isFinite(+value)) return "—";
  const sign = +value < 0 ? "−" : "";
  const abs = Math.abs(+value);
  const compact = d3.format(".3~s")(abs).replace("G", "B");

  if (unit() === "persons") {
    return `${sign}${compact} people`;
  }
  return `${sign}$${compact}`;
}

function filteredFlows(sourcePayload = payload) {
  const all = sourcePayload.bilateral || [];
  return el.coverage.value === "mrio"
    ? all.filter((d) => d.quality === "mrio")
    : all;
}

function rebuildCountriesFromFlows(flows, sourcePayload = payload) {
  const originals = new Map(
    (sourcePayload.countries || []).map((d) => [d.iso3, d])
  );

  const incoming = d3.rollup(
    flows,
    (values) => d3.sum(values, (d) => +d.value || 0),
    (d) => d.to
  );

  const outgoing = d3.rollup(
    flows,
    (values) => d3.sum(values, (d) => +d.value || 0),
    (d) => d.from
  );

  const countries = new Set([
    ...incoming.keys(),
    ...outgoing.keys(),
  ]);

  return [...countries].map((iso) => {
    const original =
      originals.get(iso) || {
        iso3: iso,
        name: iso,
        mrio_share: 1,
        coverage_tier: "mrio",
      };

    const inflow = incoming.get(iso) || 0;
    const outflow = outgoing.get(iso) || 0;

    return {
      ...original,
      inflow,
      outflow,
      net: inflow - outflow,
    };
  });
}

function syncSlider() {
  const ys = years();
  const index = Math.max(0, ys.indexOf(+el.year.value));

  el.yearSlider.max = Math.max(0, ys.length - 1);
  el.yearSlider.value = index;
  el.timelineYear.textContent = ys[index] ?? "—";
  el.timelineRange.textContent =
    ys.length ? `${ys[0]} — ${ys.at(-1)}` : "";
}

function rebuildYears() {
  const ys = years();
  const previous = +el.year.value;
  el.year.innerHTML = "";

  ys.slice().reverse().forEach((year) => {
    el.year.add(new Option(year, year));
  });

  if (ys.includes(previous)) {
    el.year.value = String(previous);
  } else if (ys.length) {
    el.year.value = String(ys.at(-1));
  }

  syncSlider();
}

async function getData(whichView, year) {
  const key = `${whichView}-${year}`;
  if (cache.has(key)) return cache.get(key);

  const response = await fetch(
    dataUrl(`data/${whichView}-${year}.json`)
  );
  if (!response.ok) {
    throw new Error(`No ${whichView} data for ${year}`);
  }

  const result = await response.json();
  cache.set(key, result);
  return result;
}

async function load() {
  if (!el.year.value) return;

  try {
    payload = await getData(view, +el.year.value);
    render();

    if (!el.summaryPanel.hidden) {
      await renderSummary();
    }
  } catch (error) {
    payload = { countries: [], bilateral: [] };
    render();
    el.details.innerHTML =
      `<div class="notice">${error.message}</div>`;
  }
}

function qualityLabel(row) {
  const pct = Math.round(100 * (row.mrio_share || 0));

  if (row.coverage_tier === "mrio") {
    return `MRIO-backed · ${pct}% weighted`;
  }
  if (row.coverage_tier === "mixed") {
    return `Mixed coverage · ${pct}% MRIO-backed`;
  }
  return `Extended calibrated · ${pct}% MRIO-backed`;
}

function render() {
  if (!world) return;

  const flows = filteredFlows();
  const rows = rebuildCountriesFromFlows(flows);
  const byIso = new Map(rows.map((d) => [d.iso3, d]));

  const values = rows.map((d) => +d.net || 0);
  const maxAbs =
    d3.quantile(
      values.map(Math.abs).sort(d3.ascending),
      0.95
    ) || 1;

  const color = d3.scaleLinear()
    .domain([-maxAbs, 0, maxAbs])
    .range(["#ef6a65", "#596574", "#59b7a8"])
    .clamp(true);

  el.legendScale.textContent =
    `${fmt(-maxAbs)} • 0 • ${fmt(maxAbs)}`;

  const svg = d3.select("#map");
  const projection = d3.geoNaturalEarth1().fitExtent(
    [[15, 15], [985, 545]],
    { type: "Sphere" }
  );
  const path = d3.geoPath(projection);
  const geometryIds = new Map(
    (meta.country_ids || []).map((x) => [
      String(x.id),
      x.iso3,
    ])
  );

  svg.selectAll("path.country")
    .data(world, (d) => d.id)
    .join("path")
    .attr("class", (d) => {
      const iso = geometryIds.get(String(d.id));
      const row = byIso.get(iso);
      return `country ${row?.coverage_tier || "nodata"}${
        selected === iso ? " selected" : ""
      }`;
    })
    .attr("d", path)
    .attr("fill", (d) => {
      const row = byIso.get(
        geometryIds.get(String(d.id))
      );
      return row ? color(row.net) : "#1b2530";
    })
    .attr("opacity", (d) =>
      byIso.has(geometryIds.get(String(d.id))) ? 1 : 0.42
    )
    .on("click", async (event, d) => {
      const iso = geometryIds.get(String(d.id));
      const row = byIso.get(iso);
      if (!row) return;

      selected = iso;
      render();
      renderDetails(row, flows);

      if (!el.summaryPanel.hidden) {
        await drawCountryTrend();
      }
    });

  svg.selectAll("path.sphere")
    .data([{ type: "Sphere" }])
    .join("path")
    .attr("class", "sphere")
    .attr("d", path)
    .attr("fill", "none")
    .attr("stroke", "#354352");

  const selectedRow = selected && byIso.get(selected);

  if (selectedRow) {
    renderDetails(selectedRow, flows);
  } else {
    el.details.innerHTML = `
      <div class="kicker">${VIEWS[view].name}</div>
      <h2>${el.year.value}</h2>
      <p class="muted">${VIEWS[view].description}</p>
      <p class="muted">Select a country.</p>
    `;
  }
}

function renderDetails(row, flows) {
  const related = flows
    .filter(
      (x) => x.from === row.iso3 || x.to === row.iso3
    )
    .sort((a, b) => b.value - a.value)
    .slice(0, 12);

  el.details.innerHTML = `
    <div class="kicker">${row.iso3}</div>
    <h2>${row.name}</h2>
    <div class="qualitybadge ${row.coverage_tier}">
      ${qualityLabel(row)}
    </div>
    <div class="muted">${el.year.value} · ${VIEWS[view].name}</div>
    <div class="metric ${row.net >= 0 ? "pos" : "neg"}">
      ${fmt(row.net)}
    </div>
    <div class="small muted">net balance</div>

    <div class="stats">
      <div class="stat">
        <span class="small muted">Received</span>
        <strong>${fmt(row.inflow)}</strong>
      </div>
      <div class="stat">
        <span class="small muted">Supplied</span>
        <strong>${fmt(row.outflow)}</strong>
      </div>
    </div>

    <div class="flows">
      <strong>Largest bilateral relationships</strong>
      ${
        related.length
          ? related.map((flow) => `
              <div class="flow">
                <span>
                  ${
                    flow.to === row.iso3
                      ? `← ${flow.from}`
                      : `→ ${flow.to}`
                  }
                  <em>${
                    flow.quality === "mrio"
                      ? "MRIO-backed"
                      : "extended calibrated"
                  }</em>
                </span>
                <span>${fmt(flow.value)}</span>
              </div>
            `).join("")
          : '<p class="muted">No bilateral records.</p>'
      }
    </div>
  `;
}

function imbalance(rows) {
  return d3.sum(rows, (d) => Math.abs(+d.net || 0)) / 2;
}

async function renderSummary() {
  const flows = filteredFlows();
  const rows = rebuildCountriesFromFlows(flows);

  const positives = rows
    .filter((d) => d.net > 0)
    .sort((a, b) => b.net - a.net);

  const negatives = rows
    .filter((d) => d.net < 0)
    .sort((a, b) => a.net - b.net);

  const total = d3.sum(flows, (d) => d.value);
  const mrio = d3.sum(
    flows.filter((d) => d.quality === "mrio"),
    (d) => d.value
  );

  el.summaryStats.innerHTML = [
    [
      "Global imbalance",
      fmt(imbalance(rows)),
      "½Σ |country net|",
    ],
    [
      "Countries covered",
      rows.length,
      el.coverage.value === "mrio"
        ? "MRIO subset"
        : "best available",
    ],
    [
      "MRIO-backed share",
      total ? `${(100 * mrio / total).toFixed(1)}%` : "—",
      "weighted by displayed flow",
    ],
    [
      "Largest recipient",
      positives[0]?.name || "—",
      positives[0] ? fmt(positives[0].net) : "—",
    ],
  ].map(([label, value, note]) => `
    <div class="summary-stat">
      <span class="small muted">${label}</span>
      <strong>${value}</strong>
      <span class="small muted">${note}</span>
    </div>
  `).join("");

  el.rankYear.textContent = el.year.value;
  drawRank(
    positives.slice(0, 6),
    negatives.slice(0, 6)
  );

  await drawGlobal();
  await drawCountryTrend();
}

function clear(node) {
  d3.select(node).selectAll("*").remove();
}

function drawRank(positive, negative) {
  clear(el.rankChart);

  const svg = d3.select(el.rankChart);
  const data = [
    ...negative.slice().reverse(),
    ...positive,
  ];

  if (!data.length) return;

  const W = 700;
  const H = 330;
  const margin = { t: 15, r: 90, b: 20, l: 120 };
  const max = d3.max(
    data,
    (d) => Math.abs(d.net)
  ) || 1;

  const x = d3.scaleLinear()
    .domain([-max, max])
    .range([margin.l, W - margin.r]);

  const y = d3.scaleBand()
    .domain(data.map((d) => d.iso3))
    .range([margin.t, H - margin.b])
    .padding(0.25);

  svg.append("line")
    .attr("x1", x(0))
    .attr("x2", x(0))
    .attr("y1", margin.t)
    .attr("y2", H - margin.b)
    .attr("stroke", "#596574");

  svg.selectAll("rect")
    .data(data)
    .join("rect")
    .attr("x", (d) => x(Math.min(0, d.net)))
    .attr("y", (d) => y(d.iso3))
    .attr("width", (d) =>
      Math.abs(x(d.net) - x(0))
    )
    .attr("height", y.bandwidth())
    .attr("fill", (d) =>
      d.net >= 0 ? "#59b7a8" : "#ef6a65"
    );

  svg.selectAll("text")
    .data(data)
    .join("text")
    .attr("x", margin.l - 8)
    .attr(
      "y",
      (d) => y(d.iso3) + y.bandwidth() / 2 + 4
    )
    .attr("text-anchor", "end")
    .attr("fill", "#dce4eb")
    .attr("font-size", 12)
    .text((d) => d.iso3);
}

async function countrySeries(iso) {
  const result = [];

  for (const year of years()) {
    try {
      const yearPayload = await getData(view, year);
      const flows =
        el.coverage.value === "mrio"
          ? (yearPayload.bilateral || []).filter(
              (d) => d.quality === "mrio"
            )
          : yearPayload.bilateral || [];

      const row = rebuildCountriesFromFlows(
        flows,
        yearPayload
      ).find((d) => d.iso3 === iso);

      if (row) {
        result.push({
          year,
          value: row.net,
        });
      }
    } catch {
      // Skip unavailable year.
    }
  }

  return result;
}

async function drawGlobal() {
  const series = [];

  for (const year of years()) {
    try {
      const yearPayload = await getData(view, year);
      const flows =
        el.coverage.value === "mrio"
          ? (yearPayload.bilateral || []).filter(
              (d) => d.quality === "mrio"
            )
          : yearPayload.bilateral || [];

      const rows = rebuildCountriesFromFlows(
        flows,
        yearPayload
      );

      series.push({
        year,
        value: imbalance(rows),
      });
    } catch {
      // Skip.
    }
  }

  drawLine(el.globalTrend, series);
}

async function drawCountryTrend() {
  clear(el.countryTrend);

  if (!selected) {
    d3.select(el.countryTrend)
      .append("text")
      .attr("x", 20)
      .attr("y", 40)
      .attr("fill", "#9aa8b6")
      .text("Select a country on the map.");
    return;
  }

  const series = await countrySeries(selected);
  el.countryTrendTitle.textContent =
    `${selected}: net balance over time`;
  drawLine(el.countryTrend, series);
}

function drawLine(node, data) {
  clear(node);
  if (!data.length) return;

  const svg = d3.select(node);
  const viewBox = node.viewBox.baseVal;
  const W = viewBox.width || 700;
  const H = viewBox.height || 260;
  const margin = { t: 20, r: 22, b: 34, l: 82 };

  let [low, high] = d3.extent(
    data,
    (d) => d.value
  );

  if (low === high) {
    const pad = Math.abs(low || 1) * 0.1;
    low -= pad;
    high += pad;
  }

  low = Math.min(low, 0);
  high = Math.max(high, 0);

  const x = d3.scalePoint()
    .domain(data.map((d) => d.year))
    .range([margin.l, W - margin.r])
    .padding(0.25);

  const y = d3.scaleLinear()
    .domain([low, high])
    .nice()
    .range([H - margin.b, margin.t]);

  const tickStep = Math.max(
    1,
    Math.ceil(data.length / 8)
  );

  svg.append("g")
    .attr(
      "transform",
      `translate(0,${H - margin.b})`
    )
    .call(
      d3.axisBottom(x).tickValues(
        data
          .filter((_, i) => i % tickStep === 0)
          .map((d) => d.year)
      )
    )
    .call((g) =>
      g.selectAll("text").attr("fill", "#9aa8b6")
    )
    .call((g) =>
      g.selectAll("line,path").attr("stroke", "#354352")
    );

  svg.append("g")
    .attr("transform", `translate(${margin.l},0)`)
    .call(
      d3.axisLeft(y)
        .ticks(5)
        .tickFormat((v) =>
          unit() === "money"
            ? `$${d3.format(".2s")(v).replace("G", "B")}`
            : d3.format(".2s")(v)
        )
    )
    .call((g) =>
      g.selectAll("text").attr("fill", "#9aa8b6")
    )
    .call((g) =>
      g.selectAll("line,path").attr("stroke", "#354352")
    );

  svg.append("path")
    .datum(data)
    .attr("fill", "none")
    .attr("stroke", "#e0b85a")
    .attr("stroke-width", 2.5)
    .attr(
      "d",
      d3.line()
        .x((d) => x(d.year))
        .y((d) => y(d.value))
    );
}

function stop() {
  if (timer) clearInterval(timer);
  timer = null;
  el.playBtn.textContent = "▶";
}

el.playBtn.addEventListener("click", () => {
  if (timer) {
    stop();
    return;
  }

  const ys = years();
  if (ys.length < 2) return;

  timer = setInterval(() => {
    let index = +el.yearSlider.value + 1;
    if (index >= ys.length) index = 0;

    el.yearSlider.value = index;
    el.year.value = String(ys[index]);
    el.timelineYear.textContent = ys[index];
    load();
  }, 1100);

  el.playBtn.textContent = "❚❚";
});

el.yearSlider.addEventListener("input", () => {
  const year = years()[+el.yearSlider.value];
  if (year == null) return;

  el.year.value = String(year);
  el.timelineYear.textContent = year;
  load();
});

el.year.addEventListener("change", () => {
  syncSlider();
  load();
});

el.coverage.addEventListener("change", () => {
  selected = null;
  render();

  if (!el.summaryPanel.hidden) {
    renderSummary();
  }
});

el.viewButtons.addEventListener("click", (event) => {
  const button = event.target.closest(
    "button[data-view]"
  );
  if (!button) return;

  stop();
  view = button.dataset.view;
  selected = null;

  [...el.viewButtons.children].forEach((child) => {
    child.classList.toggle(
      "active",
      child === button
    );
  });

  rebuildYears();
  load();
});

el.summaryBtn.addEventListener("click", async () => {
  el.summaryPanel.hidden = false;
  await renderSummary();
  el.summaryPanel.scrollIntoView({
    behavior: "smooth",
  });
});

el.closeSummary.addEventListener("click", () => {
  el.summaryPanel.hidden = true;
});

el.methodologyBtn.addEventListener("click", () => {
  document
    .querySelector("#methodology")
    .scrollIntoView({ behavior: "smooth" });
});

async function init() {
  try {
    const [topology, metadata] = await Promise.all([
      fetch(
        "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-50m.json"
      ).then((response) => {
        if (!response.ok) {
          throw new Error("Map geometry failed");
        }
        return response.json();
      }),
      fetch(dataUrl("data/meta.json")).then(
        (response) => {
          if (!response.ok) {
            throw new Error("meta.json missing");
          }
          return response.json();
        }
      ),
    ]);

    meta = metadata;
    world = feature(
      topology,
      topology.objects.countries
    ).features;

    if (!meta.years?.length) {
      throw new Error(
        "No generated data yet. Run the GitHub Actions data workflow."
      );
    }

    el.sourceBadge.textContent =
      "OECD + ILOSTAT + World Bank · quality-labelled";

    rebuildYears();
    el.loading.remove();
    await load();
  } catch (error) {
    el.loading.innerHTML = `
      <strong>Data build required.</strong><br>
      ${error.message}
    `;
    el.sourceBadge.textContent = "Build required";
  }
}

init();
