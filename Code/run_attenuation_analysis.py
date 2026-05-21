import os
import glob
from pathlib import Path
from pcap_analyzer import analyze_pcap

ROOT = Path(__file__).parent

def process_attenuation_directory(base_dir):
    pcap_files = list(Path(base_dir).rglob("*_PRP.pcap"))
    if not pcap_files:
        return

    print(f"\nFound {len(pcap_files)} Attenuation PRP files in {base_dir}")
    
    for pcap in pcap_files:
        print(f"Processing: {pcap.name}")
        # Extract Latency and Skew
        analyze_pcap(str(pcap), ignore_cache=True)
        
        base_name = pcap.with_suffix('')
        prpskew_csv = str(base_name) + "_prpskew.csv"
        
        # We can also generate the individual skew plot if needed, 
        # but the curated plot will handle the comparison.

if __name__ == "__main__":
    for tech in ["BT", "WLAN"]:
        atten_dir = ROOT / tech / "P3_Attenuation"
        if atten_dir.exists():
            print(f"\n{'='*50}\nProcessing Attenuation directory: {atten_dir}\n{'='*50}")
            process_attenuation_directory(atten_dir)
            
    print("\nAll Attenuation PRP analysis completed successfully!")
