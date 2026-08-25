#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/"public/data/exio"
man=[]
for p in sorted(DATA.glob("*/manifest.json")):
    try:man.append(json.loads(p.read_text()))
    except Exception:pass
if not man:raise SystemExit("No year manifests found")
years=sorted({int(m["year"]) for m in man});latest=max(man,key=lambda x:int(x["year"]))
meta={"mode":"exiobase-native","years":years,"latest_year":max(years),"exiobase_version":"3.8.2","exiobase_doi":"10.5281/zenodo.5589597","license":"CC-BY-SA","geography":"44 individual countries + 5 Rest-of-World regions","regions":latest["regions"],"region_names":latest["region_names"],"row_regions":latest["row_regions"],"country_to_region":latest["country_to_region"],"geometry":latest["geometry"],"members":latest["members"],"global_north":latest["global_north"],"skills":["all","low","medium","high"],"views":["labour_hours","wage_value"],"north_south_by_year":{str(m["year"]):m.get("north_south",{}) for m in man}}
(DATA/"meta.json").write_text(json.dumps(meta,indent=2))
print("Years:",years)
