# Unequal Exchange Atlas

A GitHub-Pages-ready interactive atlas for exploring alternative estimates of unequal exchange.

## What is included

- Clickable world choropleth with a draggable year timeline and play/pause animation.
- Country detail panel with bilateral relationships.
- Method-specific year ranges.
- Openable summary dashboard with headline statistics and graphs.
- English and mathematical methodology for every estimator.
- GitHub Actions for data refresh and Pages deployment.
- **No Eora dependency.**

## Run locally

```bash
npm install
npm run dev
```

## Real-data pipeline: no Eora

The production architecture uses an open/reusable source stack.

### Core 1995–2022 layers: OECD Trade in Employment

OECD TiM 2025 combines OECD Inter-Country Input-Output tables with official employment and employee-compensation statistics. The atlas pulls the official SDMX API and calculates bilateral country-pair estimates.

```bash
pip install -r scripts/requirements.txt
python scripts/build_data.py --mode oecd --years 1995:2022
```

This creates:

- `emmanuel_wage`: embodied employment × consumer/producer compensation gap.
- `wage_equalisation`: embodied employment × common-reference compensation gap.
- `embodied_labour`: OECD bilateral embodied employment in persons.
- `labour_terms`: bilateral/country embodied-employment balances.

No API key is required.

### Broad ~200-country goods layer: BACI + World Bank

The scheduled workflow uses BACI HS22 for the latest 2022–2024 years because the archive is substantially smaller:

```bash
BACI_HS=22 python scripts/build_data.py --mode baci --years 2022 2023 2024
```

For a one-time full historical goods build:

```bash
BACI_HS=92 python scripts/build_data.py --mode baci --years 1995:2024
```

That layer is deliberately called a **broad goods productivity proxy**. It provides much wider country coverage, but it does not have the supply-chain tracing quality of OECD TiM.

## Mathematical definitions

### 1. Emmanuel bilateral wage counterfactual

\[
UE_{i\to j}=H_{i\to j}(w_j-w_i)
\]

where \(H_{i\to j}\) is OECD embodied employment in producer \(i\) sustained by final demand in \(j\), and

\[
w_i=\frac{Compensation_i}{Employment_i}.
\]

This is the preferred headline Emmanuel-style estimator in the open-data build.

### 2. Common-wage equalisation

\[
UE_{i\to j}=H_{i\to j}(w^*-w_i)
\]

with

\[
w^*=\frac{\sum_i E_iw_i}{\sum_iE_i}.
\]

### 3. Embodied employment

OECD TiM is based on the Leontief production system:

\[
H=\hat e(I-A)^{-1}FD.
\]

The atlas uses OECD's published bilateral `FFD_DEM` result instead of reconstructing the full ICIO matrix.

### 4. Labour terms of exchange

\[
\Delta H_i=\sum_jH_{j\to i}-\sum_jH_{i\to j}.
\]

### 5. Broad goods productivity proxy

\[
UE_{i\to j}=X_{ij}\left(\frac{p_j}{p_i}-1\right)
\]

where \(X\) is BACI bilateral goods trade and \(p\) is World Bank GDP per person employed.

## GitHub workflow

`.github/workflows/update-data.yml`:

- refreshes OECD TiM from the official OECD SDMX API;
- optionally downloads the current BACI archive;
- queries World Bank indicators;
- caches downloaded public source data;
- publishes only compact derived JSON files;
- verifies that no Eora/restricted-data path is present;
- commits refreshed derived outputs.

The scheduled run is quarterly. OECD's own API guidance recommends caching because most datasets are updated infrequently.

## Data licensing

See [DATA_LICENSES.md](DATA_LICENSES.md).

The important distinction is:

- **source statistics are real**;
- the displayed **unequal-exchange transfer is a model-derived counterfactual estimate**.

The site should therefore say “estimated unequal exchange under method X”, rather than presenting the result as a directly observed quantity of imperialism.

## Production notes

For the strongest public release:

1. Build the complete OECD 1995–2022 history.
2. Use the OECD `emmanuel_wage` layer as the default map.
3. Run BACI HS22 automatically for 2022–2024 broad coverage.
4. Optionally run BACI HS92 once to create the full 1995–2024 broad goods timeline.
5. Preserve the generated `meta.json` and per-layer provenance.
6. Add sensitivity variants for the common wage benchmark if desired.
