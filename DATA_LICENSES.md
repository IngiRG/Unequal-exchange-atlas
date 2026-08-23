# Data sources, licences, and publication policy

The production version of this project has **no Eora dependency**.

## OECD Trade in Employment (TiM), 2025 edition

This is the main empirical source. OECD says TiM combines its Inter-Country
Input-Output system with recent official statistics on employment and compensation
of employees by industrial activity. It provides bilateral counterpart-country
measures over 1995–2022 and 50 industries.

OECD's Terms & Conditions for Data state that, except where a dataset has additional
restrictions, users may extract, download, copy, adapt, distribute, share and embed
OECD Data for any purpose, including commercial use, provided appropriate credit is
given and the attribution requirement is carried through to sublicensing.

Source:
https://www.oecd.org/en/data/datasets/trade-in-employment.html

Terms:
https://www.oecd.org/en/about/terms-conditions.html

Required project attribution:
`OECD (2026), Trade in Employment (TiM), 2025 edition, OECD Data Explorer.`

The workflow queries the official OECD SDMX API and publishes derived country-pair
results with source attribution.

## CEPII BACI

BACI 202601 provides reconciled bilateral product-level goods trade for roughly 200
countries. CEPII lists the dataset under the **Etalab Open Licence 2.0**.

Source:
https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37

The scheduled workflow uses HS22 (2022–2024) because it is much smaller. You can set
the repository Actions variable `BACI_HS=92` and run 1995:2024 manually for the full
historical BACI goods layer.

## World Bank

The BACI broad-coverage layer uses World Bank GDP per person employed as an explicitly
labelled productivity proxy. World Bank-produced Open Data are generally CC BY 4.0,
subject to dataset-specific terms.

## Why OECD TiM is preferable here

For the core unequal-exchange layers we do **not** infer labour content merely from
customs values. OECD TiM already traces employment through global production chains
using ICIO and combines those tables with official employment/compensation data.

That lets the site calculate:

1. **Emmanuel bilateral wage counterfactual**

   `UE(i→j) = H(i→j) × [w(j) − w(i)]`

   `H(i→j)` is OECD embodied employment in producer i sustained by final demand in j.
   `w(i)` is OECD employee compensation divided by employment.

2. **Common-wage equalisation**

   `UE(i→j) = H(i→j) × [w* − w(i)]`

   where `w*` is the employment-weighted mean annual compensation per worker among
   economies with data in that year.

3. **Embodied employment transfer**

   `H(i→j)` itself, in persons. This is an observed/modelled OECD supply-chain labour
   requirement, not a monetary unequal-exchange estimate.

4. **Labour terms of exchange**

   Country balance:
   `ΔH(i) = Σj H(j→i) − Σj H(i→j)`.

5. **Broad goods productivity proxy**

   `UE(i→j) = X(i→j) × [p(j)/p(i) − 1]`

   using BACI goods trade and World Bank GDP/person employed. It provides much broader
   country coverage but is deliberately labelled a proxy.

## Interpretation

The source statistics are real. **Unequal exchange is still a theoretical,
counterfactual interpretation of those statistics.** The website must say
"estimated unequal exchange under method X", not "objectively measured imperialism".

The project should retain source/version metadata in every generated release.
