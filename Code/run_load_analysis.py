import os
import glob
from pathlib import Path
from pcap_analyzer import analyze_pcap
from plot_engine import plot_latency_vs_load

ROOT = Path(__file__).parent

def process_load_directory(base_dir):
    pcap_files = list(Path(base_dir).rglob("*_PRP.pcap"))
    if not pcap_files:
        return

    print(f"\nFound {len(pcap_files)} Load PRP files in {base_dir}")
    
    for pcap in pcap_files:
        print(f"Processing: {pcap.name}")
        # 1. Extract Latency, Skew, and Load
        analyze_pcap(str(pcap), ignore_cache=True)
        
        # 2. Paths to CSVs
        base_name = pcap.with_suffix('')
        prpskew_csv = str(base_name) + "_prpskew.csv"
        load_csv = str(base_name) + "_load.csv"
        
        # 3. Generate Overlay Plot
        if os.path.exists(prpskew_csv) and os.path.exists(load_csv):
            out_plot = str(base_name) + "_Skew_vs_Load.svg"
            title = f"PRP Skew vs UDP Load: {pcap.parent.name}"
            plot_latency_vs_load(prpskew_csv, load_csv, title, out_plot, is_skew=True)

if __name__ == "__main__":
    for tech in ["BT", "WLAN"]:
        load_dir = ROOT / tech / "P2_Load"
        if load_dir.exists():
            print(f"\n{'='*50}\nProcessing Load directory: {load_dir}\n{'='*50}")
            process_load_directory(load_dir)
            
    print("\nAll Load analysis completed successfully!")
