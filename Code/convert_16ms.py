import cairosvg
import os

svg_bt = r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis\Plots\Load_Comparison\BT_16ms_Load_Comparison.svg"
pdf_bt = r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis\Plots\Load_Comparison\BT_16ms_Load_Comparison.pdf"
pdf_bt_latex = r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis\Latex\KU-Leuven-master-thesis-template-FET\figs\results\Load_Comparison\BT_16ms_Load_Comparison.pdf"

svg_wlan = r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis\Plots\Load_Comparison\WLAN_16ms_Load_Comparison.svg"
pdf_wlan = r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis\Plots\Load_Comparison\WLAN_16ms_Load_Comparison.pdf"
pdf_wlan_latex = r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis\Latex\KU-Leuven-master-thesis-template-FET\figs\results\Load_Comparison\WLAN_16ms_Load_Comparison.pdf"

os.makedirs(os.path.dirname(pdf_bt_latex), exist_ok=True)

print("Converting BT...")
cairosvg.svg2pdf(url=svg_bt, write_to=pdf_bt)
cairosvg.svg2pdf(url=svg_bt, write_to=pdf_bt_latex)

print("Converting WLAN...")
cairosvg.svg2pdf(url=svg_wlan, write_to=pdf_wlan)
cairosvg.svg2pdf(url=svg_wlan, write_to=pdf_wlan_latex)

print("Done converting 16ms SVG plots to PDF.")
