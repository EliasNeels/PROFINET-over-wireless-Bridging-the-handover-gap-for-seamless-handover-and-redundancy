import os
import sys
import cairosvg
from pathlib import Path

# Add MasterThesis to path so we can import plot_engine
thesis_path = r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis"
if thesis_path not in sys.path:
    sys.path.append(thesis_path)

from plot_engine import plot_comparison

def main():
    print("Generating 1AP vs 2AP Bluetooth comparison Plots_NoTable...")
    
    csv_2ap = Path(r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis\BT\P1_Baseline\64ms\BT_64ms_Base_End2End_latencies.csv")
    csv_1ap = Path(r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis\1AP_2CL\Baseline\BT1AP2CL_Baseline_PCAP_Hilscher_64ms_00001_20260320115621_End2End_latencies.csv")
    
    csv_dict = {
        "2AP 2CL (Standard Baseline)": str(csv_2ap),
        "1AP 2CL (MAC Flapping Baseline)": str(csv_1ap)
    }
    
    title = "Bluetooth E2E Latency: 1AP vs. 2AP Client Architectures"
    svg_out = Path(r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis\Plots_NoTable\Baseline_Comparison\BT_1AP_vs_2AP_Comparison_Plot.svg")
    pdf_out = Path(r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis\Latex\KU-Leuven-master-thesis-template-FET\figs\results\NoTable\BT_1AP_vs_2AP_Comparison_Plot.pdf")
    
    # Ensure directories exist
    svg_out.parent.mkdir(parents=True, exist_ok=True)
    pdf_out.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate 4-panel comparison
    plot_comparison(
        csv_dict=csv_dict,
        title=title,
        out_path=str(svg_out),
        cycle_time_ms=64.0
    )
    
    # Convert to high-resolution vector PDF
    print(f"Converting to vector PDF: {pdf_out.name}...")
    try:
        cairosvg.svg2pdf(url=str(svg_out), write_to=str(pdf_out))
        print("Success! Comparison Plots_NoTable and vector PDF compiled successfully.")
    except Exception as e:
        print(f"Error compiling PDF: {e}")

if __name__ == "__main__":
    main()
