# Unequal Exchange Atlas — EXIOBASE edition

This version uses **EXIOBASE 3.8.2 at its native geographic resolution** instead of estimating ~190 individual countries.

EXIOBASE 3.8.2 provides:
- 44 individual countries;
- 5 Rest-of-World regions;
- 200 product sectors in the product-by-product system;
- labour hours and employment by low/medium/high skill and gender;
- employee compensation by skill;
- a genuine global MRIO.

The Zenodo 3.8.2 record explicitly states a CC-BY-SA licence.

## Physical measure

\[
H_{p\to c}=\sum_i q_{p,i}[Ly_c]_{p,i}
\]

with \(L=(I-A)^{-1}\). The site reports **net embodied labour hours** between regions.

## Wage-value view

EXIOBASE export wage by skill:

\[
w_{r,k}=
\frac{\text{compensation embodied in r's labour exports}}
{\text{labour hours embodied in r's exports}}.
\]

Pairwise net-appropriated hours are valued at the recipient's same-skill export wage.

This is a counterfactual wage value, not an observed cash transfer.

## Hickel benchmark

Hickel, Hanbury Lemos & Barbour (2024) used EXIOBASE 3.8.1 and report for 2021:
- South → North: 906 billion hours
- North → South: 80 billion hours
- net North appropriation: 826 billion hours
- wage value: €16.9 trillion

The build calculates the same North/South aggregation automatically. Because this project uses 3.8.2, exact equality is not expected.

## Build

Start with one year:

```bash
pip install -r scripts/requirements.txt
python scripts/build_exiobase.py --year 2021
python scripts/merge_exiobase_metadata.py
```

Or use GitHub:

**Actions → Build EXIOBASE atlas data → Run workflow**

and enter:

```text
2021
```

Validate 2021 before building history. Then try:

```text
1995 2000 2005 2010 2011 2015 2018 2020 2021
```

Only after validation should you run:

```text
1995:2021
```

The raw EXIOBASE archives are never committed.
