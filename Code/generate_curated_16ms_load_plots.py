import os
from pathlib import Path
from plot_engine import plot_comparison

ROOT = Path(r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis")
OUT_DIR = ROOT / "Plots_NoTable" / "Load_Comparison"
os.makedirs(OUT_DIR, exist_ok=True)

def generate_16ms_comparison(tech):
    base_dir = ROOT / tech / "P1_Baseline" / "64ms"
    load_dir = ROOT / tech / "P2_Load"
    
    # Locate files
    baseline_csv = base_dir / f"{tech}_64ms_Base_End2End_latencies.csv"
    if tech == "WLAN":
        load_csv = load_dir / "NoQoS" / "4IO_16ms_16IO_64ms" / f"{tech}_16ms_Load_4IO_End2End_latencies.csv"
    else:
        load_csv = load_dir / "4IO_16ms_16IO_64ms" / f"{tech}_16ms_Load_4IO_End2End_latencies.csv"

    if not baseline_csv.exists() or not load_csv.exists():
        print(f"Warning: Missing files for {tech} 16ms comparison!")
        print(f"  Expected baseline: {baseline_csv} (Exists: {baseline_csv.exists()})")
        print(f"  Expected load: {load_csv} (Exists: {load_csv.exists()})")
        return

    csv_dict = {
        "1 IO Baseline (64 ms)": str(baseline_csv),
        "4 IO Load (16 ms)": str(load_csv)
    }

    display_tech = "Wi-Fi" if tech == "WLAN" else "Bluetooth"
    title = f"{display_tech} E2E Latency vs Load (16ms Cycle Time, 4 IO Islands)"
    subtitle = "Simulates 16 IO @ 64 ms Cycle Time"
    out_path = OUT_DIR / f"{tech}_16ms_Load_Comparison.svg"

    # WLAN latencies are extremely tight (mostly 0.4 - 1.5ms) with very minor outliers.
    # Standardizing limits for WLAN: xlim=(0, 1) focuses on the core distribution between 0 and 1 ms.
    xlim = (0, 1) if tech == "WLAN" else None

    print(f"Generating 16ms Load Comparison Plot for {tech}...")
    plot_comparison(
        csv_dict=csv_dict,
        title=title,
        out_path=str(out_path),
        cycle_time_ms=64.0,
        hist_xlim=xlim,
        ccdf_log_x=True if tech == "WLAN" else False,
        include_table=True
    )

if __name__ == "__main__":
    for tech in ["BT", "WLAN"]:
        generate_16ms_comparison(tech)
    print("\n16ms Load Comparison Plots_NoTable generated successfully!")
