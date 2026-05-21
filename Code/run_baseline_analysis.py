import os
import glob
from pathlib import Path
from pcap_analyzer import analyze_pcap
from plot_engine import plot_prp_skew, plot_injection_jitter

ROOT = Path(__file__).parent
print("Scanning for PRPClient and SwitchAPb files for Baseline analysis...")

prp_files = glob.glob(str(ROOT / "**" / "*PRPClient.pcap*"), recursive=True)
switch_files = glob.glob(str(ROOT / "**" / "*SwitchAPb.pcap*"), recursive=True)

print(f"Found {len(prp_files)} PRPClient files and {len(switch_files)} SwitchAP files.")

# 1. Analyze PRPClient files
for f in prp_files:
    print(f"\nProcessing PRP Skew: {f}")
    # Run analyzer (it will generate the _prpskew.csv)
    analyze_pcap(f, ignore_cache=True)
    
    # Check if CSV was created
    csv_path = f.replace(".pcapng", "").replace(".pcap", "") + "_prpskew.csv"
    if os.path.exists(csv_path):
        print(f"Plotting PRP Skew for {csv_path}")
        plot_prp_skew(csv_path)
    else:
        print(f"Warning: No _prpskew.csv generated for {f}")

# 2. Analyze SwitchAP files
for f in switch_files:
    print(f"\nProcessing Injection Jitter: {f}")
    # Run analyzer (it will generate the _ipg.csv)
    analyze_pcap(f, ignore_cache=True)
    
    # Check if CSV was created
    csv_path = f.replace(".pcapng", "").replace(".pcap", "") + "_ipg.csv"
    if os.path.exists(csv_path):
        print(f"Plotting Injection Jitter for {csv_path}")
        plot_injection_jitter(csv_path)
    else:
        print(f"Warning: No _ipg.csv generated for {f}")

print("\nBaseline analysis complete. Plots and CSVs are generated next to the source pcap files.")
