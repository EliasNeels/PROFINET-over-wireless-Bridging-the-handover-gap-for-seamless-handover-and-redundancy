import os
import re
from pathlib import Path
from plot_engine import plot_comparison, plot_metric_comparison

ROOT = Path(r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis")
OUT_DIR = ROOT / "Plots_NoTable" / "Attenuation_Comparison"
os.makedirs(OUT_DIR, exist_ok=True)

def sort_atten_key(folder_name):
    # Extract dB values (e.g. -40, -75)
    nums = [int(n) for n in re.findall(r'-?\d+', folder_name)]
    
    if "OFF" in folder_name:
        # For OFF scenarios, we want them to appear AFTER the dual-link scenarios 
        # or at least sorted among themselves by the remaining signal.
        # Let's give OFF a lower baseline and add the remaining signal.
        remaining_signal = nums[0] if nums else -100
        return -500 + remaining_signal
    
    if nums:
        # Sum of signal strengths (stronger signal = higher sum, e.g., -115 is better than -150)
        return sum(nums)
    return 0

def generate_attenuation_comparison(tech):
    root_atten = ROOT / tech / "P3_Attenuation"
    if not root_atten.exists():
        return
        
    atten_dirs = [d for d in root_atten.iterdir() if d.is_dir() and "64ms" in d.name]
    
    for base_dir in atten_dirs:
        cycle_name = base_dir.name
        e2e_items = []
        prp_items = []
        
        # --- Add Baseline Reference (5IO) ---
        if tech == "BT":
            baseline_dir = ROOT / tech / "P2_Load" / "5IO_NoUDP" / "64ms"
        else:
            baseline_dir = ROOT / tech / "P2_Load" / "NoQoS" / "5IO_NoUDP" / "64ms"
            
        if baseline_dir.exists():
            e2e_base = list(baseline_dir.glob("*_latencies.csv"))
            if e2e_base:
                e2e_items.append((999, "5IO", e2e_base[0]))
            prp_base = list(baseline_dir.glob("*_prpskew.csv"))
            if prp_base:
                prp_items.append((999, "5IO", prp_base[0]))
        
        subdirs = [d for d in base_dir.iterdir() if d.is_dir()]
        
        for folder in subdirs:
            sort_val = sort_atten_key(folder.name)
            
            # Clean label
            label = folder.name.replace('Wachtdog', '').replace('Watchdog', '').replace('LineA_', 'A:').replace('LineB_', ' B:').replace('_', ' ')
            
            # Extract Bitrates from filenames
            pcap_files = list(folder.glob("*.pcap"))
            if pcap_files:
                pcap_name = pcap_files[0].name
                # Find all occurrences of bitrate like "36Mbitss"
                bit_matches = re.findall(r'([0-9]+)Mbitss?', pcap_name)
                if bit_matches:
                    if "A_OFF" in pcap_name or "A:OFF" in label:
                        # Only show Line B bitrate
                        label += f" (B:{bit_matches[-1]} Mbps)"
                    elif len(bit_matches) >= 2:
                        label += f" (A:{bit_matches[0]} B:{bit_matches[1]} Mbps)"
                    else:
                        label += f" ({bit_matches[0]} Mbps)"
            
            # End2End Latencies
            e2e_csvs = list(folder.glob("*End2End_latencies.csv"))
            if e2e_csvs:
                e2e_items.append((sort_val, label, e2e_csvs[0]))
                
            # PRP Skew
            prp_csvs = list(folder.glob("*PRP_prpskew.csv"))
            if prp_csvs:
                prp_items.append((sort_val, label, prp_csvs[0]))
                
        # Sort so strongest signal is first (high sum to low sum)
        e2e_items.sort(key=lambda x: x[0], reverse=True)
        prp_items.sort(key=lambda x: x[0], reverse=True)
        
        e2e_files = {label: path for _, label, path in e2e_items}
        prp_files = {label: path for _, label, path in prp_items}
        
        if len(e2e_files) > 1:
            print(f"Generating {tech} {cycle_name} Attenuation Latency Comparison Plot...")
            out_path = OUT_DIR / f"{tech}_{cycle_name}_Attenuation_Latency_Comparison.svg"
            
            display_tech = "Wi-Fi" if tech == "WLAN" else "Bluetooth"
            
            if tech == "WLAN":
                title = f"{display_tech} E2E Latency vs Path Attenuation [dBm] (64 ms Cycle Time, 5 IO-Islands)"
                
                # Split OFF cases to secondary axis for better visibility
                off_labels = [l for l in e2e_files.keys() if "OFF" in l]
                other_labels = [l for l in e2e_files.keys() if "OFF" not in l]
                split = [other_labels, off_labels]
                
                # Wi-Fi Specific: Dual Axis with custom scaling for both
                plot_comparison(e2e_files, title, str(out_path), 
                                split_groups=split,
                                hist_dual_both=True,
                                ccdf_log_x=True, 
                                hist_xlim=(0.0, 2.5),
                                hist_ylim_secondary=(0.0, 10.0),
                                hist_xlim_primary=(0.0, 1.0),
                                primary_ylabel='Density')
            else:
                title = f"{display_tech} E2E Latency vs Path Attenuation [dBm] (64 ms Cycle Time, 5 IO-Islands)"
                plot_comparison(e2e_files, title, str(out_path),
                                primary_ylabel='Density')
            
        if len(prp_files) > 1:
            print(f"Generating {tech} {cycle_name} Attenuation Skew Comparison Plot...")
            out_path = OUT_DIR / f"{tech}_{cycle_name}_Attenuation_Skew_Comparison.svg"
            title = f"{display_tech} PRP Skew vs Path Attenuation (64 ms Cycle Time, 5 IO-Islands)"
            plot_metric_comparison(prp_files, "skew_ms", title, "Skew (ms)", str(out_path), cap=None)

for tech in ["BT", "WLAN"]:
    generate_attenuation_comparison(tech)

print(f"\nDone! Curated attenuation comparison Plots_NoTable added to: {OUT_DIR}")
