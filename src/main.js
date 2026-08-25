import * as d3 from "d3";
import { feature } from "topojson-client";
import "./styles.css";
const BASE=import.meta.env.BASE_URL,dataUrl=p=>`${BASE}${String(p).replace(/^\//,"")}`;
const VIEWS={labour_hours:{name:"Labour appropriation",unit:"hours",subtitle:"Net embodied labour hours through global supply chains"},wage_value:{name:"Wage value",unit:"eur",subtitle:"Wage value of net-appropriated labour in constant 2005 euros"}};
const SKILLS={all:"All skill levels",low:"Low-skilled",medium:"Medium-skilled",high:"High-skilled"};
document.querySelector("#app").innerHTML=`<div class="shell">
<header class="mast"><div><div class="kicker">EXIOBASE 3 unequal-exchange explorer</div><h1>Unequal Exchange Atlas</h1><p class="lede">Trace labour through the global production system from where work is performed to where final consumption occurs. Results use EXIOBASE's native geography: 44 countries and 5 Rest-of-World regions.</p></div><div class="badge">EXIOBASE 3.8.2</div></header>
<section class="toolbar"><div><span class="control-label">View</span><div class="segmented" id="viewButtons"><button class="active" data-view="labour_hours">Labour hours</button><button data-view="wage_value">Wage value</button></div></div><label><span>Skill level</span><select id="skill" class="control"><option value="all">All skill levels</option><option value="low">Low-skilled</option><option value="medium">Medium-skilled</option><option value="high">High-skilled</option></select></label><label><span>Year</span><select id="year" class="control"></select></label><div class="toolbar-actions"><button id="summaryBtn" class="control">Summary & North–South</button><button id="methodologyBtn" class="control">Methodology</button></div></section>
<section class="timeline card"><button id="playBtn" class="play">▶</button><div class="timeline-main"><div class="timeline-labels"><strong id="timelineYear">—</strong><span id="timelineRange"></span></div><input id="yearSlider" type="range" min="0" max="0" value="0" step="1"></div></section>
<div class="coverage-note"><strong>Map resolution:</strong> individual EXIOBASE countries are shown separately. Clicking a country inside a Rest-of-World aggregate opens the aggregate result. No country-specific value is invented inside those regions.</div>
<main class="grid"><section class="card mapwrap"><div id="loading" class="loading">Loading EXIOBASE-derived results…</div><svg id="map" viewBox="0 0 1000 560"></svg><div class="legend"><div class="small muted">net supplied ← → net appropriated</div><div class="legendbar"></div><div id="legendScale" class="small"></div></div></section><aside id="details" class="card side"><div class="muted">Select a country or aggregate region.</div></aside></main>
<section id="summaryPanel" class="card section" hidden><div class="section-head"><div><div class="kicker">Overview</div><h2>Summary & North–South</h2></div><button id="closeSummary" class="iconbtn">×</button></div><div id="summaryStats" class="summary-stats"></div><div id="northSouthBox" class="benchmark-box"></div><div class="charts-grid"><div class="chart-card"><div class="chart-head"><strong>Global net-flow magnitude</strong><span class="small muted">Timeline</span></div><svg id="globalTrend" viewBox="0 0 700 260"></svg></div><div class="chart-card"><div class="chart-head"><strong>Largest net positions</strong><span id="rankYear" class="small muted"></span></div><svg id="rankChart" viewBox="0 0 700 330"></svg></div><div class="chart-card wide"><div class="chart-head"><strong id="countryTrendTitle">Selected-region trend</strong><span class="small muted">Click the map</span></div><svg id="countryTrend" viewBox="0 0 900 260"></svg></div></div></section>
<section id="methodology" class="card section methodology"><div class="kicker">Methodology</div><h2>How the atlas works</h2><p class="method-intro">The central question is simple: <strong>how much labour performed in one part of the world is embodied in what another part of the world consumes?</strong></p>
<div class="steps">
<article class="step-card"><div class="step-number">1</div><div><h3>Start with the global production network</h3><p>EXIOBASE is a multi-regional input-output database. It links industries across countries, so it traces indirect supply chains rather than only direct border trade.</p><div class="plain-example">A mineral can be extracted in one region, processed in another, assembled in a third and ultimately consumed somewhere else. The MRIO follows that chain.</div></div></article>
<article class="step-card"><div class="step-number">2</div><div><h3>Trace labour to final consumption</h3><p>EXIOBASE records labour hours by region, product sector, gender and low/medium/high skill. The Leontief model traces those hours through all upstream production required for each region's final demand.</p><div class="formula">F = q̂ (I − A)<sup>−1</sup> y</div></div></article>
<article class="step-card"><div class="step-number">3</div><div><h3>Compare both directions</h3><p>If A's consumption embodies 10 billion hours from B while B's consumption embodies 2 billion hours from A, the atlas records a net appropriation of 8 billion hours from B toward A.</p><div class="formula">Net<sub>B→A</sub> = H<sub>B→A</sub> − H<sub>A→B</sub></div></div></article>
<article class="step-card"><div class="step-number">4</div><div><h3>Value net labour by skill</h3><p>The wage-value view values low-, medium- and high-skilled net-appropriated hours using the recipient region's EXIOBASE compensation per exported labour hour for the same skill.</p><div class="plain-example">This is a counterfactual wage valuation, not an observed cash payment.</div></div></article>
<article class="step-card"><div class="step-number">5</div><div><h3>Keep EXIOBASE's real geography</h3><p>There are 44 individual countries and five aggregates: Rest of Asia & Pacific, America, Europe, Africa and Middle East.</p><p>The atlas <strong>does not split these into fake country estimates</strong>. Clicking Kenya, for example, opens Rest of Africa.</p></div></article>
</div>
<details class="math-details"><summary>Show technical details</summary><div class="math-content"><h3>Leontief system</h3><div class="formula">A<sub>ij</sub> = z<sub>ij</sub> / x<sub>j</sub></div><div class="formula">L = (I − A)<sup>−1</sup></div><p>The build solves the sparse system (I−A)X=Y for 49 consumer regions instead of constructing a huge dense inverse.</p><h3>Embodied labour</h3><div class="formula">H = q̂ L Y</div><p>q is direct labour-hours intensity. Calculations are done separately for low-, medium- and high-skilled labour.</p><h3>Wage value</h3><p>A region's export wage equals compensation embodied in its labour exports divided by exported labour hours. Net-appropriated hours are valued at the recipient's same-skill export wage.</p></div></details>
<div class="notice"><strong>Important limitations:</strong> EXIOBASE's original detailed socioeconomic observations largely end around 2011; later years are now-casted. Most Global South countries are inside five Rest-of-World aggregates, so trade occurring within those aggregates is not visible as international trade.</div></section>
<footer class="footer">EXIOBASE 3.8.2 · CC-BY-SA · derived atlas results. North–South totals are calculated directly from the atlas's EXIOBASE results.</footer></div>`;
const ids=["viewButtons","skill","year","summaryBtn","methodologyBtn","playBtn","yearSlider","timelineYear","timelineRange","loading","details","legendScale","summaryPanel","closeSummary","summaryStats","northSouthBox","globalTrend","rankChart","rankYear","countryTrend","countryTrendTitle"],el=Object.fromEntries(ids.map(id=>[id,document.getElementById(id)]));
let meta={},world=[],view="labour_hours",payload=null,selected=null,timer=null,cache=new Map();
const years=()=>[...(meta.years||[])].sort((a,b)=>a-b);
function fmt(v){if(v==null||!Number.isFinite(+v))return"—";const s=v<0?"−":"",a=Math.abs(+v),x=d3.format(".3~s")(a).replace("G","B");return view==="labour_hours"?`${s}${x} h`:`${s}€${x}`}
const fmtH=v=>`${d3.format(".3~s")(Math.abs(+v||0)).replace("G","B")} h`,fmtE=v=>`€${d3.format(".3~s")(Math.abs(+v||0)).replace("G","B")}`;
async function getPayload(v=view,skill=el.skill.value,year=+el.year.value){const k=`${v}-${skill}-${year}`;if(cache.has(k))return cache.get(k);const r=await fetch(dataUrl(`data/exio/${year}/${v}-${skill}.json`));if(!r.ok)throw new Error(`Derived EXIOBASE data for ${year} have not been built.`);const p=await r.json();cache.set(k,p);return p}
async function load(){try{payload=await getPayload();selected=null;render();if(!el.summaryPanel.hidden)await renderSummary()}catch(e){payload={regions:[],bilateral:[]};render();el.details.innerHTML=`<div class="notice">${e.message}</div>`}}
function rebuildYears(){const ys=years(),p=+el.year.value;el.year.innerHTML="";ys.slice().reverse().forEach(y=>el.year.add(new Option(y,y)));el.year.value=String(ys.includes(p)?p:ys.at(-1));syncSlider()}
function syncSlider(){const ys=years(),i=Math.max(0,ys.indexOf(+el.year.value));el.yearSlider.max=Math.max(0,ys.length-1);el.yearSlider.value=i;el.timelineYear.textContent=ys[i]??"—";el.timelineRange.textContent=ys.length?`${ys[0]} — ${ys.at(-1)}`:""}
function regionFor(d){return(meta.geometry||[]).find(x=>String(x.id)===String(d.id))?.exio_region||null}
function nameOf(c){return meta.region_names?.[c]||c}
function render(){if(!world.length||!payload)return;const by=new Map((payload.regions||[]).map(d=>[d.code,d])),vals=[...by.values()].map(d=>+d.net||0),mx=d3.quantile(vals.map(Math.abs).sort(d3.ascending),.95)||1,color=d3.scaleLinear().domain([-mx,0,mx]).range(["#ef6a65","#596574","#59b7a8"]).clamp(true);el.legendScale.textContent=`${fmt(-mx)} • 0 • ${fmt(mx)}`;const svg=d3.select("#map"),proj=d3.geoNaturalEarth1().fitExtent([[15,15],[985,545]],{type:"Sphere"}),path=d3.geoPath(proj);svg.selectAll("path.country").data(world,d=>d.id).join("path").attr("class",d=>{const r=regionFor(d);return`country${r&&meta.row_regions.includes(r)?" aggregate":""}${selected===r?" selected":""}`}).attr("d",path).attr("fill",d=>{const r=by.get(regionFor(d));return r?color(r.net):"#1b2530"}).attr("opacity",d=>by.has(regionFor(d))?1:.42).on("click",(e,d)=>{const r=regionFor(d);if(r&&by.has(r)){selected=r;render();details(by.get(r));if(!el.summaryPanel.hidden)drawCountryTrend()}});svg.selectAll("path.sphere").data([{type:"Sphere"}]).join("path").attr("class","sphere").attr("d",path).attr("fill","none").attr("stroke","#354352");if(selected&&by.has(selected))details(by.get(selected));else el.details.innerHTML=`<div class="kicker">${VIEWS[view].name}</div><h2>${el.year.value}</h2><p class="muted">${VIEWS[view].subtitle}</p><p class="muted">${SKILLS[el.skill.value]}</p><p class="muted">Select a country or aggregate.</p>`}
function details(d){const rel=(payload.bilateral||[]).filter(x=>x.from===d.code||x.to===d.code).sort((a,b)=>b.value-a.value).slice(0,12);el.details.innerHTML=`<div class="kicker">${d.aggregate?"EXIOBASE aggregate":"EXIOBASE country"} · ${d.code}</div><h2>${d.name}</h2>${d.aggregate?`<div class="aggregate-note">Regional aggregate, not a country-specific estimate. ${d.members?.length||0} mapped countries/territories.</div>`:""}<div class="muted">${el.year.value} · ${SKILLS[el.skill.value]}</div><div class="metric ${d.net>=0?"pos":"neg"}">${fmt(d.net)}</div><div class="small muted">net ${view==="labour_hours"?"labour appropriation":"wage value"}</div>${view==="labour_hours"?`<div class="stats"><div class="stat"><span class="small muted">Gross imported labour</span><strong>${fmtH(d.gross_imported)}</strong></div><div class="stat"><span class="small muted">Gross exported labour</span><strong>${fmtH(d.gross_exported)}</strong></div></div>`:""}<div class="flows"><strong>Largest net bilateral relationships</strong>${rel.map(f=>`<div class="flow"><span>${f.to===d.code?"← "+nameOf(f.from):"→ "+nameOf(f.to)}</span><span>${fmt(f.value)}</span></div>`).join("")||'<p class="muted">No net bilateral relationships.</p>'}</div>${d.aggregate?`<details class="members"><summary>Countries contained in this aggregate</summary><p>${(d.members||[]).join(", ")}</p></details>`:""}`}
const magnitude=rows=>d3.sum(rows,d=>Math.abs(+d.net||0))/2;
async function renderSummary(){const rows=payload.regions||[],pos=rows.filter(d=>d.net>0).sort((a,b)=>b.net-a.net),neg=rows.filter(d=>d.net<0).sort((a,b)=>a.net-b.net);el.summaryStats.innerHTML=[["Global net-flow magnitude",fmt(magnitude(rows)),"½Σ |regional net balance|"],["Largest net appropriator",pos[0]?.name||"—",pos[0]?fmt(pos[0].net):"—"],["Largest net supplier",neg[0]?.name||"—",neg[0]?fmt(neg[0].net):"—"],["Native regions",rows.length,"44 countries + 5 ROW aggregates"]].map(x=>`<div class="summary-stat"><span class="small muted">${x[0]}</span><strong>${x[1]}</strong><span class="small muted">${x[2]}</span></div>`).join("");northSouthDashboard();el.rankYear.textContent=el.year.value;rank(pos.slice(0,6),neg.slice(0,6));await globalTrend();await drawCountryTrend()}
function northSouthDashboard(){
  const b=meta.north_south_by_year?.[String(el.year.value)];
  if(!b){
    el.northSouthBox.innerHTML="";
    return;
  }

  const skillRows=Object.entries(b.by_skill||{}).map(([skill,d])=>`
    <tr>
      <td>${SKILLS[skill]||skill}</td>
      <td>${fmtH(d.south_to_north_hours)}</td>
      <td>${fmtH(d.north_to_south_hours)}</td>
      <td>${fmtH(d.net_north_appropriation_hours)}</td>
      <td>${fmtE(d.wage_value_2005_eur)}</td>
    </tr>
  `).join("");

  el.northSouthBox.innerHTML=`
    <h3>North–South flows ${b.year}</h3>
    <p>
      These values are calculated directly from this atlas's EXIOBASE matrices.
      They are not copied from an external study.
    </p>

    <div class="benchmark-grid">
      <div>
        <span>South → North labour</span>
        <strong>${fmtH(b.south_to_north_hours)}</strong>
      </div>
      <div>
        <span>North → South labour</span>
        <strong>${fmtH(b.north_to_south_hours)}</strong>
      </div>
      <div>
        <span>Net North appropriation</span>
        <strong>${fmtH(b.net_north_appropriation_hours)}</strong>
      </div>
      <div>
        <span>Wage value</span>
        <strong>${fmtE(b.wage_value_2005_eur)}</strong>
      </div>
    </div>

    <details class="north-south-details">
      <summary>Show skill breakdown</summary>
      <div class="table-scroll">
        <table class="ns-table">
          <thead>
            <tr>
              <th>Skill</th>
              <th>South → North</th>
              <th>North → South</th>
              <th>Net North</th>
              <th>Wage value</th>
            </tr>
          </thead>
          <tbody>${skillRows}</tbody>
        </table>
      </div>
    </details>

    <p class="small muted">
      “North” follows the atlas's EXIOBASE Global North classification.
      All remaining EXIOBASE regions are grouped as Global South.
    </p>
  `;
}
const clear=n=>d3.select(n).selectAll("*").remove();
function rank(pos,neg){clear(el.rankChart);const svg=d3.select(el.rankChart),data=[...neg.slice().reverse(),...pos];if(!data.length)return;const W=700,H=330,m={t:15,r:80,b:20,l:140},mx=d3.max(data,d=>Math.abs(d.net))||1,x=d3.scaleLinear().domain([-mx,mx]).range([m.l,W-m.r]),y=d3.scaleBand().domain(data.map(d=>d.code)).range([m.t,H-m.b]).padding(.25);svg.append("line").attr("x1",x(0)).attr("x2",x(0)).attr("y1",m.t).attr("y2",H-m.b).attr("stroke","#596574");svg.selectAll("rect").data(data).join("rect").attr("x",d=>x(Math.min(0,d.net))).attr("y",d=>y(d.code)).attr("width",d=>Math.abs(x(d.net)-x(0))).attr("height",y.bandwidth()).attr("fill",d=>d.net>=0?"#59b7a8":"#ef6a65");svg.selectAll("text").data(data).join("text").attr("x",m.l-8).attr("y",d=>y(d.code)+y.bandwidth()/2+4).attr("text-anchor","end").attr("fill","#dce4eb").attr("font-size",11).text(d=>d.name)}
async function globalTrend(){const s=[];for(const y of years()){try{const p=await getPayload(view,el.skill.value,y);s.push({year:y,value:magnitude(p.regions||[])})}catch{}}line(el.globalTrend,s)}
async function drawCountryTrend(){clear(el.countryTrend);if(!selected){d3.select(el.countryTrend).append("text").attr("x",20).attr("y",40).attr("fill","#9aa8b6").text("Select a region on the map.");return}const s=[];for(const y of years()){try{const p=await getPayload(view,el.skill.value,y),r=(p.regions||[]).find(d=>d.code===selected);if(r)s.push({year:y,value:r.net})}catch{}}el.countryTrendTitle.textContent=`${nameOf(selected)}: net balance over time`;line(el.countryTrend,s)}
function line(node,data){clear(node);if(!data.length)return;const svg=d3.select(node),vb=node.viewBox.baseVal,W=vb.width||700,H=vb.height||260,m={t:20,r:22,b:34,l:88};let[lo,hi]=d3.extent(data,d=>d.value);if(lo===hi){const p=Math.abs(lo||1)*.1;lo-=p;hi+=p}lo=Math.min(lo,0);hi=Math.max(hi,0);const x=d3.scalePoint().domain(data.map(d=>d.year)).range([m.l,W-m.r]).padding(.25),y=d3.scaleLinear().domain([lo,hi]).nice().range([H-m.b,m.t]),step=Math.max(1,Math.ceil(data.length/8));svg.append("g").attr("transform",`translate(0,${H-m.b})`).call(d3.axisBottom(x).tickValues(data.filter((_,i)=>i%step===0).map(d=>d.year))).call(g=>g.selectAll("text").attr("fill","#9aa8b6")).call(g=>g.selectAll("line,path").attr("stroke","#354352"));svg.append("g").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickFormat(v=>view==="labour_hours"?d3.format(".2s")(v):"€"+d3.format(".2s")(v).replace("G","B"))).call(g=>g.selectAll("text").attr("fill","#9aa8b6")).call(g=>g.selectAll("line,path").attr("stroke","#354352"));svg.append("path").datum(data).attr("fill","none").attr("stroke","#e0b85a").attr("stroke-width",2.5).attr("d",d3.line().x(d=>x(d.year)).y(d=>y(d.value)))}
function stop(){if(timer)clearInterval(timer);timer=null;el.playBtn.textContent="▶"}
el.playBtn.addEventListener("click",()=>{if(timer){stop();return}const ys=years();if(ys.length<2)return;timer=setInterval(()=>{let i=+el.yearSlider.value+1;if(i>=ys.length)i=0;el.yearSlider.value=i;el.year.value=ys[i];el.timelineYear.textContent=ys[i];load()},1100);el.playBtn.textContent="❚❚"});
el.yearSlider.addEventListener("input",()=>{const y=years()[+el.yearSlider.value];if(y!=null){el.year.value=y;el.timelineYear.textContent=y;load()}});
el.year.addEventListener("change",()=>{syncSlider();load()});el.skill.addEventListener("change",load);el.viewButtons.addEventListener("click",e=>{const b=e.target.closest("button[data-view]");if(!b)return;view=b.dataset.view;[...el.viewButtons.children].forEach(x=>x.classList.toggle("active",x===b));load()});el.summaryBtn.addEventListener("click",async()=>{el.summaryPanel.hidden=false;await renderSummary();el.summaryPanel.scrollIntoView({behavior:"smooth"})});el.closeSummary.addEventListener("click",()=>el.summaryPanel.hidden=true);el.methodologyBtn.addEventListener("click",()=>document.querySelector("#methodology").scrollIntoView({behavior:"smooth"}));
async function init(){try{const[topo,m]=await Promise.all([fetch("https://cdn.jsdelivr.net/npm/world-atlas@2/countries-50m.json").then(r=>r.ok?r.json():Promise.reject(new Error("Map geometry failed"))),fetch(dataUrl("data/exio/meta.json")).then(r=>r.ok?r.json():Promise.reject(new Error("EXIOBASE metadata missing")))]);meta=m;world=feature(topo,topo.objects.countries).features;if(!meta.years?.length)throw new Error("No EXIOBASE years have been built yet. Run the data workflow.");rebuildYears();el.loading.remove();await load()}catch(e){el.loading.innerHTML=`<strong>Data build required.</strong><br>${e.message}`;el.details.innerHTML="<div class='muted'>Run the EXIOBASE workflow first.</div>"}}
init();