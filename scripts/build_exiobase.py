#!/usr/bin/env python3
from __future__ import annotations
import argparse, gc, json, math, re, shutil, time
from pathlib import Path
import country_converter as coco
import numpy as np
import pandas as pd
import pycountry
import pymrio
import requests
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
    """
    Download the exact EXIOBASE 3.8.2 archive directly from Zenodo.

    PyMRIO's Zenodo downloader can fail to resolve older record layouts even
    though the files are publicly available. Using the official file endpoint
    avoids that discovery step while still downloading from the canonical
    EXIOBASE 3.8.2 Zenodo record.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    expected = CACHE / f"IOT_{year}_{SYSTEM}.zip"

    # A valid EXIOBASE pxp archive is hundreds of MB. A 50 MB floor catches
    # HTML error pages or partial downloads without hard-coding each year's size.
    minimum_size = 50 * 1024 * 1024

    if expected.exists() and expected.stat().st_size >= minimum_size:
        log(
            f"Using cached EXIOBASE archive "
            f"{expected.name} ({expected.stat().st_size / 1e6:.1f} MB)"
        )
        return expected

    if expected.exists():
        expected.unlink()

    url = (
        f"https://zenodo.org/records/5589597/files/"
        f"IOT_{year}_{SYSTEM}.zip?download=1"
    )
    partial = expected.with_suffix(expected.suffix + ".part")

    for attempt in range(1, 5):
        try:
            if partial.exists():
                partial.unlink()

            log(
                f"Downloading EXIOBASE 3.8.2 {year} ({SYSTEM}) "
                f"directly from Zenodo, attempt {attempt}/4"
            )

            with requests.get(
                url,
                stream=True,
                timeout=(60, 1800),
                headers={
                    "User-Agent": (
                        "Unequal-Exchange-Atlas/3.0 "
                        "(academic EXIOBASE analysis)"
                    )
                },
            ) as response:
                response.raise_for_status()

                content_type = (
                    response.headers.get("content-type", "")
                    .lower()
                )
                if "text/html" in content_type:
                    raise RuntimeError(
                        "Zenodo returned HTML instead of the EXIOBASE ZIP."
                    )

                expected_length = int(
                    response.headers.get("content-length", "0") or 0
                )
                downloaded = 0

                with partial.open("wb") as handle:
                    for chunk in response.iter_content(
                        chunk_size=4 * 1024 * 1024
                    ):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        downloaded += len(chunk)

                        # Log roughly every 100 MB.
                        if (
                            downloaded // (100 * 1024 * 1024)
                            !=
                            (downloaded - len(chunk))
                            // (100 * 1024 * 1024)
                        ):
                            log(
                                f"Downloaded "
                                f"{downloaded / 1e6:.0f} MB..."
                            )

                actual_size = partial.stat().st_size

                if actual_size < minimum_size:
                    raise RuntimeError(
                        f"Downloaded file is too small "
                        f"({actual_size / 1e6:.1f} MB); "
                        "likely an incomplete response."
                    )

                # Content-Length can be absent on redirected/chunked downloads,
                # so only enforce it when Zenodo supplies one.
                if (
                    expected_length > 0
                    and actual_size != expected_length
                ):
                    raise RuntimeError(
                        f"Incomplete EXIOBASE download: "
                        f"{actual_size} of {expected_length} bytes."
                    )

            partial.replace(expected)
            log(
                f"EXIOBASE archive ready: "
                f"{expected.name} "
                f"({expected.stat().st_size / 1e6:.1f} MB)"
            )
            return expected

        except Exception as exc:
            if partial.exists():
                partial.unlink()

            if attempt == 4:
                raise RuntimeError(
                    f"Failed to download EXIOBASE "
                    f"{year} after 4 attempts: {exc}"
                ) from exc

            log(
                f"Download attempt {attempt} failed: {exc}. "
                "Retrying..."
            )
            time.sleep(20 * attempt)

    raise RuntimeError("EXIOBASE download failed unexpectedly.")

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


def fetch_population(year):
    """Annual population by ISO3 code, using World Bank with OWID fallback."""
    cache_dir = ROOT / "cache/population"
    cache_dir.mkdir(parents=True, exist_ok=True)
    year_file = cache_dir / f"population-{year}.json"
    if year_file.exists():
        return json.loads(year_file.read_text())

    population = {}
    wb_url = (
        "https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL"
        f"?format=json&per_page=400&page=1&date={year}"
    )
    try:
        r = requests.get(wb_url, timeout=180)
        r.raise_for_status()
        payload = r.json()
        rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
        for item in rows:
            iso = str(item.get("countryiso3code") or "").upper()
            value = item.get("value")
            if re.fullmatch(r"[A-Z]{3}", iso) and value is not None:
                population[iso] = float(value)
    except Exception as exc:
        log(f"World Bank population fetch failed: {exc}")

    owid_path = cache_dir / "owid-population.csv"
    try:
        if not owid_path.exists() or owid_path.stat().st_size < 10000:
            log("Downloading population fallback from Our World in Data")
            r = requests.get(
                "https://ourworldindata.org/grapher/population.csv",
                timeout=300,
            )
            r.raise_for_status()
            owid_path.write_bytes(r.content)

        owid = pd.read_csv(owid_path)
        value_col = next(
            c for c in owid.columns if c not in {"Entity", "Code", "Year"}
        )
        sub = owid[
            (pd.to_numeric(owid["Year"], errors="coerce") == year)
            & owid["Code"].astype(str).str.fullmatch(r"[A-Z]{3}")
        ]
        for row in sub.to_dict("records"):
            iso = str(row.get("Code") or "").upper()
            value = row.get(value_col)
            if iso not in population and pd.notna(value):
                population[iso] = float(value)
    except Exception as exc:
        log(f"OWID population fallback failed: {exc}")

    year_file.write_text(json.dumps(population))
    return population


def region_population(year, regions, members):
    country_population = fetch_population(year)
    result, coverage = {}, {}

    for region in regions:
        if region in ROW_CODES:
            isos = members.get(region, [])
        else:
            try:
                isos = [pycountry.countries.get(alpha_2=region).alpha_3]
            except Exception:
                isos = []

        values = [
            country_population[iso]
            for iso in isos
            if iso in country_population
            and math.isfinite(country_population[iso])
            and country_population[iso] > 0
        ]
        result[region] = float(sum(values)) if values else math.nan
        coverage[region] = {
            "population_members_found": len(values),
            "population_members_total": len(isos),
        }
    return result, coverage


def region_gdp(A, x, sec_regions, regions):
    """
    Regional GDP from EXIOBASE value added:
    VA_j = x_j * (1 - sum_i A_ij).
    EXIOBASE monetary tables are stored in million EUR.
    """
    xv = np.asarray(x).reshape(-1).astype(float)
    input_share = np.asarray(A.sum(axis=0)).reshape(-1)
    va = xv * (1.0 - input_share) * 1e6
    return {
        region: float(va[sec_regions == region].sum())
        for region in regions
    }


def aggregate_direct_stressor(F, rows, ext, kind, sec_regions, regions):
    values = (
        F.iloc[rows, :].sum(axis=0).to_numpy(float)
        * scale_from_unit(unit_for(ext, rows[0]), kind)
    )
    return {
        region: float(values[sec_regions == region].sum())
        for region in regions
    }


def safe_ratio(numerator, denominator, multiplier=1.0):
    if denominator is None:
        return None
    try:
        d = float(denominator)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(d) or d == 0:
        return None
    return float(numerator) / d * multiplier

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

def north_south(hours, comp, regions, year, population, gdp, direct_hours):
    """North-South aggregates for every selectable skill grouping."""
    idx = {r: i for i, r in enumerate(regions)}
    north_regions = sorted(r for r in GLOBAL_NORTH if r in idx)
    south_regions = sorted(r for r in regions if r not in GLOBAL_NORTH)
    north = [idx[r] for r in north_regions]
    south = [idx[r] for r in south_regions]

    north_pop = sum(
        population.get(r, 0.0)
        for r in north_regions
        if population.get(r) is not None
        and math.isfinite(float(population.get(r)))
    )
    south_pop = sum(
        population.get(r, 0.0)
        for r in south_regions
        if population.get(r) is not None
        and math.isfinite(float(population.get(r)))
    )
    north_gdp = sum(float(gdp.get(r, 0.0)) for r in north_regions)
    south_gdp = sum(float(gdp.get(r, 0.0)) for r in south_regions)

    by_selection = {}

    for selection in ("low", "medium", "high", "all"):
        selected_skills = list(SKILLS) if selection == "all" else [selection]
        south_to_north = 0.0
        north_to_south = 0.0
        wage_value = 0.0
        by_skill = {}

        for skill in selected_skills:
            H = hours[skill]
            C = comp[skill]
            stn = float(H[np.ix_(south, north)].sum())
            nts = float(H[np.ix_(north, south)].sum())
            net = stn - nts

            north_export_hours = 0.0
            north_export_comp = 0.0
            for i in north:
                mask = np.ones(len(regions), bool)
                mask[i] = False
                north_export_hours += float(H[i, mask].sum())
                north_export_comp += float(C[i, mask].sum())

            north_wage = (
                north_export_comp / north_export_hours
                if north_export_hours > 0 else math.nan
            )
            skill_value = (
                net * north_wage
                if net > 0 and math.isfinite(north_wage) else 0.0
            )

            by_skill[skill] = {
                "south_to_north_hours": stn,
                "north_to_south_hours": nts,
                "net_north_appropriation_hours": net,
                "north_export_wage_eur_per_hour": (
                    north_wage if math.isfinite(north_wage) else None
                ),
                "wage_value_2005_eur": skill_value,
            }
            south_to_north += stn
            north_to_south += nts
            wage_value += skill_value

        net_hours = south_to_north - north_to_south
        north_direct = sum(
            direct_hours[sk].get(r, 0.0)
            for sk in selected_skills for r in north_regions
        )
        south_direct = sum(
            direct_hours[sk].get(r, 0.0)
            for sk in selected_skills for r in south_regions
        )

        by_selection[selection] = {
            "south_to_north_hours": south_to_north,
            "north_to_south_hours": north_to_south,
            "net_north_appropriation_hours": net_hours,
            "wage_value_2005_eur": wage_value,
            "north_population": north_pop,
            "south_population": south_pop,
            "north_gdp_eur_2005": north_gdp,
            "south_gdp_eur_2005": south_gdp,
            "north_net_hours_per_capita": safe_ratio(net_hours, north_pop),
            "south_net_hours_per_capita": safe_ratio(-net_hours, south_pop),
            "north_wage_value_per_capita_eur": safe_ratio(wage_value, north_pop),
            "south_wage_value_per_capita_eur": safe_ratio(-wage_value, south_pop),
            "wage_value_pct_north_gdp": safe_ratio(wage_value, north_gdp, 100.0),
            "wage_value_pct_south_gdp": safe_ratio(wage_value, south_gdp, 100.0),
            "net_hours_pct_north_domestic_labor": safe_ratio(net_hours, north_direct, 100.0),
            "net_hours_pct_south_domestic_labor": safe_ratio(-net_hours, south_direct, 100.0),
            "by_skill": by_skill,
        }

    return {
        "year": year,
        "by_selection": by_selection,
        "north_regions": north_regions,
        "south_regions": south_regions,
        "note": "Calculated directly from this atlas's EXIOBASE 3.8.2 build for the selected year.",
    }

def build(year,keep_raw=False):
    if not 1995<=year<=2022:raise ValueError("Use EXIOBASE years 1995-2022")
    archive=download_year(year)
    log(f"Parsing {archive.name}")
    io=pymrio.parse_exiobase3(str(archive))
    A=io.A;Y=io.Y;ext=extension(io);x=io.x.iloc[:,0].to_numpy(float)
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
    population,pop_coverage=region_population(year,regions,members)
    gdp=region_gdp(A,x,sec_regions,regions)
    direct_hours={}
    for sk in SKILLS:
        direct_hours[sk]=aggregate_direct_stressor(
            ext.F,rows[sk]["hours"],ext,"hours",sec_regions,regions
        )
    ydir=OUT/str(year);ydir.mkdir(parents=True,exist_ok=True)
    for sel in ["low","medium","high","all"]:
        if sel=="all":
            H=sum(hours.values());P=sum(people.values())
        else:H=hours[sel];P=people[sel]
        labrec=pairwise_net(H,regions);labsum=summary_net(labrec,regions);gh=gross(H,regions);gp=gross(P,regions)
        for r in regions:
            labsum[r].update(gh[r])
            labsum[r]["gross_imported_employment_equivalents"]=gp[r]["gross_imported"]
            labsum[r]["gross_exported_employment_equivalents"]=gp[r]["gross_exported"]
            labsum[r]["population"]=population.get(r)
            labsum[r]["population_coverage"]=pop_coverage.get(r,{})
            labsum[r]["gdp_eur_2005"]=gdp.get(r)
            selected_skills=list(SKILLS) if sel=="all" else [sel]
            region_direct_hours=sum(
                direct_hours[sk].get(r,0.0) for sk in selected_skills
            )
            labsum[r]["domestic_labor_hours"]=region_direct_hours
            labsum[r]["net_per_capita"]=safe_ratio(labsum[r]["net"],population.get(r))
            labsum[r]["net_pct_domestic_labor"]=safe_ratio(
                labsum[r]["net"],region_direct_hours,100.0
            )
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
        for r in regions:
            ws[r]["population"]=population.get(r)
            ws[r]["population_coverage"]=pop_coverage.get(r,{})
            ws[r]["gdp_eur_2005"]=gdp.get(r)
            ws[r]["net_per_capita"]=safe_ratio(ws[r]["net"],population.get(r))
            ws[r]["net_pct_gdp"]=safe_ratio(ws[r]["net"],gdp.get(r),100.0)
        wp={"year":year,"view":"wage_value","skill":sel,"unit":"constant_2005_EUR","regions":[{"code":r,"name":REGION_NAMES.get(r,r),"aggregate":r in ROW_CODES,"members":sorted(members.get(r,[])),**ws[r]} for r in regions],"bilateral":wr,"note":"Counterfactual wage value of pairwise net-appropriated labour, valued at the recipient region's same-skill export wage."}
        (ydir/f"labour_hours-{sel}.json").write_text(json.dumps(lp,separators=(",",":"),allow_nan=False))
        (ydir/f"wage_value-{sel}.json").write_text(json.dumps(wp,separators=(",",":"),allow_nan=False))
    ns=north_south(hours,comp,regions,year,population,gdp,direct_hours)
    (ydir/"north_south.json").write_text(json.dumps(ns,indent=2,allow_nan=False))
    manifest={"year":year,"exiobase_version":"3.8.2","exiobase_doi":DOI,"system":SYSTEM,"regions":regions,"region_names":{r:REGION_NAMES.get(r,r) for r in regions},"row_regions":sorted(ROW_CODES & set(regions)),"country_to_region":mapping,"geometry":geometry,"members":members,"global_north":sorted(GLOBAL_NORTH & set(regions)),"north_south":ns,"region_population":population,"region_gdp_eur_2005":gdp,"skills":["all","low","medium","high"],"views":["labour_hours","wage_value"]}
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
