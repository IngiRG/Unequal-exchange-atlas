# Unequal Exchange Atlas

A global interactive atlas built around **one unequal-exchange methodology** with explicit data-quality tiers.

## One underlying quantity

The atlas estimates:

\[
H_{i\to j}
\]

the employment in producer country \(i\) associated with production serving consumers in country \(j\).

It can be displayed as:

- **Labour transfer** — embodied employment.
- **Monetary value** — an Emmanuel-inspired labour-income counterfactual.

## Tier A — MRIO-backed

Where OECD Trade in Employment (TiM) provides a bilateral country-pair estimate, the site uses it directly.

These observations trace indirect supply chains through OECD's inter-country input-output system.

## Tier B — extended calibrated

Countries outside the MRIO core are not discarded.

The extension first estimates export-linked employment:

\[
D_i = E_i\frac{Exports_i}{GDP_i}
\]

using ILOSTAT employment and World Development Indicators.

For economies that overlap OECD TiM:

\[
m_i =
\frac{\text{OECD TiM foreign-demand employment}_i}{D_i}.
\]

Robust regional median multipliers are calculated from those overlapping economies.

For relationships not covered by TiM:

\[
\tilde H_{i\to j}
=
E_i
\frac{Exports_i}{GDP_i}
m_{region,t}
s_{ij}
\]

where \(s_{ij}\) is country \(j\)'s share of country \(i\)'s balanced merchandise exports in OECD BIMTS.

This is visibly labelled **Extended calibrated**, not MRIO-backed.

## Monetary unequal exchange

Average labour income per employed person is estimated using:

\[
w_i =
\frac{LabourIncomeShare_i \times GDP_i}
{Employment_i}.
\]

Then:

\[
UE_{i\to j}=H_{i\to j}(w_j-w_i).
\]

The formula is **Emmanuel-inspired**. It is not presented as an equation that Arghiri Emmanuel himself published.

## Sources

- OECD Trade in Employment (TiM): MRIO core.
- OECD BIMTS: approximately 200 reporters/partners; bilateral merchandise-trade shares.
- ILOSTAT modelled estimates: employment and labour-income share.
- World Development Indicators: GDP and exports of goods and services.

## Why 2005–2022?

This gives a broad global extension while retaining overlap with the OECD TiM anchor and internationally comparable labour-income inputs.

## Build

```bash
pip install -r scripts/requirements.txt
python scripts/build_data.py --clean --years 2005:2022
```

Or run:

**GitHub → Actions → Refresh global unequal-exchange data → Run workflow**

with:

```text
2005:2022
```

## Website

The map defaults to **Best available**.

The coverage selector can switch to **MRIO-backed only**. That is a confidence filter, not a different economic method.

Country borders show data quality:

- solid light — predominantly MRIO-backed;
- amber — mixed;
- dashed muted — predominantly extended calibrated.

See `DATA_LICENSES.md` for source/reuse notes.
