#!/usr/bin/env python3
from __future__ import annotations
import argparse, gc, json, math, re, shutil, time
from pathlib import Path
import country_converter as coco
import numpy as np
import pandas as pd
import pycountry
import pymrio
from scipy import sparse
from scipy.sparse.linalg import splu

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/"cache/exiobase"
OUT=ROOT/"build/exio"
PUBLIC=ROOT/"public/data/exio"
DOI="10.5281/zenodo.5589597"
SYSTEM="pxp"

REGION_NAMES={"AT":"Austria","BE":"Belgium","BG":"Bulgaria","CY":"Cyprus","CZ":"Czech Republic","DE":"Germany","DK":"Denmark","EE":"Estonia","ES":"Spain","FI":"Finland","FR":"France","GR":"Greece","HR":"Croatia","HU":"Hungary","IE":"Ireland","IT":"Italy","LT":"Lithuania","LU":"Luxembourg","LV":"Latvia","MT":"Malta","NL":"Netherlands","PL":"Poland","PT":"Portugal","RO":"Romania","SE":"Sweden","SI":"Slovenia","SK":"Slovakia","GB":"United Kingdom","US":"United States","JP":"Japan","CN":"China","CA":"Canada","KR":"South Korea","BR":"Brazil","IN":"India","MX":"Mexico","RU":"Russia","AU":"Australia","CH":"Switzerland","TR":"Turkey","TW":"Taiwan","NO":"Norway","ID":"Indonesia","ZA":"South Africa","WA":"Rest of Asia & Pacific","WL":"Rest of America","WE":"Rest of Europe","WF":"Rest of Africa","WM":"Rest of Middle East"}
ROW_CODES={"WA","WL","WE","WF","WM"}
GLOBAL_NORTH={"US","GB","CA","AU","NO","AT","BE","DE","DK","FR","LU","NL","FI","SE","CH","JP","KR","EE","ES","GR","IE","IT","LV","MT","PT","SI","SK","TW","CY","CZ"}
SKILLS={
"low":{"hours":["employment hours","low-skilled"],"people":["employment:","low-skilled"],"comp":["compensation of employees","low-skilled"]},
"medium":{"hours":["employment hours","medium-skilled"],"people":["employment:","medium-skilled"],"comp":["compensation of employees","medium-skilled"]},
"high":{"hours":["employment hours","high-skilled"],"people":["employment:","high-skilled"],"comp":["compensation of employees","high-skilled"]},
}
EXPECTED_2021={"south_to_north_hours":906e9,"north_to_south_hours":80e9,"net_hours":826e9,"wage_value_2005_eur":16.9e12}

def log(x): print(x,flush=True)
def norm(x): return re.sub(r"\s+"," ",str(x).lower().replace("–","-").replace("—","-")).strip()

def labels(df):
    if isinstance(df.index,pd.MultiIndex):
        return [" | ".join(map(str,x if isinstance(x,tuple) else (x,))) for x in df.index]
    return [str(x) for x in df.index]

def find_rows(df,terms):
    out=[]
    for i,l in enumerate(labels(df)):
        n=norm(l)
        if all(norm(t) in n for t in terms): out.append(i)
    return out

def need_rows(df,terms,kind):
    r=find_rows(df,terms)
    if not r: raise RuntimeError(f"Could not identify {kind}: {terms}. First stressors:\n"+"\n".join(labels(df)[:80]))
    return r

def download_year(year):
    CACHE.mkdir(parents=True,exist_ok=True)
    expected=CACHE/f"IOT_{year}_{SYSTEM}.zip"
    if expected.exists() and expected.stat().st_size>1_000_000:return expected
    for attempt in range(1,5):
        try:
            log(f"Downloading EXIOBASE 3.8.2 {year}, attempt {attempt}/4")
            pymrio.download_exiobase3(storage_folder=str(CACHE),years=[year],system=SYSTEM,overwrite_existing=False,doi=DOI)
            if expected.exists():return expected
            c=list(CACHE.glob(f"*{year}*{SYSTEM}*.zip"))
            if c:return c[0]
            raise RuntimeError("Expected EXIOBASE archive not found")
        except Exception as e:
            if attempt==4:raise
            log(f"Retry after error: {e}")
            time.sleep(20*attempt)

def extension(io):
    for name in ("satellite","employment","factor_inputs"):
        ext=getattr(io,name,None)
        if ext is not None and getattr(ext,"S",None) is not None:return ext
    raise RuntimeError("No EXIOBASE socioeconomic extension with S matrix found")

def region_vector(index):
    if not isinstance(index,pd.MultiIndex): raise RuntimeError("Expected EXIOBASE MultiIndex")
    return np.array(index.get_level_values("region" if "region" in index.names else 0).astype(str))

def group_Y(Y,regions):
    level="region" if isinstance(Y.columns,pd.MultiIndex) and "region" in Y.columns.names else 0
    g=Y.T.groupby(level=level,sort=False).sum().T
    return g.reindex(columns=regions,fill_value=0)

def unit_for(ext,row):
    u=getattr(ext,"unit",None)
    if u is None:return ""
    try:
        return str(u.iloc[row,0] if isinstance(u,pd.DataFrame) else u.iloc[row])
    except Exception:return ""

def scale_from_unit(unit,kind):
    u=norm(unit)
    if kind in ("hours","comp"):
        if "m.hr" in u or "m.eur" in u or "million" in u:return 1e6
        if "1000" in u or "thousand" in u:return 1e3
    if kind=="people":
        if "1000" in u or "thousand" in u:return 1e3
        if "million" in u:return 1e6
    return 1.0

def intensity(S,rows,ext,kind):
    return S.iloc[rows,:].sum(axis=0).to_numpy(float)*scale_from_unit(unit_for(ext,rows[0]),kind)

def agg_region(mat,sec_regions,regions):
    out=np.zeros((len(regions),mat.shape[1]),float)
    for i,r in enumerate(regions): out[i,:]=mat[sec_regions==r,:].sum(axis=0)
    return out

def solve(A,Yreg):
    log("Converting A to sparse matrix")
    Asp=sparse.csc_matrix(A.to_numpy(float,copy=False))
    M=sparse.eye(Asp.shape[0],format="csc")-Asp
    log(f"Sparse LU factorisation: {Asp.shape[0]:,} sectors/products")
    lu=splu(M)
    Q=lu.solve(Yreg.to_numpy(float))
    del lu,M,Asp
    gc.collect()
    return Q

def geography(regions):
    cc=coco.CountryConverter()
    alias={"WWA":"WA","WWL":"WL","WWE":"WE","WWF":"WF","WWM":"WM"}
    mapping={};members={r:[] for r in regions};geometry=[]
    for c in pycountry.countries:
        iso3=c.alpha_3
        try:m=cc.convert(iso3,src="ISO3",to="EXIO3",not_found=None)
        except Exception:m=None
        if isinstance(m,list):m=m[0] if m else None
        m=alias.get(m,m)
        if m not in regions:m=None
        if m:
            mapping[iso3]=m;members.setdefault(m,[]).append(iso3)
        if getattr(c,"numeric",None):geometry.append({"id":str(c.numeric).zfill(3),"iso3":iso3,"exio_region":m})
    return mapping,members,geometry

def exported_wage(C,H):
    n=H.shape[0];w=np.full(n,np.nan)
    for i in range(n):
        mask=np.ones(n,bool);mask[i]=False
        hh=H[i,mask].sum();cc=C[i,mask].sum()
        if hh>0:w[i]=cc/hh
    return w

def pairwise_net(H,regions):
    rec=[]
    for i in range(len(regions)):
        for j in range(i+1,len(regions)):
            s=float(H[i,j]-H[j,i])
            if s>0:rec.append({"from":regions[i],"to":regions[j],"value":s})
            elif s<0:rec.append({"from":regions[j],"to":regions[i],"value":-s})
    return rec

def summary_net(records,regions):
    inc={r:0.0 for r in regions};out={r:0.0 for r in regions}
    for x in records:out[x["from"]]+=x["value"];inc[x["to"]]+=x["value"]
    return {r:{"received":inc[r],"supplied":out[r],"net":inc[r]-out[r]} for r in regions}

def gross(H,regions):
    out={}
    for i,r in enumerate(regions):
        mask=np.ones(len(regions),bool);mask[i]=False
        out[r]={"gross_imported":float(H[mask,i].sum()),"gross_exported":float(H[i,mask].sum()),"domestic":float(H[i,i])}
    return out

def benchmark(hours,comp,regions,year):
    idx={r:i for i,r in enumerate(regions)}
    north=[idx[r] for r in GLOBAL_NORTH if r in idx]
    south=[i for i,r in enumerate(regions) if r not in GLOBAL_NORTH]
    stn=nts=wv=0.0;net_skill={};north_wage={}
    for sk in SKILLS:
        H=hours[sk];C=comp[sk]
        a=float(H[np.ix_(south,north)].sum());b=float(H[np.ix_(north,south)].sum())
        stn+=a;nts+=b;net=a-b;net_skill[sk]=net
        he=ce=0.0
        for i in north:
            mask=np.ones(len(regions),bool);mask[i]=False
            he+=float(H[i,mask].sum());ce+=float(C[i,mask].sum())
        wage=ce/he if he>0 else math.nan;north_wage[sk]=wage
        if net>0 and math.isfinite(wage):wv+=net*wage
    res={"year":year,"south_to_north_hours":stn,"north_to_south_hours":nts,"net_hours":stn-nts,"net_hours_by_skill":net_skill,"north_export_wage_eur_per_hour_by_skill":north_wage,"wage_value_2005_eur":wv}
    if year==2021:
        res["published_hickel_2021"]=EXPECTED_2021
        res["difference_pct"]={k:100*(res[k]-EXPECTED_2021[k])/EXPECTED_2021[k] for k in EXPECTED_2021}
    return res

def build(year,keep_raw=False):
    if not 1995<=year<=2022:raise ValueError("Use EXIOBASE years 1995-2022")
    archive=download_year(year)
    log(f"Parsing {archive.name}")
    io=pymrio.parse_exiobase3(str(archive))
    A=io.A;Y=io.Y;ext=extension(io)
    regions=list(dict.fromkeys(region_vector(A.index).tolist()))
    if len(regions)!=49:log(f"WARNING expected 49 regions, parsed {len(regions)}")
    sec_regions=region_vector(A.index)
    Yreg=group_Y(Y,regions)
    rows={}
    for sk,spec in SKILLS.items():
        rows[sk]={k:need_rows(ext.S,v,f"{sk} {k}") for k,v in spec.items()}
    Q=solve(A,Yreg)
    io.A=None;io.Y=None;gc.collect()
    hours={};people={};comp={}
    for sk in SKILLS:
        hi=intensity(ext.S,rows[sk]["hours"],ext,"hours")
        pi=intensity(ext.S,rows[sk]["people"],ext,"people")
        ci=intensity(ext.S,rows[sk]["comp"],ext,"comp")
        hours[sk]=agg_region(hi[:,None]*Q,sec_regions,regions)
        people[sk]=agg_region(pi[:,None]*Q,sec_regions,regions)
        comp[sk]=agg_region(ci[:,None]*Q,sec_regions,regions)
    mapping,members,geometry=geography(set(regions))
    ydir=OUT/str(year);ydir.mkdir(parents=True,exist_ok=True)
    for sel in ["low","medium","high","all"]:
        if sel=="all":
            H=sum(hours.values());P=sum(people.values())
        else:H=hours[sel];P=people[sel]
        labrec=pairwise_net(H,regions);labsum=summary_net(labrec,regions);gh=gross(H,regions);gp=gross(P,regions)
        for r in regions:
            labsum[r].update(gh[r]);labsum[r]["gross_imported_employment_equivalents"]=gp[r]["gross_imported"];labsum[r]["gross_exported_employment_equivalents"]=gp[r]["gross_exported"]
        lp={"year":year,"view":"labour_hours","skill":sel,"unit":"hours","regions":[{"code":r,"name":REGION_NAMES.get(r,r),"aggregate":r in ROW_CODES,"members":sorted(members.get(r,[])),**labsum[r]} for r in regions],"bilateral":labrec}
        skills=list(SKILLS) if sel=="all" else [sel]
        edges={}
        for sk in skills:
            Hk=hours[sk];Ck=comp[sk];w=exported_wage(Ck,Hk)
            for i in range(len(regions)):
                for j in range(i+1,len(regions)):
                    s=float(Hk[i,j]-Hk[j,i])
                    if s>0:src,dst,hrs,wage=regions[i],regions[j],s,w[j]
                    elif s<0:src,dst,hrs,wage=regions[j],regions[i],-s,w[i]
                    else:continue
                    if not math.isfinite(wage) or wage<0:continue
                    e=edges.setdefault((src,dst),{"from":src,"to":dst,"value":0.0,"hours":0.0})
                    e["value"]+=hrs*wage;e["hours"]+=hrs
        wr=list(edges.values());ws=summary_net(wr,regions)
        wp={"year":year,"view":"wage_value","skill":sel,"unit":"constant_2005_EUR","regions":[{"code":r,"name":REGION_NAMES.get(r,r),"aggregate":r in ROW_CODES,"members":sorted(members.get(r,[])),**ws[r]} for r in regions],"bilateral":wr,"note":"Counterfactual wage value of pairwise net-appropriated labour, valued at the recipient region's same-skill export wage."}
        (ydir/f"labour_hours-{sel}.json").write_text(json.dumps(lp,separators=(",",":"),allow_nan=False))
        (ydir/f"wage_value-{sel}.json").write_text(json.dumps(wp,separators=(",",":"),allow_nan=False))
    b=benchmark(hours,comp,regions,year)
    (ydir/"benchmark.json").write_text(json.dumps(b,indent=2,allow_nan=False))
    manifest={"year":year,"exiobase_version":"3.8.2","exiobase_doi":DOI,"system":SYSTEM,"regions":regions,"region_names":{r:REGION_NAMES.get(r,r) for r in regions},"row_regions":sorted(ROW_CODES & set(regions)),"country_to_region":mapping,"geometry":geometry,"members":members,"global_north":sorted(GLOBAL_NORTH & set(regions)),"benchmark":b,"skills":["all","low","medium","high"],"views":["labour_hours","wage_value"]}
    (ydir/"manifest.json").write_text(json.dumps(manifest,indent=2,allow_nan=False))
    dest=PUBLIC/str(year)
    if dest.exists():shutil.rmtree(dest)
    shutil.copytree(ydir,dest)
    log(f"Finished {year}: {dest}")
    if not keep_raw:
        try:archive.unlink()
        except Exception:pass

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--year",type=int,required=True);ap.add_argument("--keep-raw",action="store_true")
    a=ap.parse_args();build(a.year,a.keep_raw)
