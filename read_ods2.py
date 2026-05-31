import sys, subprocess
subprocess.check_call([sys.executable, "-m", "pip", "install", "ezodf", "lxml", "-q"])
import ezodf

path = r"H:\Trishula_SBM\DataMine\MLB\Team Props\MLB Team Prop 05_18_2026.ods"
doc = ezodf.opendoc(path)

print(f"Total sheets: {len(doc.sheets)}")
for idx, sheet in enumerate(doc.sheets):
    print(f"\n=== SHEET {idx}: '{sheet.name}' ({sheet.nrows()} rows x {sheet.ncols()} cols) ===")
    for i in range(min(sheet.nrows(), 200)):
        row = []
        for j in range(sheet.ncols()):
            v = sheet[i, j].value
            row.append(str(v) if v is not None else "")
        if any(c.strip() for c in row):
            print(f"R{i}: " + " | ".join(c for c in row if c.strip()))
