
import * as d3 from "d3";
import { feature } from "topojson-client";
import "./styles.css";

const METHODS = {
  emmanuel_wage: {
    name: "Emmanuel bilateral wage counterfactual",
    short: "Embodied jobs × partner wage gap",
    english: "The strongest Emmanuel-style layer in the open-data version. OECD Trade in Employment gives the number of people employed in producer country i whose production is sustained by final demand in consumer country j. Annual compensation per worker is calculated from OECD employee compensation divided by employment. The counterfactual asks what the same embodied employment would be worth at the consumer country's compensation level.",
    formula: String.raw`UE_{i→j}=H_{i→j}(w_j-w_i),\qquad w_i=\frac{Compensation_i}{Employment_i}`,
    needs: "OECD TiM 2025: embodied employment + compensation of employees + employment"
  },
  wage_equalisation: {
    name: "Common-wage equalisation",
    short: "Embodied jobs × common wage",
    english: "Values OECD supply-chain embodied employment at one common compensation-per-worker benchmark. The reference wage is the employment-weighted mean among economies with usable data in that year. This isolates the monetary transfer implied by equalising the value assigned to a worker across production locations.",
    formula: String.raw`UE_{i→j}=H_{i→j}(w^*-w_i),\qquad w^*=\frac{\sum_i E_iw_i}{\sum_iE_i}`,
    needs: "OECD TiM 2025"
  },
  embodied_labour: {
    name: "Embodied employment transfer",
    short: "Supply-chain jobs",
    english: "A non-monetary layer using OECD's ICIO-derived Trade in Employment measure. H(i→j) is the number of people employed in producer country i to satisfy final demand in consumer country j. It traces direct and indirect supply-chain requirements. It measures embodied employment, not labour-hours.",
    formula: String.raw`H_{i→j}=\sum_{s\in i}\left[\hat e(I-A)^{-1}FD_j\right]_s`,
    needs: "OECD TiM 2025, measure FFD_DEM"
  },
  labour_terms: {
    name: "Labour terms of exchange",
    short: "Jobs given / jobs received",
    english: "Compares supply-chain employment a country provides for foreign final demand with employment embodied abroad for its own final demand. A negative country balance means it supplies more embodied employment to others than it receives through its consumption.",
    formula: String.raw`\Delta H_i=\sum_jH_{j→i}-\sum_jH_{i→j}`,
    needs: "OECD TiM 2025, bilateral embodied employment"
  },
  goods_wage_proxy: {
    name: "Broad goods productivity proxy",
    short: "~200-country goods proxy",
    english: "A broad-coverage supplementary layer. CEPII BACI bilateral goods exports are revalued using World Bank GDP per person employed. It reaches far more countries and extends through 2024, but GDP per worker is not a wage and customs trade does not trace indirect supply chains. Treat this as a robustness/context layer, not the headline estimate.",
    formula: String.raw`UE_{i→j}=X_{ij}\left(\frac{p_j}{p_i}-1\right)`,
    needs: "CEPII BACI + World Bank GDP per person employed"
  }
};

const app = document.querySelector("#app");
app.innerHTML = `
<div class="shell">
  <header class="mast">
    <div><div class="kicker">Global political economy explorer</div><h1>Unequal Exchange Atlas</h1>
    <p class="lede">Explore estimated bilateral value and labour transfers under alternative definitions of unequal exchange. Results are model-dependent estimates, not directly observed “imperialism” statistics.</p></div>
    <div class="badge" id="sourceBadge">Loading data…</div>
  </header>
  <section class="toolbar">
    <label><span>Method</span><select id="method" class="control"></select></label>
    <label><span>Year</span><select id="year" class="control"></select></label>
    <label><span>Map metric</span><select id="metric" class="control"><option value="net">Net transfer</option><option value="outflow">Estimated outflow</option><option value="inflow">Estimated inflow</option><option value="gdp_share">Net as % of GDP</option></select></label>
    <div class="toolbar-actions"><button id="summaryBtn" class="control">Summary & graphs</button><button id="methodologyBtn" class="control">Methodology</button></div>
  </section>
  <section class="timeline card" aria-label="Timeline controls">
    <button id="playBtn" type="button" class="play" aria-label="Play timeline">▶</button>
    <div class="timeline-main"><div class="timeline-labels"><strong id="timelineYear">2022</strong><span id="timelineRange"></span></div>
    <input id="yearSlider" type="range" min="0" max="0" step="1" value="0" aria-label="Year timeline"></div>
  </section>
  <main class="grid">
    <section class="card mapwrap"><div class="loading" id="loading">Loading world geometry and derived results…</div><svg id="map" viewBox="0 0 1000 560" aria-label="World choropleth of unequal exchange estimates"></svg>
      <div class="legend"><div class="small muted">loss / transfer out ← → gain / transfer in</div><div class="legendbar"></div><div class="small" id="legendScale"></div></div></section>
    <aside class="card side" id="details"><div class="muted">Select a country on the map.</div></aside>
  </main>
  <section class="summary-panel card section" id="summaryPanel" hidden>
    <div class="section-head"><div><div class="kicker">Openable overview</div><h2>Summary statistics & graphs</h2></div><button id="closeSummary" type="button" class="iconbtn" aria-label="Close summary">×</button></div>
    <div class="summary-stats" id="summaryStats"></div>
    <div class="charts-grid">
      <div class="chart-card"><div class="chart-head"><strong>Global transfer magnitude</strong><span class="small muted">Across available years</span></div><svg id="globalTrend" viewBox="0 0 700 260"></svg></div>
      <div class="chart-card"><div class="chart-head"><strong>Largest net positions</strong><span class="small muted" id="rankYear"></span></div><svg id="rankChart" viewBox="0 0 700 330"></svg></div>
      <div class="chart-card wide"><div class="chart-head"><strong id="countryTrendTitle">Selected-country trend</strong><span class="small muted">Click a country to inspect its history</span></div><svg id="countryTrend" viewBox="0 0 900 260"></svg></div>
    </div>
  </section>
  <section class="footergrid">
    <div class="card section" id="methodology">
      <h3>Methodology</h3><div class="method-buttons" id="methodButtons"></div>
      <h2 id="methodTitle"></h2><p id="methodEnglish"></p><div class="formula" id="methodFormula"></div>
      <p class="small muted" id="methodNeeds"></p>
      <div class="notice">Interpretation matters: these are counterfactual/model-derived quantities. The site deliberately exposes the formula and data requirements for each layer.</div>
    </div>
    <div class="card section"><h3>Largest bilateral estimates</h3><div class="tablewrap"><table><thead><tr><th>From</th><th>To</th><th>Estimate</th></tr></thead><tbody id="topFlows"></tbody></table></div></div>
  </section>
</div>`;

const els = Object.fromEntries(["method","year","metric","details","sourceBadge","loading","legendScale","methodButtons","methodTitle","methodEnglish","methodFormula","methodNeeds","topFlows","methodologyBtn","summaryBtn","summaryPanel","closeSummary","summaryStats","globalTrend","rankChart","countryTrend","countryTrendTitle","rankYear","yearSlider","timelineYear","timelineRange","playBtn"].map(id=>[id,document.getElementById(id)]));
function populateMethods(){
  els.method.innerHTML=""; els.methodButtons.innerHTML="";
  const available=meta.available_methods?.length?meta.available_methods:Object.keys(METHODS);
  available.filter(k=>METHODS[k]).forEach(k=>{
    const m=METHODS[k]; els.method.add(new Option(m.name,k));
    const b=document.createElement("button"); b.type="button"; b.textContent=m.short; b.dataset.method=k;
    b.addEventListener("click",()=>{els.method.value=k; rebuildYearsForMethod(); renderMethod(); loadYear();});
    els.methodButtons.appendChild(b);
  });
}
function methodYears(){ return (meta.method_years?.[els.method.value] || meta.years || []).slice().sort((a,b)=>a-b); }
function rebuildYearsForMethod(){
  const years=methodYears(), previous=+els.year.value;
  els.year.innerHTML="";
  years.slice().sort((a,b)=>b-a).forEach(y=>els.year.add(new Option(y,y)));
  if(years.includes(previous)) els.year.value=String(previous);
  else if(years.length) els.year.value=String(years[years.length-1]);
  syncSliderFromYear();
}
els.methodologyBtn.addEventListener("click",()=>document.querySelector("#methodology").scrollIntoView({behavior:"smooth",block:"start"}));
els.summaryBtn.addEventListener("click",async()=>{els.summaryPanel.hidden=false; await renderSummary(); els.summaryPanel.scrollIntoView({behavior:"smooth",block:"start"});});
els.closeSummary.addEventListener("click",()=>{els.summaryPanel.hidden=true;});
els.method.addEventListener("change",()=>{rebuildYearsForMethod(); renderMethod(); loadYear()});
els.year.addEventListener("change",()=>{syncSliderFromYear(); loadYear();});
els.metric.addEventListener("change",render);
els.yearSlider.addEventListener("input",()=>{const years=timelineYears(); const y=years[+els.yearSlider.value]; if(y!=null){els.year.value=String(y); els.timelineYear.textContent=y; loadYear();}});
let playTimer=null;
els.playBtn.addEventListener("click",()=>togglePlay());

let world, records=[], bilateral=[], selected=null, meta={}, yearCache=new Map();

function timelineYears(){ return methodYears(); }
function syncSliderFromYear(){
  const years=timelineYears(), idx=Math.max(0,years.indexOf(+els.year.value));
  els.yearSlider.max=Math.max(0,years.length-1); els.yearSlider.value=idx;
  els.timelineYear.textContent=years[idx]??"—";
  els.timelineRange.textContent=years.length?`${years[0]} — ${years[years.length-1]}`:"";
}
function togglePlay(){
  if(playTimer){ clearInterval(playTimer); playTimer=null; els.playBtn.textContent="▶"; els.playBtn.setAttribute("aria-label","Play timeline"); return; }
  const years=timelineYears(); if(years.length<2) return;
  els.playBtn.textContent="❚❚"; els.playBtn.setAttribute("aria-label","Pause timeline");
  playTimer=setInterval(()=>{ let i=+els.yearSlider.value+1; if(i>=years.length)i=0; els.yearSlider.value=i; els.year.value=String(years[i]); els.timelineYear.textContent=years[i]; loadYear(); },1100);
}

function renderMethod(){
  const k=els.method.value||"emmanuel_proxy", m=METHODS[k];
  els.methodTitle.textContent=m.name; els.methodEnglish.textContent=m.english; els.methodFormula.textContent=m.formula; els.methodNeeds.textContent="Data required: "+m.needs;
  [...els.methodButtons.children].forEach(b=>b.classList.toggle("active",b.dataset.method===k));
}
function applyAvailability(){
  const available=new Set(meta.available_methods||[]);
  [...els.method.options].forEach(o=>{o.disabled=!available.has(o.value); o.textContent=METHODS[o.value].name+(available.has(o.value)?"":" — unavailable");});
  [...els.methodButtons.children].forEach(b=>{b.disabled=!available.has(b.dataset.method); b.title=available.has(b.dataset.method)?"":"This layer has not been legally built from its required source data.";});
  if(!available.has(els.method.value)){
    const first=[...available][0];
    if(first) els.method.value=first;
  }
  renderMethod();
}
renderMethod();

function fmt(v, kind="money"){
  if(v==null || !Number.isFinite(+v)) return "—";
  v=+v;
  if(kind==="pct") return `${v.toFixed(2)}%`;
  if(kind==="hours" || kind==="persons") return d3.format(".3~s")(v)+(kind==="persons"?" people":" h");
  return (v<0?"−":"") + "$" + d3.format(".3~s")(Math.abs(v));
}

async function init(){
  try{
    const [topology, metadata] = await Promise.all([
      fetch("https://cdn.jsdelivr.net/npm/world-atlas@2/countries-50m.json").then(r=>r.json()),
      fetch("/data/meta.json").then(r=>r.ok?r.json():{})
    ]);
    meta=metadata; world=feature(topology,topology.objects.countries).features;
    const years=meta.years?.length?meta.years:[];
    years.slice().sort((a,b)=>b-a).forEach(y=>els.year.add(new Option(y,y)));
    applyAvailability();
    if(!years.length || !(meta.available_methods||[]).length){
      els.sourceBadge.textContent="Real data not built yet";
      els.loading.textContent="No synthetic fallback is published. Run the real-data update workflow to fetch licensed/open sources and calculate the atlas.";
      els.year.disabled=true; els.yearSlider.disabled=true; els.playBtn.disabled=true;
      return;
    }
    els.sourceBadge.textContent="Real derived dataset";
    els.loading.remove();
    syncSliderFromYear();
    await loadYear();
  }catch(e){els.loading.textContent="Could not load data: "+e.message}
}

async function loadYear(){
  selected=null;
  const method=els.method.value||"emmanuel_proxy", year=els.year.value||2022;
  let payload;
  try{
    const r=await fetch(`/data/${method}-${year}.json`);
    if(!r.ok) throw new Error("This methodology/year has not been built.");
    payload=await r.json();
  }catch(err){
    records=[]; bilateral=[]; render();
    els.details.innerHTML=`<div class="notice"><strong>Layer unavailable.</strong><br>${err.message} The site will not substitute another methodology.</div>`;
    return;
  }
  records=payload.countries||[]; bilateral=payload.bilateral||[];
  yearCache.set(`${method}-${year}`, payload);
  syncSliderFromYear();
  render();
  if(!els.summaryPanel.hidden) renderSummary();
}

function render(){
  if(!world) return;
  const metric=els.metric.value;
  const byIso=new Map(records.map(d=>[d.iso3,d]));
  const values=records.map(d=>+d[metric]||0);
  const maxAbs=d3.quantile(values.map(Math.abs).sort(d3.ascending),.95)||1;
  const color=d3.scaleLinear().domain([-maxAbs,0,maxAbs]).range(["#ef6a65","#596574","#59b7a8"]).clamp(true);
  els.legendScale.textContent=`${fmt(-maxAbs,metric==="gdp_share"?"pct":"money")}   •   0   •   ${fmt(maxAbs,metric==="gdp_share"?"pct":"money")}`;

  const svg=d3.select("#map"), projection=d3.geoNaturalEarth1().fitExtent([[15,15],[985,545]],{type:"Sphere"}), path=d3.geoPath(projection);
  const mapId=new Map((meta.country_ids||[]).map(x=>[String(x.id),x.iso3]));
  svg.selectAll("path.country").data(world,d=>d.id).join("path")
    .attr("class",d=>"country"+(selected&&mapId.get(String(d.id))===selected?" selected":""))
    .attr("d",path)
    .attr("fill",d=>{const r=byIso.get(mapId.get(String(d.id))); return r?color(+r[metric]||0):"#1b2530"})
    .attr("opacity",d=>byIso.has(mapId.get(String(d.id)))?1:.55)
    .on("click",(ev,d)=>{const iso=mapId.get(String(d.id)); if(iso&&byIso.has(iso)){selected=iso; render(); renderDetails(byIso.get(iso)); if(!els.summaryPanel.hidden) drawCountryTrend(metricUnit());}});
  svg.selectAll("path.sphere").data([{type:"Sphere"}]).join("path").attr("class","sphere").attr("d",path).attr("fill","none").attr("stroke","#354352");
  if(selected && byIso.has(selected)) renderDetails(byIso.get(selected)); else els.details.innerHTML='<div class="muted">Select a country on the map.</div>';
  renderTopFlows();
}

function renderDetails(d){
  const unit=["labour_terms","embodied_labour"].includes(els.method.value)?"persons":"money";
  const flows=bilateral.filter(x=>x.from===d.iso3||x.to===d.iso3).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value)).slice(0,12);
  els.details.innerHTML=`<div class="kicker">${d.iso3}</div><h2>${d.name}</h2><div class="muted">${els.year.value} · ${METHODS[els.method.value].name}</div>
  <div class="metric ${d.net>=0?"pos":"neg"}">${fmt(d.net,unit)}</div><div class="small muted">net estimated balance</div>
  <div class="stats"><div class="stat"><span class="small muted">Outflow</span><strong>${fmt(d.outflow,unit)}</strong></div><div class="stat"><span class="small muted">Inflow</span><strong>${fmt(d.inflow,unit)}</strong></div><div class="stat"><span class="small muted">GDP share</span><strong>${fmt(d.gdp_share,"pct")}</strong></div><div class="stat"><span class="small muted">Partners</span><strong>${flows.length}</strong></div></div>
  <div class="flows"><strong>Largest bilateral relationships</strong>${flows.map(f=>`<div class="flow"><span>${f.from===d.iso3?"→ "+f.to:"← "+f.from}</span><span class="${f.value>=0?"neg":"pos"}">${fmt(Math.abs(f.value),unit)}</span></div>`).join("")||'<p class="muted">No bilateral records.</p>'}</div>`;
}

function renderTopFlows(){
  const unit=["labour_terms","embodied_labour"].includes(els.method.value)?"persons":"money";
  els.topFlows.innerHTML=bilateral.slice().sort((a,b)=>Math.abs(b.value)-Math.abs(a.value)).slice(0,50)
    .map(f=>`<tr><td>${f.from}</td><td>${f.to}</td><td>${fmt(f.value,unit)}</td></tr>`).join("");
}

async function getYearPayload(method, year){
  const key=`${method}-${year}`;
  if(yearCache.has(key)) return yearCache.get(key);
  try{
    const r=await fetch(`/data/${method}-${year}.json`);
    if(!r.ok) return null;
    const p=await r.json(); yearCache.set(key,p); return p;
  }catch{return null}
}
function metricUnit(){ return ["labour_terms","embodied_labour"].includes(els.method.value)?"persons":"money"; }
function sumAbsNet(rows){ return rows.reduce((s,d)=>s+Math.abs(+d.net||0),0)/2; }

async function renderSummary(){
  if(els.summaryPanel.hidden) return;
  const unit=metricUnit(), year=+els.year.value;
  const positives=records.filter(d=>(+d.net||0)>0).sort((a,b)=>b.net-a.net);
  const negatives=records.filter(d=>(+d.net||0)<0).sort((a,b)=>a.net-b.net);
  const total=sumAbsNet(records);
  const biggestGain=positives[0], biggestLoss=negatives[0];
  els.summaryStats.innerHTML=[
    ["Global transfer magnitude",fmt(total,unit),"½Σ |net country balance|"],
    ["Largest net recipient",biggestGain?.name||"—",biggestGain?fmt(biggestGain.net,unit):"—"],
    ["Largest net contributor",biggestLoss?.name||"—",biggestLoss?fmt(biggestLoss.net,unit):"—"],
    ["Countries covered",String(records.length),`${bilateral.length} bilateral estimates`]
  ].map(([a,b,c])=>`<div class="summary-stat"><span class="small muted">${a}</span><strong>${b}</strong><span class="small muted">${c}</span></div>`).join("");
  els.rankYear.textContent=String(year);
  drawRankChart(positives.slice(0,6),negatives.slice(0,6),unit);
  await drawGlobalTrend(unit);
  await drawCountryTrend(unit);
}
function cleanSvg(el){ d3.select(el).selectAll("*").remove(); }
function drawRankChart(pos,neg,unit){
  const svg=d3.select(els.rankChart); cleanSvg(els.rankChart);
  const data=[...neg.slice().reverse(),...pos], W=700,H=330, m={t:15,r:75,b:20,l:120};
  if(!data.length){svg.append("text").attr("x",20).attr("y",35).attr("fill","#9aa8b6").text("No ranking data.");return}
  const max=d3.max(data,d=>Math.abs(+d.net||0))||1;
  const x=d3.scaleLinear().domain([-max,max]).range([m.l,W-m.r]);
  const y=d3.scaleBand().domain(data.map(d=>d.iso3)).range([m.t,H-m.b]).padding(.25);
  svg.append("line").attr("x1",x(0)).attr("x2",x(0)).attr("y1",m.t).attr("y2",H-m.b).attr("stroke","#596574");
  svg.selectAll("rect").data(data).join("rect").attr("x",d=>x(Math.min(0,d.net))).attr("y",d=>y(d.iso3)).attr("width",d=>Math.abs(x(d.net)-x(0))).attr("height",y.bandwidth()).attr("rx",3).attr("fill",d=>d.net>=0?"#59b7a8":"#ef6a65");
  svg.selectAll("text.name").data(data).join("text").attr("class","name").attr("x",m.l-8).attr("y",d=>y(d.iso3)+y.bandwidth()/2+4).attr("text-anchor","end").attr("fill","#dce4eb").attr("font-size",12).text(d=>d.iso3);
  svg.selectAll("text.val").data(data).join("text").attr("class","val").attr("x",d=>d.net>=0?x(d.net)+7:x(d.net)-7).attr("y",d=>y(d.iso3)+y.bandwidth()/2+4).attr("text-anchor",d=>d.net>=0?"start":"end").attr("fill","#9aa8b6").attr("font-size",11).text(d=>fmt(d.net,unit));
}
async function drawGlobalTrend(unit){
  const years=timelineYears(), method=els.method.value, series=[];
  for(const y of years){ const p=await getYearPayload(method,y); if(p) series.push({year:y,value:sumAbsNet(p.countries||[])}); }
  drawLine(els.globalTrend,series,d=>d.year,d=>d.value,{unit,empty:"No multi-year data available."});
}
async function drawCountryTrend(unit){
  cleanSvg(els.countryTrend);
  if(!selected){d3.select(els.countryTrend).append("text").attr("x",20).attr("y",40).attr("fill","#9aa8b6").text("Select a country on the map to show its timeline."); els.countryTrendTitle.textContent="Selected-country trend"; return;}
  const years=timelineYears(), method=els.method.value, series=[]; let name=selected;
  for(const y of years){ const p=await getYearPayload(method,y); const row=(p?.countries||[]).find(d=>d.iso3===selected); if(row){name=row.name||selected; series.push({year:y,value:+row.net||0});}}
  els.countryTrendTitle.textContent=`${name}: net balance over time`;
  drawLine(els.countryTrend,series,d=>d.year,d=>d.value,{unit,zero:true,empty:"No history for this country."});
}
function drawLine(el,data,xv,yv,opt={}){
  const svg=d3.select(el); cleanSvg(el); const vb=el.viewBox.baseVal, W=vb.width||700,H=vb.height||260,m={t:20,r:22,b:34,l:74};
  if(data.length<1){svg.append("text").attr("x",20).attr("y",40).attr("fill","#9aa8b6").text(opt.empty||"No data.");return}
  let [lo,hi]=d3.extent(data,yv); if(lo===hi){lo-=Math.abs(lo||1)*.1;hi+=Math.abs(hi||1)*.1}
  if(opt.zero){lo=Math.min(lo,0);hi=Math.max(hi,0)}
  const x=d3.scalePoint().domain(data.map(xv)).range([m.l,W-m.r]).padding(.25);
  const y=d3.scaleLinear().domain([lo,hi]).nice().range([H-m.b,m.t]);
  svg.append("g").attr("transform",`translate(0,${H-m.b})`).call(d3.axisBottom(x).tickValues(data.length>8?data.filter((_,i)=>i%Math.ceil(data.length/8)===0).map(xv):data.map(xv))).call(g=>g.selectAll("text").attr("fill","#9aa8b6")).call(g=>g.selectAll("line,path").attr("stroke","#354352"));
  svg.append("g").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickFormat(v=>opt.unit==="hours"?d3.format(".2s")(v):"$"+d3.format(".2s")(v))).call(g=>g.selectAll("text").attr("fill","#9aa8b6")).call(g=>g.selectAll("line,path").attr("stroke","#354352"));
  if(opt.zero&&lo<0&&hi>0)svg.append("line").attr("x1",m.l).attr("x2",W-m.r).attr("y1",y(0)).attr("y2",y(0)).attr("stroke","#596574").attr("stroke-dasharray","4 4");
  svg.append("path").datum(data).attr("fill","none").attr("stroke","#e0b85a").attr("stroke-width",2.5).attr("d",d3.line().x(d=>x(xv(d))).y(d=>y(yv(d))));
  svg.selectAll("circle").data(data).join("circle").attr("cx",d=>x(xv(d))).attr("cy",d=>y(yv(d))).attr("r",4).attr("fill","#e0b85a").append("title").text(d=>`${xv(d)}: ${fmt(yv(d),opt.unit)}`);
}

init();
