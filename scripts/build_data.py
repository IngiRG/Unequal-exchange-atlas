#!/usr/bin/env python3
"""
Open-data builder for the Unequal Exchange Atlas.

Primary empirical backbone (no Eora):
  OECD Trade in Employment (TiM) 2025 edition
  - OECD ICIO-derived bilateral employment sustained by foreign final demand
  - official employment and compensation-of-employees by industry
  - 1995-2022, EU/OECD/G20 + most East/Southeast Asian economies

Optional broad goods layer:
  CEPII BACI 202601 (Etalab Open Licence 2.0)
  - ~200 countries, HS6 bilateral goods trade
  - HS92: 1995-2024
  World Bank GDP/person employed is used ONLY as a labelled broad proxy where a
  true cross-country wage series is unavailable.

All published atlas values are derived estimates. Source data remain attributable
to their publishers. No Eora data, licence, account or token is used.
"""
from __future__ import annotations
import argparse, io, json, os, re, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import pycountry
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"public/data"
CACHE=ROOT/"cache"
OUT.mkdir(parents=True,exist_ok=True); CACHE.mkdir(exist_ok=True)

OECD_BASE="https://sdmx.oecd.org/public/rest/data/OECD.STI.PIE,DSD_TIM_2025@DF_TIM_2025,1.0"
# Measure.REF_AREA.ACTIVITY.COUNTERPART.UNIT.FREQ
OECD_QUERIES={
    # Persons, unit multiplier 10^3 in the OECD dataset.
    "ffd": "FFD_DEM.._T..PS.A",
    "employment": "EMPN.._T.W.PS.A",
    # USD, unit multiplier 10^6 in the OECD dataset.
    "compensation": "LABR.._T.W.USD.A",
}
OECD_YEARS=range(1995,2023)

BACI_VERSION=os.getenv("BACI_VERSION","202601")
BACI_HS=os.getenv("BACI_HS","22")  # Scheduled default: small recent archive.
BACI_URL=os.getenv("BACI_ARCHIVE_URL",f"https://www.cepii.fr/DATA_DOWNLOAD/baci/data/BACI_HS{BACI_HS}_V{BACI_VERSION}.zip")
BACI_RANGES={"92":range(1995,2025),"96":range(1996,2025),"02":range(2002,2025),
             "07":range(2007,2025),"12":range(2012,2025),"17":range(2017,2025),"22":range(2022,2025)}
WB="https://api.worldbank.org/v2/country/all/indicator/{indicator}?format=json&per_page=20000&date={year}"
GDP="NY.GDP.MKTP.CD"
GDP_EMP="SL.GDP.PCAP.EM.KD"

SOURCES={
 "oecd_tim":{
  "name":"OECD Trade in Employment (TiM), 2025 edition",
  "url":"https://www.oecd.org/en/data/datasets/trade-in-employment.html",
  "api":"https://sdmx.oecd.org/public/rest/",
  "coverage":"1995-2022; EU/OECD/G20 and most East/Southeast Asian economies; 50 industries",
  "license":"OECD Terms and Conditions (Data): reuse, adaptation, distribution and embedding permitted with attribution unless specific additional restrictions apply.",
  "attribution":"OECD (2026), Trade in Employment (TiM), 2025 edition, accessed via OECD Data Explorer."
 },
 "baci":{
  "name":"CEPII BACI",
  "url":"https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37",
  "version":BACI_VERSION,"hs_revision":BACI_HS,
  "license":"Etalab Open Licence 2.0",
  "attribution":"CEPII, BACI; Gaulier and Zignago (2010)."
 },
 "world_bank":{
  "name":"World Bank Open Data",
  "url":"https://data.worldbank.org/",
  "license":"World Bank-produced datasets are generally CC BY 4.0, subject to dataset-specific terms.",
  "attribution":"World Bank Open Data."
 }
}

METHODS={
 "emmanuel_wage":{
  "name":"Emmanuel bilateral wage counterfactual",
  "source":["oecd_tim"],"unit":"current USD/year",
  "definition":"OECD embodied employment in producer i for consumer j, multiplied by the annual compensation-per-worker gap between j and i.",
  "formula":"UE_i→j = H_i→j (w_j - w_i)"
 },
 "wage_equalisation":{
  "name":"Common-wage equalisation",
  "source":["oecd_tim"],"unit":"current USD/year",
  "definition":"OECD embodied employment valued at a common employment-weighted reference compensation per worker.",
  "formula":"UE_i→j = H_i→j (w* - w_i)"
 },
 "embodied_labour":{
  "name":"Embodied employment transfer",
  "source":["oecd_tim"],"unit":"persons",
  "definition":"Persons employed in producer i whose production is sustained by final demand in consumer j, traced through the OECD ICIO system.",
  "formula":"H_i→j = ê B FD_j"
 },
 "labour_terms":{
  "name":"Labour terms of exchange",
  "source":["oecd_tim"],"unit":"persons",
  "definition":"Bilateral embodied employment. Country net balances compare employment supplied for foreign final demand with employment embodied abroad for domestic final demand.",
  "formula":"ΔH_i = Σ_j H_j→i - Σ_j H_i→j"
 },
 "goods_wage_proxy":{
  "name":"Broad goods wage/productivity proxy",
  "source":["baci","world_bank"],"unit":"current USD estimate",
  "definition":"BACI goods exports revalued by the ratio of World Bank GDP per person employed. Broad country coverage, but not a direct wage or labour-value measure.",
  "formula":"UE_i→j = X_i→j (p_j/p_i - 1)"
 }
}

def log(s): print(s,flush=True)

def get_csv(url, cache:Path, *, timeout=600):
    if cache.exists() and cache.stat().st_size>100:
        return pd.read_csv(cache)
    cache.parent.mkdir(parents=True,exist_ok=True)
    headers={"Accept":"text/csv;version=2"}
    log("GET "+url)
    r=requests.get(url,headers=headers,timeout=timeout); r.raise_for_status()
    cache.write_bytes(r.content)
    return pd.read_csv(io.BytesIO(r.content))

def oecd_table(kind,start,end):
    q=OECD_QUERIES[kind]
    url=f"{OECD_BASE}/{q}?startPeriod={start}&endPeriod={end}&dimensionAtObservation=AllDimensions"
    return get_csv(url,CACHE/"oecd"/f"{kind}-{start}-{end}.csv")

def col(df,*names):
    cmap={str(c).upper():c for c in df.columns}
    for n in names:
        if n.upper() in cmap:return cmap[n.upper()]
    raise RuntimeError(f"Missing column {names}; received {list(df.columns)}")

def normalize_oecd_value(df):
    """Convert OECD OBS_VALUE using UNIT_MULT (10^n) when present."""
    v=pd.to_numeric(df[col(df,"OBS_VALUE","ObsValue")],errors="coerce")
    try:
        mult=pd.to_numeric(df[col(df,"UNIT_MULT","Unit multiplier")],errors="coerce").fillna(0)
    except RuntimeError:
        mult=pd.Series(0,index=df.index)
    return v*np.power(10.0,mult)

def oecd_inputs(start,end):
    ffd=oecd_table("ffd",start,end)
    emp=oecd_table("employment",start,end)
    comp=oecd_table("compensation",start,end)

    def tidy(d):
        out=pd.DataFrame({
          "iso":d[col(d,"REF_AREA")].astype(str),
          "activity":d[col(d,"ACTIVITY","ECONOMIC_ACTIVITY")].astype(str),
          "year":pd.to_numeric(d[col(d,"TIME_PERIOD")],errors="coerce"),
          "value":normalize_oecd_value(d)
        })
        if any(str(c).upper()=="COUNTERPART_AREA" for c in d.columns):
            out["partner"]=d[col(d,"COUNTERPART_AREA")].astype(str)
        return out

    F=tidy(ffd); E=tidy(emp); C=tidy(comp)
    # Query already requests _T, but retain this guard if API semantics change.
    F=F[F.activity.eq("_T") | F.activity.str.upper().isin(["TOTAL","T"])]
    E=E[E.activity.eq("_T") | E.activity.str.upper().isin(["TOTAL","T"])]
    C=C[C.activity.eq("_T") | C.activity.str.upper().isin(["TOTAL","T"])]

    # Only ISO3-like economies; discard OECD aggregates and World.
    valid=lambda s:s.str.fullmatch(r"[A-Z]{3}") & ~s.isin(["WLD"])
    F=F[valid(F.iso)&valid(F.partner)&F.iso.ne(F.partner)].copy()
    E=E[valid(E.iso)].copy(); C=C[valid(C.iso)].copy()
    E=E.groupby(["iso","year"],as_index=False).value.sum()
    C=C.groupby(["iso","year"],as_index=False).value.sum()
    wages=E.merge(C,on=["iso","year"],suffixes=("_emp","_comp"))
    wages["wage"]=np.divide(wages.value_comp,wages.value_emp,
        out=np.full(len(wages),np.nan),where=wages.value_emp.to_numpy()!=0)
    F=F.groupby(["iso","partner","year"],as_index=False).value.sum()
    return F,wages

def wb(ind,year):
    r=requests.get(WB.format(indicator=ind,year=year),timeout=180);r.raise_for_status()
    p=r.json(); out={}
    for x in (p[1] if isinstance(p,list) and len(p)>1 else []):
        k=(x.get("countryiso3code") or "").upper(); v=x.get("value")
        if re.fullmatch(r"[A-Z]{3}",k) and v is not None:out[k]=float(v)
    return out

def names():
    return {c.alpha_3:getattr(c,"common_name",c.name) for c in pycountry.countries}

def aggregate(flows,year,method,gdp,nm,provenance):
    flows=flows[flows["from"].ne(flows["to"]) & np.isfinite(flows["value"])].copy()
    infl=flows.groupby("to").value.sum(); out=flows.groupby("from").value.sum()
    isos=sorted(set(infl.index)|set(out.index)); rows=[]
    for iso in isos:
        a=float(infl.get(iso,0)); b=float(out.get(iso,0)); net=a-b
        gv=gdp.get(iso)
        rows.append({"iso3":iso,"name":nm.get(iso,iso),"inflow":a,"outflow":b,"net":net,
                     "gdp_share":100*net/gv if gv and method not in {"embodied_labour","labour_terms"} else None})
    payload={"countries":rows,"bilateral":flows[["from","to","value"]].to_dict("records"),
             "year":year,"method":method,"provenance":provenance,"model_derived":True}
    (OUT/f"{method}-{year}.json").write_text(json.dumps(payload,separators=(",",":"),allow_nan=False))

def build_oecd(start,end):
    F,W=oecd_inputs(start,end); nm=names()
    method_years={k:[] for k in ["emmanuel_wage","wage_equalisation","embodied_labour","labour_terms"]}
    for year in range(start,end+1):
        fy=F[F.year.eq(year)].copy(); wy=W[W.year.eq(year)].copy()
        if fy.empty or wy.empty:
            log(f"Skip OECD {year}: no observations"); continue
        wm=dict(zip(wy.iso,wy.wage)); emp=dict(zip(wy.iso,wy.value_emp))
        fy=fy[fy.iso.isin(wm)&fy.partner.isin(wm)&fy.value.gt(0)].copy()
        if fy.empty: continue
        gdp=wb(GDP,year)
        base=fy.rename(columns={"iso":"from","partner":"to","value":"value"})[["from","to","value"]]
        prov={"source":"OECD TiM 2025","measure":"FFD_DEM","year":year,
              "note":"OECD ICIO-derived persons employed in producer country to satisfy final demand in partner country."}
        aggregate(base,year,"embodied_labour",gdp,nm,prov)
        aggregate(base,year,"labour_terms",gdp,nm,prov)
        method_years["embodied_labour"].append(year);method_years["labour_terms"].append(year)

        ew=fy.copy()
        ew["value"]=ew.apply(lambda r:r["value"]*(wm[r["partner"]]-wm[r["iso"]]),axis=1)
        aggregate(ew.rename(columns={"iso":"from","partner":"to"}),year,"emmanuel_wage",gdp,nm,
                  prov|{"wage":"OECD TiM LABR / EMPN","counterfactual":"consumer-country compensation per worker"})
        method_years["emmanuel_wage"].append(year)

        total_emp=sum(emp.get(i,0) for i in wm if np.isfinite(wm[i]))
        wstar=sum(emp.get(i,0)*wm[i] for i in wm if np.isfinite(wm[i]))/total_emp
        eq=fy.copy();eq["value"]=eq.apply(lambda r:r["value"]*(wstar-wm[r["iso"]]),axis=1)
        aggregate(eq.rename(columns={"iso":"from","partner":"to"}),year,"wage_equalisation",gdp,nm,
                  prov|{"wage":"OECD TiM LABR / EMPN","reference_wage":wstar,
                        "counterfactual":"employment-weighted common compensation per worker"})
        method_years["wage_equalisation"].append(year)
        log(f"Built OECD layers {year}: {len(fy):,} bilateral observations")
    return method_years

def download(url,path):
    if path.exists() and path.stat().st_size>100:return path
    path.parent.mkdir(parents=True,exist_ok=True);part=path.with_suffix(".part")
    log("GET "+url)
    with requests.get(url,stream=True,timeout=1800) as r:
        r.raise_for_status()
        with part.open("wb") as f:
            for x in r.iter_content(1024*1024):
                if x:f.write(x)
    part.replace(path);return path

def baci_metadata(z):
    for n in z.namelist():
        if n.lower().endswith(".csv") and "country" in n.lower():
            d=pd.read_csv(z.open(n)); lo={str(c).lower():c for c in d.columns}
            code=next((c for c in d.columns if "country_code" in str(c).lower()),None)
            iso=next((c for c in d.columns if "iso" in str(c).lower() and "alpha" in str(c).lower()),None)
            if code and iso:
                d[code]=pd.to_numeric(d[code],errors="coerce");d[iso]=d[iso].astype(str).str.upper()
                q=d[d[code].notna()&d[iso].str.fullmatch(r"[A-Z]{3}")]
                if len(q)>150:return dict(zip(q[code].astype(int),q[iso]))
    raise RuntimeError("Could not find BACI country-code table in official archive.")

def build_baci(years):
    legal=set(BACI_RANGES.get(BACI_HS,[]))
    years=[y for y in years if y in legal]
    if not years:return []
    arc=download(BACI_URL,CACHE/"baci"/f"BACI_HS{BACI_HS}_V{BACI_VERSION}.zip")
    nm=names();built=[]
    with zipfile.ZipFile(arc) as z:
        codes=baci_metadata(z)
        for year in years:
            rx=re.compile(rf"BACI_HS{re.escape(BACI_HS)}_Y{year}_V{re.escape(BACI_VERSION)}\.csv$",re.I)
            hit=next((n for n in z.namelist() if rx.search(Path(n).name)),None)
            if not hit: log(f"Missing BACI {year} in archive");continue
            totals={}
            for ch in pd.read_csv(z.open(hit),usecols=["i","j","v"],chunksize=600_000):
                g=ch.groupby(["i","j"]).v.sum()
                for k,v in g.items():totals[k]=totals.get(k,0)+float(v)
            d=pd.DataFrame([(codes.get(int(i)),codes.get(int(j)),v*1000) for (i,j),v in totals.items()],
                           columns=["from","to","trade"]).dropna()
            p=wb(GDP_EMP,year);gdp=wb(GDP,year)
            d["pi"]=d["from"].map(p);d["pj"]=d["to"].map(p)
            d=d[(d.pi>0)&(d.pj>0)&d["from"].ne(d["to"])].copy()
            d["value"]=d.trade*(d.pj/d.pi-1)
            aggregate(d,year,"goods_wage_proxy",gdp,nm,
                      {"source":f"CEPII BACI HS{BACI_HS} V{BACI_VERSION} + World Bank",
                       "proxy":"GDP per person employed (constant PPP $)",
                       "warning":"Broad goods-only productivity proxy; not direct wage or MRIO labour transfer."})
            built.append(year);log(f"Built BACI proxy {year}")
    return built

def geometry_ids():
    return [{"id":str(c.numeric).zfill(3),"iso3":c.alpha_3} for c in pycountry.countries if getattr(c,"numeric",None)]

def parse_years(xs):
    out=[]
    for x in xs:
        if ":" in x:
            a,b=map(int,x.split(":"));out.extend(range(a,b+1))
        else:out.append(int(x))
    return sorted(set(out))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",choices=["oecd","baci","all"],default="all")
    ap.add_argument("--years",nargs="+",default=["1995:2022"])
    ap.add_argument("--clean",action="store_true")
    a=ap.parse_args();years=parse_years(a.years)
    if a.clean:
        for p in OUT.glob("*.json"):p.unlink()
    method_years={}
    if a.mode in {"oecd","all"}:
        oy=[y for y in years if y in OECD_YEARS]
        if oy:method_years.update(build_oecd(min(oy),max(oy)))
    if a.mode in {"baci","all"}:
        by=build_baci(years);method_years["goods_wage_proxy"]=by

    # Preserve method years already generated when running modes separately.
    old={}
    mp=OUT/"meta.json"
    if mp.exists():
        try:old=json.loads(mp.read_text()).get("method_years",{})
        except Exception:old={}
    for k,v in old.items():
        method_years.setdefault(k,v)
    method_years={k:sorted(set(v)) for k,v in method_years.items() if v}
    all_years=sorted(set(y for ys in method_years.values() for y in ys))
    meta={"mode":"derived-real-open-data","years":all_years,"method_years":method_years,
          "available_methods":list(method_years),"country_ids":geometry_ids(),
          "sources":SOURCES,"methods":{k:METHODS[k] for k in method_years},
          "generated_by":"scripts/build_data.py","eora_used":False}
    mp.write_text(json.dumps(meta,separators=(",",":")))
    (OUT/"sources.json").write_text(json.dumps(SOURCES,indent=2))
    log("Done. No Eora dependency; public/data contains only derived atlas files and provenance.")
if __name__=="__main__":main()
