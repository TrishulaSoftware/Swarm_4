import sys, subprocess
subprocess.check_call([sys.executable, "-m", "pip", "install", "ezodf", "lxml", "-q"])
import ezodf, json

path = r"H:\Trishula_SBM\DataMine\MLB\Team Props\MLB Team Prop 05_18_2026.ods"
doc = ezodf.opendoc(path)

all_sheets = []
for sheet in doc.sheets:
    rows = []
    for i in range(sheet.nrows()):
        row = []
        for j in range(sheet.ncols()):
            v = sheet[i, j].value
            row.append(str(v) if v is not None else "")
        if any(c.strip() for c in row):
            rows.append(row)
    all_sheets.append({"name": sheet.name, "rows": rows})
    print(f"SHEET: {sheet.name} ({len(rows)} rows)")
    for r in rows[:80]:
        print(" | ".join(r))
    print("---")

with open(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging\ods_dump.json", "w") as f:
    json.dump(all_sheets, f, indent=2)
print("Dumped to ods_dump.json")
