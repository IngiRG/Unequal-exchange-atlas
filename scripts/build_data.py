#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import re
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

START_YEAR = 2005
END_YEAR = 2022

TIM_BASE = (
    "https://sdmx.oecd.org/public/rest/data/"
    "OECD.STI.PIE,DSD_TIM_2025@DF_TIM_2025,1.0"
)
TIM_QUERY = "FFD_DEM.._T..PS.A"

BIMTS_BASE = (
    "https://sdmx.oecd.org/public/rest/data/"
    "OECD.SDD.TPS,DSD_BIMTS@DF_BIMTS_CPA_2_1,1.1"
)
# Official Data Explorer API pattern: all reporters/counterparts,
# balanced adjustment, total merchandise, annual current USD.
BIMTS_QUERY = "...C._T..A.USD_EXC."

ILO_ENDPOINT = "https://rplumber.ilo.org/data/indicator/"
ILO_EMPLOYMENT = "EMP_2EMP_SEX_AGE_NB_A"
ILO_LABOUR_SHARE = "LAP_2GDP_NOC_RT_A"

WB_API = "https://api.worldbank.org/v2"
WB_GDP = "NY.GDP.MKTP.CD"
WB_EXPORTS = "NE.EXP.GNFS.CD"

UA = {"User-Agent": "Unequal-Exchange-Atlas/2.0"}

SOURCES = {
    "oecd_tim": {
        "name": "OECD Trade in Employment (TiM), 2025 edition",
        "url": "https://www.oecd.org/en/data/datasets/trade-in-employment.html",
        "role": "MRIO-backed bilateral embodied employment",
    },
    "oecd_bimts": {
        "name": "OECD Balanced International Merchandise Trade Statistics (BIMTS)",
        "url": "https://www.oecd.org/en/data/datasets/oecd-balanced-trade-statistics.html",
        "role": "Bilateral partner allocation for the global extension",
    },
    "ilostat": {
        "name": "ILOSTAT modelled estimates",
        "url": "https://ilostat.ilo.org/",
        "role": "Employment and labour-income share",
    },
    "world_bank": {
        "name": "World Development Indicators",
        "url": "https://datacatalog.worldbank.org/search/dataset/0037712/world-development-indicators",
        "role": "Current-USD GDP and exports of goods and services",
    },
}


def log(message: str) -> None:
    print(message, flush=True)


def find_col(df: pd.DataFrame, *names: str):
    cols = {str(c).upper(): c for c in df.columns}
    for name in names:
        if name.upper() in cols:
            return cols[name.upper()]
    raise RuntimeError(f"Missing expected column {names}. Received {list(df.columns)}")


def cached_csv(url: str, path: Path, *, oecd=False, timeout=1200) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 100:
        return pd.read_csv(path)

    headers = dict(UA)
    if oecd:
        headers["Accept"] = "text/csv;version=2"

    log(f"GET {url}")
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    path.write_bytes(response.content)
    return pd.read_csv(io.BytesIO(response.content))


def oecd_value(df: pd.DataFrame) -> pd.Series:
    values = pd.to_numeric(df[find_col(df, "OBS_VALUE")], errors="coerce")
    try:
        multiplier = pd.to_numeric(
            df[find_col(df, "UNIT_MULT")], errors="coerce"
        ).fillna(0)
    except RuntimeError:
        multiplier = pd.Series(0, index=df.index)
    return values * np.power(10.0, multiplier)


def fetch_tim(start: int, end: int) -> pd.DataFrame:
    url = (
        f"{TIM_BASE}/{TIM_QUERY}"
        f"?startPeriod={start}&endPeriod={end}"
        "&dimensionAtObservation=AllDimensions"
    )
    raw = cached_csv(
        url,
        CACHE / "oecd" / f"tim-{start}-{end}.csv",
        oecd=True,
    )
    out = pd.DataFrame(
        {
            "from": raw[find_col(raw, "REF_AREA")].astype(str).str.upper(),
            "to": raw[find_col(raw, "COUNTERPART_AREA")].astype(str).str.upper(),
            "year": pd.to_numeric(
                raw[find_col(raw, "TIME_PERIOD")], errors="coerce"
            ),
            "value": oecd_value(raw),
        }
    )
    mask = (
        out["from"].str.fullmatch(r"[A-Z]{3}")
        & out["to"].str.fullmatch(r"[A-Z]{3}")
        & out["from"].ne(out["to"])
        & out["value"].gt(0)
    )
    return (
        out[mask]
        .groupby(["from", "to", "year"], as_index=False)
        .value.sum()
    )


def fetch_bimts(start: int, end: int) -> pd.DataFrame:
    url = (
        f"{BIMTS_BASE}/{BIMTS_QUERY}"
        f"?startPeriod={start}&endPeriod={end}"
        "&dimensionAtObservation=AllDimensions"
    )
    raw = cached_csv(
        url,
        CACHE / "oecd" / f"bimts-{start}-{end}.csv",
        oecd=True,
        timeout=1800,
    )
    out = pd.DataFrame(
        {
            "from": raw[find_col(raw, "REF_AREA")].astype(str).str.upper(),
            "to": raw[find_col(raw, "COUNTERPART_AREA")].astype(str).str.upper(),
            "year": pd.to_numeric(
                raw[find_col(raw, "TIME_PERIOD")], errors="coerce"
            ),
            "value": oecd_value(raw),
        }
    )
    mask = (
        out["from"].str.fullmatch(r"[A-Z]{3}")
        & out["to"].str.fullmatch(r"[A-Z]{3}")
        & out["from"].ne(out["to"])
        & out["value"].gt(0)
    )
    return (
        out[mask]
        .groupby(["from", "to", "year"], as_index=False)
        .value.sum()
    )


def fetch_ilo(indicator: str, start: int, end: int, extra=None) -> pd.DataFrame:
    path = CACHE / "ilo" / f"{indicator}-{start}-{end}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 100:
        return pd.read_csv(path)

    params = {
        "id": indicator,
        "lang": "en",
        "type": "both",
        "format": ".csv",
        "timefrom": str(start),
        "timeto": str(end),
    }
    if extra:
        params.update(extra)

    log(f"GET ILOSTAT {indicator}")
    response = requests.get(
        ILO_ENDPOINT,
        params=params,
        headers=UA,
        timeout=900,
    )
    response.raise_for_status()
    path.write_bytes(response.content)
    return pd.read_csv(io.BytesIO(response.content))


def tidy_ilo(start: int, end: int):
    employment_raw = fetch_ilo(
        ILO_EMPLOYMENT,
        start,
        end,
        {
            "sex": "SEX_T",
            "classif1": "AGE_YTHADULT_YGE15",
        },
    )
    labour_share_raw = fetch_ilo(ILO_LABOUR_SHARE, start, end)

    def standard(df: pd.DataFrame):
        return pd.DataFrame(
            {
                "iso": df[find_col(df, "ref_area")].astype(str).str.upper(),
                "year": pd.to_numeric(
                    df[find_col(df, "time")], errors="coerce"
                ),
                "value": pd.to_numeric(
                    df[find_col(df, "obs_value")], errors="coerce"
                ),
            }
        )

    emp = standard(employment_raw)
    emp = emp[
        emp.iso.str.fullmatch(r"[A-Z]{3}")
        & emp.year.notna()
        & emp.value.notna()
    ].copy()
    # ILO modelled employment is in thousands.
    emp["employment"] = emp["value"] * 1000.0
    emp = (
        emp.groupby(["iso", "year"], as_index=False)
        .employment.mean()
    )

    share = standard(labour_share_raw)
    share = share[
        share.iso.str.fullmatch(r"[A-Z]{3}")
        & share.year.notna()
        & share.value.notna()
    ].copy()
    share["labour_share"] = share["value"]
    share = (
        share.groupby(["iso", "year"], as_index=False)
        .labour_share.mean()
    )
    return emp, share


def wb_indicator(indicator: str, start: int, end: int) -> pd.DataFrame:
    """
    Fetch a World Development Indicators series with pagination.

    The World Bank API can reject very large per_page values. We therefore use
    a conservative page size and follow the API's reported page count.
    """
    path = CACHE / "worldbank" / f"{indicator}-{start}-{end}.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        rows = json.loads(path.read_text())
    else:
        rows = []
        page = 1
        pages = 1

        while page <= pages:
            url = (
                f"{WB_API}/country/all/indicator/{indicator}"
                f"?format=json&per_page=1000"
                f"&page={page}"
                f"&date={start}:{end}"
            )

            log(
                f"GET World Bank {indicator} "
                f"page {page}/{pages if pages > 1 else '?'}"
            )

            response = requests.get(
                url,
                headers=UA,
                timeout=600,
            )
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, list) or len(payload) < 2:
                raise RuntimeError(
                    f"Unexpected World Bank API response for {indicator}"
                )

            metadata = payload[0] or {}
            page_rows = payload[1] or []

            rows.extend(page_rows)

            try:
                pages = int(metadata.get("pages", 1))
            except (TypeError, ValueError):
                pages = 1

            page += 1

        path.write_text(json.dumps(rows))

    output = []

    for item in rows:
        iso = str(item.get("countryiso3code") or "").upper()
        value = item.get("value")
        year = item.get("date")

        if not re.fullmatch(r"[A-Z]{3}", iso):
            continue
        if value is None:
            continue

        try:
            output.append(
                (iso, int(year), float(value))
            )
        except (TypeError, ValueError):
            continue

    return pd.DataFrame(
        output,
        columns=["iso", "year", "value"],
    )


def wb_regions() -> dict[str, str]:
    path = CACHE / "worldbank" / "countries.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        payload = json.loads(path.read_text())
    else:
        response = requests.get(
            f"{WB_API}/country?format=json&per_page=400",
            headers=UA,
            timeout=300,
        )
        response.raise_for_status()
        payload = response.json()
        path.write_text(json.dumps(payload))

    rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    result = {}

    for item in rows:
        iso = str(item.get("id") or "").upper()
        region = (item.get("region") or {}).get("id")
        if (
            re.fullmatch(r"[A-Z]{3}", iso)
            and region
            and region != "NA"
        ):
            result[iso] = region

    return result


def build_macro(start: int, end: int) -> pd.DataFrame:
    employment, labour_share = tidy_ilo(start, end)
    gdp = wb_indicator(WB_GDP, start, end).rename(columns={"value": "gdp"})
    exports = wb_indicator(WB_EXPORTS, start, end).rename(
        columns={"value": "exports"}
    )

    macro = (
        employment
        .merge(labour_share, on=["iso", "year"], how="inner")
        .merge(gdp, on=["iso", "year"], how="inner")
        .merge(exports, on=["iso", "year"], how="inner")
    )

    macro = macro[
        (macro.employment > 0)
        & (macro.gdp > 0)
        & (macro.exports >= 0)
        & (macro.labour_share > 0)
        & (macro.labour_share < 100)
    ].copy()

    macro["wage"] = (
        macro.labour_share / 100.0
        * macro.gdp
        / macro.employment
    )
    macro["direct_export_employment"] = (
        macro.employment
        * macro.exports
        / macro.gdp
    )
    return macro


def country_names() -> dict[str, str]:
    return {
        c.alpha_3: getattr(c, "common_name", c.name)
        for c in pycountry.countries
    }


def geometry_ids():
    return [
        {"id": str(c.numeric).zfill(3), "iso3": c.alpha_3}
        for c in pycountry.countries
        if getattr(c, "numeric", None)
    ]


def calibration(
    core_year: pd.DataFrame,
    macro_year: pd.DataFrame,
    regions: dict[str, str],
):
    core_total = core_year.groupby("from").value.sum()

    overlap = macro_year.copy()
    overlap["tim"] = overlap.iso.map(core_total)
    overlap = overlap[
        (overlap.tim > 0)
        & (overlap.direct_export_employment > 0)
    ].copy()

    if overlap.empty:
        return {}, 1.0, {}

    overlap["raw_multiplier"] = (
        overlap.tim / overlap.direct_export_employment
    )

    lo = max(float(overlap.raw_multiplier.quantile(0.05)), 0.05)
    hi = max(float(overlap.raw_multiplier.quantile(0.95)), lo)
    overlap["multiplier"] = overlap.raw_multiplier.clip(lo, hi)
    overlap["region"] = overlap.iso.map(regions)

    global_median = float(overlap.multiplier.median())
    regional = (
        overlap.dropna(subset=["region"])
        .groupby("region")
        .multiplier.median()
        .to_dict()
    )
    country = dict(zip(overlap.iso, overlap.multiplier))
    return regional, global_median, country


def best_available_labour(
    year: int,
    core: pd.DataFrame,
    trade: pd.DataFrame,
    macro: pd.DataFrame,
    regions: dict[str, str],
) -> pd.DataFrame:
    core_year = core[core.year.eq(year)].copy()
    trade_year = trade[trade.year.eq(year)].copy()
    macro_year = macro[macro.year.eq(year)].copy()

    regional, global_mult, country_mult = calibration(
        core_year, macro_year, regions
    )

    macro_map = macro_year.set_index("iso").to_dict("index")
    exact_pairs = set(zip(core_year["from"], core_year["to"]))
    exact_out = core_year.groupby("from").value.sum().to_dict()

    rows = []

    for row in core_year.to_dict("records"):
        rows.append(
            {
                "from": row["from"],
                "to": row["to"],
                "value": float(row["value"]),
                "quality": "mrio",
            }
        )

    for exporter, group in trade_year.groupby("from"):
        macro_row = macro_map.get(exporter)
        if not macro_row:
            continue

        region = regions.get(exporter)
        multiplier = country_mult.get(
            exporter,
            regional.get(region, global_mult),
        )
        if not np.isfinite(multiplier) or multiplier <= 0:
            multiplier = global_mult

        target = (
            float(macro_row["direct_export_employment"])
            * float(multiplier)
        )
        residual = max(
            target - float(exact_out.get(exporter, 0.0)),
            0.0,
        )
        if residual <= 0:
            continue

        remaining = group[
            ~group.apply(
                lambda r: (r["from"], r["to"]) in exact_pairs,
                axis=1,
            )
        ].copy()

        if remaining.empty:
            continue

        denominator = float(remaining.value.sum())
        if denominator <= 0:
            continue

        for row in remaining.to_dict("records"):
            value = residual * float(row["value"]) / denominator
            if value > 0:
                rows.append(
                    {
                        "from": exporter,
                        "to": row["to"],
                        "value": value,
                        "quality": "extended",
                    }
                )

    result = pd.DataFrame(rows)
    if result.empty:
        return pd.DataFrame(
            columns=["from", "to", "value", "quality"]
        )

    result = result[
        result["from"].str.fullmatch(r"[A-Z]{3}")
        & result["to"].str.fullmatch(r"[A-Z]{3}")
        & result["from"].ne(result["to"])
        & result.value.gt(0)
    ].copy()

    return (
        result.groupby(
            ["from", "to", "quality"],
            as_index=False,
        ).value.sum()
    )


def monetary_edges(
    labour: pd.DataFrame,
    wages: dict[str, float],
) -> pd.DataFrame:
    rows = []

    for row in labour.to_dict("records"):
        source = row["from"]
        target = row["to"]
        wi = wages.get(source)
        wj = wages.get(target)

        if (
            wi is None
            or wj is None
            or not np.isfinite(wi)
            or not np.isfinite(wj)
        ):
            continue

        signed = float(row["value"]) * (float(wj) - float(wi))

        if signed > 0:
            rows.append(
                {
                    "from": source,
                    "to": target,
                    "value": signed,
                    "quality": row["quality"],
                }
            )
        elif signed < 0:
            rows.append(
                {
                    "from": target,
                    "to": source,
                    "value": -signed,
                    "quality": row["quality"],
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=["from", "to", "value", "quality"]
        )

    return (
        pd.DataFrame(rows)
        .groupby(
            ["from", "to", "quality"],
            as_index=False,
        ).value.sum()
    )


def country_rows(
    flows: pd.DataFrame,
    names: dict[str, str],
) -> list[dict]:
    inflow = flows.groupby("to").value.sum()
    outflow = flows.groupby("from").value.sum()
    countries = sorted(set(inflow.index) | set(outflow.index))

    incident_total = {}
    incident_mrio = {}

    for row in flows.to_dict("records"):
        for iso in (row["from"], row["to"]):
            incident_total[iso] = (
                incident_total.get(iso, 0.0)
                + float(row["value"])
            )
            if row["quality"] == "mrio":
                incident_mrio[iso] = (
                    incident_mrio.get(iso, 0.0)
                    + float(row["value"])
                )

    output = []

    for iso in countries:
        incoming = float(inflow.get(iso, 0))
        outgoing = float(outflow.get(iso, 0))
        denominator = incident_total.get(iso, 0.0)
        mrio_share = (
            incident_mrio.get(iso, 0.0) / denominator
            if denominator
            else 0.0
        )

        if mrio_share >= 0.80:
            tier = "mrio"
        elif mrio_share >= 0.20:
            tier = "mixed"
        else:
            tier = "extended"

        output.append(
            {
                "iso3": iso,
                "name": names.get(iso, iso),
                "inflow": incoming,
                "outflow": outgoing,
                "net": incoming - outgoing,
                "mrio_share": mrio_share,
                "coverage_tier": tier,
            }
        )

    return output


def write_view(
    view: str,
    year: int,
    flows: pd.DataFrame,
    names: dict[str, str],
    provenance: dict,
) -> None:
    payload = {
        "year": year,
        "view": view,
        "model_derived": True,
        "countries": country_rows(flows, names),
        "bilateral": flows[
            ["from", "to", "value", "quality"]
        ].to_dict("records"),
        "provenance": provenance,
    }
    (OUT / f"{view}-{year}.json").write_text(
        json.dumps(
            payload,
            separators=(",", ":"),
            allow_nan=False,
        )
    )


def clean_outputs() -> None:
    for path in OUT.glob("*.json"):
        path.unlink()


def parse_years(tokens: list[str]) -> list[int]:
    years = []
    for token in tokens:
        if ":" in token:
            start, end = map(int, token.split(":"))
            years.extend(range(start, end + 1))
        else:
            years.append(int(token))
    return sorted(
        set(
            y for y in years
            if START_YEAR <= y <= END_YEAR
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--years",
        nargs="+",
        default=[f"{START_YEAR}:{END_YEAR}"],
    )
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    years = parse_years(args.years)
    if not years:
        raise SystemExit(
            f"Choose years within {START_YEAR}-{END_YEAR}"
        )

    if args.clean:
        clean_outputs()

    start, end = min(years), max(years)

    core = fetch_tim(start, end)
    trade = fetch_bimts(start, end)
    macro = build_macro(start, end)
    regions = wb_regions()
    names = country_names()

    view_years = {
        "labour_transfer": [],
        "monetary_transfer": [],
    }
    quality_by_year = {}

    for year in years:
        labour = best_available_labour(
            year,
            core,
            trade,
            macro,
            regions,
        )
        if labour.empty:
            log(f"Skip {year}: no labour flows")
            continue

        macro_year = macro[macro.year.eq(year)]
        wages = dict(zip(macro_year.iso, macro_year.wage))
        money = monetary_edges(labour, wages)

        write_view(
            "labour_transfer",
            year,
            labour,
            names,
            {
                "method": "best-available embodied employment",
                "mrio_source": "OECD TiM",
                "extension_sources": [
                    "OECD BIMTS",
                    "ILOSTAT",
                    "World Development Indicators",
                ],
                "extension_formula": (
                    "E_i*(Exports_i/GDP_i)*"
                    "regional_calibration*"
                    "bilateral_merchandise_share_ij"
                ),
            },
        )
        view_years["labour_transfer"].append(year)

        if not money.empty:
            write_view(
                "monetary_transfer",
                year,
                money,
                names,
                {
                    "method": (
                        "Emmanuel-inspired labour-income "
                        "counterfactual"
                    ),
                    "formula": "UE_i→j=H_i→j*(w_j-w_i)",
                    "wage_formula": (
                        "w_i=labour_income_share_i*"
                        "GDP_i/employment_i"
                    ),
                },
            )
            view_years["monetary_transfer"].append(year)

        total = float(labour.value.sum())
        exact = float(
            labour.loc[
                labour.quality.eq("mrio"),
                "value",
            ].sum()
        )
        countries = set(labour["from"]) | set(labour["to"])

        quality_by_year[str(year)] = {
            "mrio_weighted_share": (
                exact / total if total else 0.0
            ),
            "countries": len(countries),
            "bilateral_flows": len(labour),
        }

        log(
            f"{year}: {len(countries)} countries, "
            f"{len(labour)} flows, "
            f"{quality_by_year[str(year)]['mrio_weighted_share']*100:.1f}% "
            "weighted MRIO-backed"
        )

    all_years = sorted(
        set(
            view_years["labour_transfer"]
            + view_years["monetary_transfer"]
        )
    )
    if not all_years:
        raise RuntimeError("No output years generated.")

    meta = {
        "mode": "best-available-global",
        "years": all_years,
        "view_years": view_years,
        "available_views": [
            "monetary_transfer",
            "labour_transfer",
        ],
        "country_ids": geometry_ids(),
        "sources": SOURCES,
        "quality_by_year": quality_by_year,
        "methodology": {
            "single_method": True,
            "core": "OECD TiM embodied employment",
            "extension": (
                "Calibrated export-linked employment "
                "allocated by OECD BIMTS partner shares"
            ),
            "monetary": (
                "H_i→j*(w_j-w_i), with ILO labour-income "
                "share and WDI GDP/employment"
            ),
        },
        "eora_used": False,
        "gloria_used": False,
        "adb_mrio_used": False,
    }

    (OUT / "meta.json").write_text(
        json.dumps(meta, separators=(",", ":"))
    )
    (OUT / "sources.json").write_text(
        json.dumps(SOURCES, indent=2)
    )

    log("Build complete.")


if __name__ == "__main__":
    main()
