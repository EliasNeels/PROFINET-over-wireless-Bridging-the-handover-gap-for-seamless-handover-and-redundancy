import os
from pathlib import Path
from plot_engine import plot_comparison, plot_metric_comparison

ROOT = Path(r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis")
OUT_DIR = ROOT / "Plots_NoTable" / "Baseline_Comparison"
os.makedirs(OUT_DIR, exist_ok=True)

# 1. End-to-End Latency Comparison (64ms)
e2e_files = {
    'Wired (PRP)': ROOT / "Wired" / "PRP" / "Wire_64ms_PRP_End2End_latencies.csv",
    'Bluetooth (BT)': ROOT / "BT" / "P1_Baseline" / "64ms" / "BT_64ms_Base_End2End_latencies.csv",
    'WLAN': ROOT / "WLAN" / "P1_Baseline" / "64ms" / "WLAN_64ms_Base_End2End_latencies.csv"
}
e2e_files = {k: v for k, v in e2e_files.items() if v.exists()}
if e2e_files:
    print("Generating E2E Comparison Plot for 64ms Baseline...")
    out_e2e = OUT_DIR / "Baseline_64ms_E2E_Detailed_Comparison.svg"
    plot_comparison(e2e_files, "E2E Latency Comparison (64ms Baseline)", str(out_e2e))

# 2. PRP Skew Comparison (64ms)
skew_files = {
    'Wired': ROOT / "Wired" / "PRP" / "Wire_64ms_PRP_PRP_prpskew.csv",
    'Bluetooth (BT)': ROOT / "BT" / "P1_Baseline" / "64ms" / "BT_64ms_Base_PRPClient_prpskew.csv",
    'WLAN': ROOT / "WLAN" / "P1_Baseline" / "64ms" / "WLAN_64ms_Base_PRPClient_prpskew.csv"
}
skew_files = {k: v for k, v in skew_files.items() if v.exists()}
if skew_files:
    print("Generating PRP Skew Comparison Plot for 64ms Baseline...")
    out_skew = OUT_DIR / "Baseline_64ms_PRP_Skew_Comparison.svg"
    # We use a larger cap for Skew (BT is ~2ms)
    plot_metric_comparison(skew_files, "skew_ms", "PRP Skew Comparison (64ms Baseline)", "Skew (ms)", str(out_skew), cap=0.5)

# 3. Injection Jitter Comparison (64ms)
ipg_files = {
    'Wired': ROOT / "Wired" / "PRP" / "Wire_64ms_PRP_SwitchAPb_ipg.csv", # If exists
    'Bluetooth (BT)': ROOT / "BT" / "P1_Baseline" / "64ms" / "BT_64ms_Base_SwitchAPb_ipg.csv",
    'WLAN': ROOT / "WLAN" / "P1_Baseline" / "64ms" / "WLAN_64ms_Base_SwitchAPb_ipg.csv"
}
# Fallback for Wired IPG if named differently
if not ipg_files['Wired'].exists():
    # Try finding any ipg in Wired folder
    wired_ipgs = list((ROOT / "Wired").rglob("*ipg.csv"))
    if wired_ipgs: ipg_files['Wired'] = wired_ipgs[0]

ipg_files = {k: v for k, v in ipg_files.items() if v.exists()}
if ipg_files:
    print("Generating Injection Jitter Comparison Plot for 64ms Baseline...")
    out_ipg = OUT_DIR / "Baseline_64ms_Injection_Stability_Comparison.svg"
    plot_metric_comparison(ipg_files, "ipg_ms", "PLC Injection Jitter Comparison (64ms)", "IPG (ms)", str(out_ipg), cap=0.1)

# 4. BT Cycle Time Comparison
print("Generating BT Cycle Time Comparison Plot...")
bt_ct_files = {}
for ct in [16, 32, 64, 128]:
    p = ROOT / "BT" / "P1_Baseline" / f"{ct}ms"
    csvs = list(p.glob("*End2End_latencies.csv"))
    if csvs: bt_ct_files[f"{ct}ms"] = csvs[0]

if len(bt_ct_files) >= 2:
    out_bt_ct = OUT_DIR / "BT_Cycle_Time_Comparison.svg"
    plot_comparison(bt_ct_files, "Bluetooth (BT) Baseline — Latency Comparison at different Cycle Times (1 IO-Island)", str(out_bt_ct))

# 5. WLAN Cycle Time Comparison
print("Generating WLAN Cycle Time Comparison Plot...")
wlan_ct_files = {}
for ct in [16, 32, 64, 128]:
    p = ROOT / "WLAN" / "P1_Baseline" / f"{ct}ms"
    csvs = list(p.glob("*End2End_latencies.csv"))
    if csvs: wlan_ct_files[f"{ct}ms"] = csvs[0]

if len(wlan_ct_files) >= 2:
    out_wlan_ct = OUT_DIR / "WLAN_Cycle_Time_Comparison.svg"
    plot_comparison(wlan_ct_files, "Wi-Fi Baseline — Latency Comparison at different Cycle Times (1 IO-Island)", 
                    str(out_wlan_ct), split_groups=[['16ms', '128ms'], ['32ms', '64ms']],
                    hist_dual_x=False, hist_xlim=(0.5, 0.8))

print(f"\nDone! Curated Plots_NoTable added to: {OUT_DIR}")
