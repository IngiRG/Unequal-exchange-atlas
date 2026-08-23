#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import os
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pycountry
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public/data"
CACHE = ROOT / "cache"
OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

OECD_BASE = "https://sdmx.oecd.org/public/rest/data/OECD.STI.PIE,DSD_TIM_2025@DF_TIM_2025,1.0"
OECD_QUERIES = {
    "ffd": "FFD_DEM.._T..PS.A",
    "employment": "EMPN.._T.W.PS.A",
    "compensation": "LABR.._T.W.USD.A",
}
OECD_YEARS = range(1995, 2023)

BACI_VERSION = os.getenv("BACI_VERSION") or "202601"
BACI_HS = os.getenv("BACI_HS") or "22"
BACI_URL = os.getenv("BACI_ARCHIVE_URL") or (
    f"https://www.cepii.fr/DATA_DOWNLOAD/baci/data/"
    f"BACI_HS{BACI_HS}_V{BACI_VERSION}.zip"
)
BACI_RANGES = {
    "92": range(1995, 2025),
    "96": range(1996, 2025),
    "02": range(2002, 2025),
    "07": range(2007, 2025),
    "12": range(2012, 2025),
    "17": range(2017, 2025),
    "22": range(2022, 2025),
}

WB = "https://api.worldbank.org/v2/country/all/indicator/{indicator}?format=json&per_page=20000&date={year}"
GDP = "NY.GDP.MKTP.CD"
GDP_EMP = "SL.GDP.PCAP.EM.KD"

SOURCES = {
    "oecd_tim": {
        "name": "OECD Trade in Employment (TiM), 2025 edition",
        "url": "https://www.oecd.org/en/data/datasets/trade-in-employment.html",
        "api": "https://sdmx.oecd.org/public/rest/",
        "coverage": "1995-2022; bilateral counterpart economies; 50 industries",
        "attribution": "OECD, Trade in Employment (TiM), 2025 edition.",
    },
    "baci": {
        "name": "CEPII BACI",
        "url": "https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37",
        "version": BACI_VERSION,
        "hs_revision": BACI_HS,
        "license": "Etalab Open Licence 2.0",
        "attribution": "CEPII, BACI; Gaulier and Zignago (2010).",
    },
    "world_bank": {
        "name": "World Bank Open Data",
        "url": "https://data.worldbank.org/",
        "attribution": "World Bank Open Data.",
    },
}

METHODS = {
    "emmanuel_wage": {
        "name": "Emmanuel bilateral wage counterfactual",
        "source": ["oecd_tim"],
        "unit": "current USD/year",
        "formula": "UE_i→j = H_i→j (w_j - w_i)",
    },
    "wage_equalisation": {
        "name": "Common-wage equalisation",
        "source": ["oecd_tim"],
        "unit": "current USD/year",
        "formula": "UE_i→j = H_i→j (w* - w_i)",
    },
    "embodied_labour": {
        "name": "Embodied employment transfer",
        "source": ["oecd_tim"],
        "unit": "persons",
        "formula": "H_i→j = ê B FD_j",
    },
    "labour_terms": {
        "name": "Labour terms of exchange",
        "source": ["oecd_tim"],
        "unit": "persons",
        "formula": "ΔH_i = Σ_j H_j→i - Σ_j H_i→j",
    },
    "goods_wage_proxy": {
        "name": "Broad goods productivity proxy",
        "source": ["baci", "world_bank"],
        "unit": "current USD estimate",
        "formula": "UE_i→j = X_i→j (p_j/p_i - 1)",
    },
}


def log(msg: str) -> None:
    print(msg, flush=True)


def request(url: str, **kwargs):
    if not url or not str(url).startswith(("http://", "https://")):
        raise RuntimeError(f"Invalid URL: {url!r}")
    r = requests.get(url, **kwargs)
    r.raise_for_status()
    return r


def get_csv(url: str, cache: Path) -> pd.DataFrame:
    if cache.exists() and cache.stat().st_size > 100:
        return pd.read_csv(cache)
    cache.parent.mkdir(parents=True, exist_ok=True)
    log("GET " + url)
    r = request(url, headers={"Accept": "text/csv;version=2"}, timeout=600)
    cache.write_bytes(r.content)
    return pd.read_csv(io.BytesIO(r.content))


def oecd_table(kind: str, start: int, end: int) -> pd.DataFrame:
    q = OECD_QUERIES[kind]
    url = f"{OECD_BASE}/{q}?startPeriod={start}&endPeriod={end}&dimensionAtObservation=AllDimensions"
    return get_csv(url, CACHE/"oecd"/f"{kind}-{start}-{end}.csv")


def col(df: pd.DataFrame, *names: str):
    m = {str(c).upper(): c for c in df.columns}
    for n in names:
        if n.upper() in m:
            return m[n.upper()]
    raise RuntimeError(f"Missing column {names}; got {list(df.columns)}")


def normalized_value(df: pd.DataFrame) -> pd.Series:
    v = pd.to_numeric(df[col(df, "OBS_VALUE")], errors="coerce")
    try:
        mult = pd.to_numeric(df[col(df, "UNIT_MULT")], errors="coerce").fillna(0)
    except RuntimeError:
        mult = pd.Series(0, index=df.index)
    return v * np.power(10.0, mult)


def oecd_inputs(start: int, end: int):
    raw = {
        k: oecd_table(k, start, end)
        for k in ("ffd", "employment", "compensation")
    }

    def tidy(df: pd.DataFrame) -> pd.DataFrame:
        o = pd.DataFrame({
            "iso": df[col(df, "REF_AREA")].astype(str),
            "activity": df[col(df, "ACTIVITY", "ECONOMIC_ACTIVITY")].astype(str),
            "year": pd.to_numeric(df[col(df, "TIME_PERIOD")], errors="coerce"),
            "value": normalized_value(df),
        })
        if "COUNTERPART_AREA" in {str(c).upper() for c in df.columns}:
            o["partner"] = df[col(df, "COUNTERPART_AREA")].astype(str)
        return o

    F, E, C = (tidy(raw[k]) for k in ("ffd", "employment", "compensation"))
    total = lambda s: s.eq("_T") | s.str.upper().isin(["TOTAL", "T"])
    F, E, C = F[total(F.activity)], E[total(E.activity)], C[total(C.activity)]

    valid = lambda s: s.str.fullmatch(r"[A-Z]{3}") & ~s.isin(["WLD"])
    F = F[valid(F.iso) & valid(F.partner) & F.iso.ne(F.partner)].copy()
    E, C = E[valid(E.iso)].copy(), C[valid(C.iso)].copy()

    E = E.groupby(["iso", "year"], as_index=False).value.sum()
    C = C.groupby(["iso", "year"], as_index=False).value.sum()
    W = E.merge(C, on=["iso", "year"], suffixes=("_emp", "_comp"))
    W["wage"] = np.divide(
        W.value_comp, W.value_emp,
        out=np.full(len(W), np.nan),
        where=W.value_emp.to_numpy() != 0
    )
    F = F.groupby(["iso", "partner", "year"], as_index=False).value.sum()
    return F, W


def wb(indicator: str, year: int) -> dict[str, float]:
    r = request(WB.format(indicator=indicator, year=year), timeout=180)
    payload = r.json()
    rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    out = {}
    for x in rows:
        iso = (x.get("countryiso3code") or "").upper()
        if re.fullmatch(r"[A-Z]{3}", iso) and x.get("value") is not None:
            out[iso] = float(x["value"])
    return out


def country_names():
    return {c.alpha_3: getattr(c, "common_name", c.name) for c in pycountry.countries}


def aggregate(flows, year, method, gdp, names, provenance):
    flows = flows.copy()
    flows["value"] = pd.to_numeric(flows["value"], errors="coerce")
    flows = flows[
        flows["from"].ne(flows["to"]) &
        np.isfinite(flows["value"])
    ]
    incoming = flows.groupby("to").value.sum()
    outgoing = flows.groupby("from").value.sum()
    rows = []
    for iso in sorted(set(incoming.index) | set(outgoing.index)):
        inn, out = float(incoming.get(iso, 0)), float(outgoing.get(iso, 0))
        net = inn - out
        gv = gdp.get(iso)
        rows.append({
            "iso3": iso,
            "name": names.get(iso, iso),
            "inflow": inn,
            "outflow": out,
            "net": net,
            "gdp_share": (
                100 * net / gv
                if gv and method not in {"embodied_labour", "labour_terms"}
                else None
            ),
        })
    payload = {
        "countries": rows,
        "bilateral": flows[["from", "to", "value"]].to_dict("records"),
        "year": year,
        "method": method,
        "provenance": provenance,
        "model_derived": True,
    }
    (OUT/f"{method}-{year}.json").write_text(
        json.dumps(payload, separators=(",", ":"), allow_nan=False)
    )


def build_oecd(start: int, end: int):
    F, W = oecd_inputs(start, end)
    names = country_names()
    years = {k: [] for k in (
        "emmanuel_wage", "wage_equalisation",
        "embodied_labour", "labour_terms"
    )}

    for year in range(start, end + 1):
        fy, wy = F[F.year.eq(year)].copy(), W[W.year.eq(year)].copy()
        if fy.empty or wy.empty:
            continue

        wages = dict(zip(wy.iso, wy.wage))
        employment = dict(zip(wy.iso, wy.value_emp))
        fy = fy[
            fy.iso.isin(wages) &
            fy.partner.isin(wages) &
            fy.value.gt(0)
        ].copy()
        if fy.empty:
            continue

        gdp = wb(GDP, year)
        base = fy.rename(columns={"iso": "from", "partner": "to"})[
            ["from", "to", "value"]
        ]
        prov = {
            "source": "OECD TiM 2025",
            "measure": "FFD_DEM",
            "year": year,
        }

        aggregate(base, year, "embodied_labour", gdp, names, prov)
        aggregate(base, year, "labour_terms", gdp, names, prov)
        years["embodied_labour"].append(year)
        years["labour_terms"].append(year)

        em = fy.rename(columns={"iso": "from", "partner": "to"})
        em["value"] = em.apply(
            lambda r: r["value"] * (wages[r["to"]] - wages[r["from"]]),
            axis=1
        )
        aggregate(
            em, year, "emmanuel_wage", gdp, names,
            prov | {"counterfactual": "consumer-country compensation per worker"}
        )
        years["emmanuel_wage"].append(year)

        usable = [
            i for i in wages
            if np.isfinite(wages[i]) and employment.get(i, 0) > 0
        ]
        denom = sum(employment[i] for i in usable)
        if denom <= 0:
            raise RuntimeError(f"Cannot calculate reference wage for {year}")
        wstar = sum(employment[i] * wages[i] for i in usable) / denom

        eq = fy.rename(columns={"iso": "from", "partner": "to"})
        eq["value"] = eq.apply(
            lambda r: r["value"] * (wstar - wages[r["from"]]),
            axis=1
        )
        aggregate(
            eq, year, "wage_equalisation", gdp, names,
            prov | {"reference_wage": float(wstar)}
        )
        years["wage_equalisation"].append(year)

        log(f"Built OECD layers {year}: {len(fy):,} bilateral observations")

    return years


def download(url: str, path: Path) -> Path:
    if path.exists() and path.stat().st_size > 100:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    log("GET " + url)
    try:
        with request(url, stream=True, timeout=1800) as r:
            with part.open("wb") as f:
                for chunk in r.iter_content(1024 * 1024):
                    if chunk:
                        f.write(chunk)
        part.replace(path)
    except Exception:
        if part.exists():
            part.unlink()
        raise
    return path


def baci_codes(z: zipfile.ZipFile):
    # Prefer metadata bundled in the BACI archive.
    for name in z.namelist():
        if name.lower().endswith(".csv") and "country" in name.lower():
            d = pd.read_csv(z.open(name))
            code = next((c for c in d.columns if "country_code" in str(c).lower()), None)
            iso = next((c for c in d.columns if "iso" in str(c).lower()), None)
            if code and iso:
                d[code] = pd.to_numeric(d[code], errors="coerce")
                d[iso] = d[iso].astype(str).str.upper()
                q = d[d[code].notna() & d[iso].str.fullmatch(r"[A-Z]{3}")]
                if len(q) > 100:
                    return dict(zip(q[code].astype(int), q[iso]))

    # Fallback: BACI country codes overwhelmingly use ISO numeric identifiers.
    result = {}
    for c in pycountry.countries:
        if getattr(c, "numeric", None):
            result[int(c.numeric)] = c.alpha_3
    if len(result) < 150:
        raise RuntimeError("Could not construct BACI country mapping")
    return result


def build_baci(requested_years):
    legal = set(BACI_RANGES.get(BACI_HS, []))
    requested_years = [y for y in requested_years if y in legal]
    if not requested_years:
        log(f"No requested years are valid for BACI HS{BACI_HS}")
        return []

    archive = download(
        BACI_URL,
        CACHE/"baci"/f"BACI_HS{BACI_HS}_V{BACI_VERSION}.zip"
    )
    names = country_names()
    built = []

    with zipfile.ZipFile(archive) as z:
        codes = baci_codes(z)

        for year in requested_years:
            pattern = re.compile(
                rf"BACI_HS{re.escape(BACI_HS)}_Y{year}_V{re.escape(BACI_VERSION)}\.csv$",
                re.I
            )
            member = next(
                (n for n in z.namelist() if pattern.search(Path(n).name)),
                None
            )
            if not member:
                log(f"BACI {year} not found in archive; skipping")
                continue

            totals = {}
            for chunk in pd.read_csv(
                z.open(member),
                usecols=["i", "j", "v"],
                chunksize=600_000
            ):
                grouped = chunk.groupby(["i", "j"]).v.sum()
                for key, value in grouped.items():
                    totals[key] = totals.get(key, 0.0) + float(value)

            trade = pd.DataFrame(
                [
                    (codes.get(int(i)), codes.get(int(j)), value * 1000)
                    for (i, j), value in totals.items()
                ],
                columns=["from", "to", "trade"]
            ).dropna()

            productivity, gdp = wb(GDP_EMP, year), wb(GDP, year)
            trade["pi"] = trade["from"].map(productivity)
            trade["pj"] = trade["to"].map(productivity)
            trade = trade[
                (trade.pi > 0) & (trade.pj > 0) &
                trade["from"].ne(trade["to"])
            ].copy()
            trade["value"] = trade.trade * (trade.pj / trade.pi - 1)

            aggregate(
                trade, year, "goods_wage_proxy", gdp, names,
                {
                    "source": f"CEPII BACI HS{BACI_HS} V{BACI_VERSION} + World Bank",
                    "warning": "Goods-only productivity proxy; not an MRIO labour-transfer measure.",
                }
            )
            built.append(year)
            log(f"Built BACI proxy {year}: {len(trade):,} bilateral observations")

    return built


def geometry_ids():
    return [
        {"id": str(c.numeric).zfill(3), "iso3": c.alpha_3}
        for c in pycountry.countries
        if getattr(c, "numeric", None)
    ]


def parse_years(items):
    years = []
    for item in items:
        if ":" in item:
            a, b = map(int, item.split(":"))
            years.extend(range(a, b + 1))
        else:
            years.append(int(item))
    return sorted(set(years))


def read_existing_method_years():
    p = OUT/"meta.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text()).get("method_years", {})
    except Exception:
        return {}


def write_meta(method_years):
    method_years = {
        k: sorted(set(v))
        for k, v in method_years.items()
        if v
    }
    all_years = sorted({
        year for years in method_years.values() for year in years
    })
    meta = {
        "mode": "derived-real-open-data",
        "years": all_years,
        "method_years": method_years,
        "available_methods": list(method_years),
        "country_ids": geometry_ids(),
        "sources": SOURCES,
        "methods": {k: METHODS[k] for k in method_years},
        "generated_by": "scripts/build_data.py",
        "eora_used": False,
    }
    (OUT/"meta.json").write_text(
        json.dumps(meta, separators=(",", ":"), allow_nan=False)
    )
    (OUT/"sources.json").write_text(json.dumps(SOURCES, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["oecd", "baci", "all"], default="all")
    ap.add_argument("--years", nargs="+", default=["1995:2022"])
    args = ap.parse_args()

    requested = parse_years(args.years)
    combined = read_existing_method_years()

    if args.mode in {"oecd", "all"}:
        oy = [y for y in requested if y in OECD_YEARS]
        if oy:
            new = build_oecd(min(oy), max(oy))
            for method, years in new.items():
                combined[method] = sorted(set(combined.get(method, [])) | set(years))

    if args.mode in {"baci", "all"}:
        years = build_baci(requested)
        if years:
            combined["goods_wage_proxy"] = sorted(
                set(combined.get("goods_wage_proxy", [])) | set(years)
            )

    write_meta(combined)

    if not combined:
        raise RuntimeError("No data were generated")

    log("Done. Open-data atlas files and provenance written to public/data.")


if __name__ == "__main__":
    main()
