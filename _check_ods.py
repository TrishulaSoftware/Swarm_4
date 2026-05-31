import ezodf

path = r"H:\Trishula_SBM\DataMine\MLB\Team Props\05_19_2026\team main template.ods"
doc = ezodf.opendoc(path)
sheet = doc.sheets[0]
print(f"Sheet: {sheet.name} ({sheet.nrows()} x {sheet.ncols()})")

non_empty_count = 0
for i in range(sheet.nrows()):
    row = []
    for j in range(sheet.ncols()):
        cell = sheet[i, j]
        val = cell.value
        text = cell.plaintext() if hasattr(cell, 'plaintext') else ""
        rep = str(val) if val is not None else text
        row.append(rep.strip())
    if any(c.strip() for c in row):
        non_empty_count += 1
        if non_empty_count <= 100:
            # Print non-empty items only
            print(f"R{i}: " + " | ".join(f"[{j}]: {c}" for j, c in enumerate(row) if c.strip()))
print("Total non-empty:", non_empty_count)
