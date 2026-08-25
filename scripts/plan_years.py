#!/usr/bin/env python3
import json,re,sys
v=sys.argv[1] if len(sys.argv)>1 else "2021";ys=[]
for t in re.split(r"[,\s]+",v.strip()):
    if not t:continue
    if ":" in t:
        a,b=map(int,t.split(":"));ys.extend(range(a,b+1))
    else:ys.append(int(t))
ys=sorted(set(y for y in ys if 1995<=y<=2022))
if not ys:raise SystemExit("No valid years")
print(json.dumps(ys,separators=(",",":")))
