# Data licensing and source decisions

## OECD

Used for:

- Trade in Employment (TiM)
- Balanced International Merchandise Trade Statistics (BIMTS)

OECD data use is subject to OECD's current Terms and Conditions and any dataset-specific notices.

Terms:
https://www.oecd.org/en/about/terms-conditions.html

Sources:
https://www.oecd.org/en/data/datasets/trade-in-employment.html
https://www.oecd.org/en/data/datasets/oecd-balanced-trade-statistics.html

## ILOSTAT

Used for:

- modelled employment;
- modelled labour-income share.

ILO states that databases, datasets and accompanying reference metadata published from 3 May 2023 are covered by CC BY 4.0, subject to the ILO's terms and exclusions for constituent/partner microdata.

Source:
https://ilostat.ilo.org/

## World Development Indicators

Used for:

- GDP at current USD;
- exports of goods and services at current USD.

The World Bank Data Catalog lists World Development Indicators under CC BY 4.0.

Source:
https://datacatalog.worldbank.org/search/dataset/0037712/world-development-indicators

## Why not GLORIA?

GLORIA is technically attractive and currently reaches 164 regions. However, IELab explicitly points commercial users to commercial licences from FootprintLab. To keep this project's future distribution and use terms simple, GLORIA is not an automated dependency.

## Why not ADB MRIO?

ADB MRIO reaches 74 economies, and ADB's general data terms are often permissive. But some related input-output resources carry dataset-specific "All Rights Reserved" labels. The automated production pipeline therefore does not rely on ADB MRIO.

## Publication policy

Raw source downloads are cached during builds and excluded from Git.

The public repository publishes derived bilateral estimates, confidence metadata, and source provenance.
