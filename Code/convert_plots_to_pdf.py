"""Convert all SVG Plots_NoTable to PDF for LaTeX inclusion and copy to figs/results/NoTable/."""
import os
import cairosvg
from pathlib import Path

SRC = Path(r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis\Plots_NoTable")
DST = Path(r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis\Latex\KU-Leuven-master-thesis-template-FET\figs\results\NoTable")
os.makedirs(DST, exist_ok=True)

# Also convert individual E2E Plots_NoTable from handover directories
EXTRA_SVGS = [
    Path(r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis\BT\P4_Seamless_Handover\BT_64ms_SeamlessHandover_PullA_PullBoth_PullB_Both_5minInterval_End2End_E2E_Plot.svg"),
    Path(r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis\WLAN\P4_seamless_handover\WLAN_64ms_SeamlessHandover_PullA_PullBoth_PullB_Both_4minInterval_End2End_E2E_Plot.svg"),
]

count = 0
# Walk through all subdirectories
for svg_file in SRC.rglob("*.svg"):
    pdf_name = svg_file.stem + ".pdf"
    pdf_path = DST / pdf_name
    print(f"  Converting: {svg_file.name} -> {pdf_name}")
    try:
        cairosvg.svg2pdf(url=str(svg_file), write_to=str(pdf_path))
        count += 1
    except Exception as e:
        print(f"    ERROR: {e}")

# Extra SVGs
for svg_file in EXTRA_SVGS:
    if svg_file.exists():
        pdf_name = svg_file.stem + ".pdf"
        pdf_path = DST / pdf_name
        print(f"  Converting extra: {svg_file.name} -> {pdf_name}")
        try:
            cairosvg.svg2pdf(url=str(svg_file), write_to=str(pdf_path))
            count += 1
        except Exception as e:
            print(f"    ERROR: {e}")

print(f"\nDone! Converted {count} SVGs to PDF in: {DST}")
