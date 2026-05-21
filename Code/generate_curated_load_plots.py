import os
import re
from pathlib import Path
from plot_engine import plot_comparison

ROOT = Path(r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis")
OUT_DIR = ROOT / "Plots_NoTable" / "Load_Comparison"
os.makedirs(OUT_DIR, exist_ok=True)

def sort_load_key(folder_name):
    # Typo-proof regex: looks for numbers before 'M' (handles Mbps and Mpbs)
    match = re.search(r'([0-9]+(?:,[0-9]+)?)M', folder_name, re.IGNORECASE)
    if match:
        val_str = match.group(1).replace(',', '.')
        try:
            return float(val_str)
        except ValueError:
            return 0.0
    return 0.0

def generate_load_comparison(tech, packet_size, base_load_dir, suffix=""):
    load_dir = base_load_dir / f"5IO_{packet_size}_UDP" / "64ms"
    if not load_dir.exists():
        return
        
    items = []
    
    # 1. Baseline (Reference)
    baseline_dir = base_load_dir / "5IO_NoUDP" / "64ms"
    if baseline_dir.exists():
        baseline_csvs = list(baseline_dir.glob("*End2End_latencies.csv"))
        if baseline_csvs:
            items.append((-1.0, "5IO", baseline_csvs[0]))
            
    # 2. Load steps
        for folder in [d for d in load_dir.iterdir() if d.is_dir()]:
            csvs = list(folder.glob("*End2End_latencies.csv"))
            if csvs:
                mbps_val = sort_load_key(folder.name)
                
                # Filter out outliers or unstable measurements if requested
                if tech == "BT" and packet_size == "1400B" and abs(mbps_val - 0.35) < 0.01:
                    continue
                if tech == "WLAN" and packet_size == "64B" and abs(mbps_val - 10.0) < 0.1:
                    continue
                if tech == "BT" and packet_size == "64B" and abs(mbps_val - 0.15) < 0.01:
                    continue

                # Normalize label name for the plot
    for folder in [d for d in load_dir.iterdir() if d.is_dir()]:
        csvs = list(folder.glob("*End2End_latencies.csv"))
        if csvs:
            mbps_val = sort_load_key(folder.name)
            
            # Filter out outliers or unstable measurements if requested
            if tech == "BT" and packet_size == "1400B" and abs(mbps_val - 0.35) < 0.01:
                continue
            if tech == "WLAN" and packet_size == "64B" and abs(mbps_val - 10.0) < 0.1:
                continue
            if tech == "BT" and packet_size == "64B" and abs(mbps_val - 0.15) < 0.01:
                continue

            # Normalize label name for the plot
            name = folder.name.replace('_Watchdog', '').replace('_Wachtdog', '').replace('_SwitchError', '')
            # Standardize to "X Mbps"
            match_m = re.search(r'([0-9]+(?:,[0-9]+)?)M', name, re.IGNORECASE)
            if match_m:
                mbps_str = match_m.group(1).replace(',', '.')
                label = f"5IO + UDP {mbps_str} Mbps"
            else:
                label = f"5IO + UDP {name}"
            items.append((mbps_val, label, csvs[0]))
            
    items.sort(key=lambda x: x[0])
    print(f"  [Sort Order] {tech} {suffix} {packet_size}: {[x[1] for x in items]}")
    
    files = {label: path for _, label, path in items}
    
    if len(files) > 1:
        prefix = f"{tech}_{suffix}_" if suffix else f"{tech}_"
        title_suffix = f" {suffix}" if suffix else ""
        out_path = OUT_DIR / f"{prefix}64ms_{packet_size}_Load_Comparison.svg"
        tech_map = {"WLAN": "Wi-Fi", "BT": "Bluetooth"}
        display_tech = tech_map.get(tech, tech)
        display_packet = packet_size.replace('B', '')
        title = f"{display_tech} E2E Latency vs UDP Load (64 ms Cycle Time, {display_packet} Bytes UDP Packets){title_suffix}"
        
        # WLAN histograms should be zoomed into 0-3.5ms for better visibility (unless it's the high-latency 64B load)
        xlim = (0, 2) if (tech == "WLAN" and packet_size == "1400B") else None
        
        # For WLAN 64B, use dual X and Y axes to separate the tall baseline peak from shorter load peaks
        # For WLAN 1400B, keep it simple as requested
        split = None
        split_ccdf = None
        dual_xy = False
        if tech == "WLAN" and packet_size == "64B":
            # Baseline is alone on primary for Histogram/Box to allow zooming
            split = [["5IO"], [l for l in files.keys() if l != "5IO"]]
            
            # 7.5 Mbps is alone on secondary for CCDF
            split_ccdf = None
            has_7_5 = any("7.5 Mbps" in l for l in files.keys())
            if has_7_5:
                split_ccdf = [[l for l in files.keys() if "7.5 Mbps" not in l], [l for l in files.keys() if "7.5 Mbps" in l]]
            
            dual_xy = True
            
        # WLAN specific zoom and dual CCDF axis
        hist_p_xlim = (0, 1.5) if tech == "WLAN" else None
        
        # We're trying Log X for CCDF instead of dual-axis
        ccdf_log = True if tech == "WLAN" else False
        ccdf_dual = False # Disable dual CCDF axis when using Log X

        # WLAN 1400B: Disable secondary Y axis for histogram as requested
        h_dual_y = True if (tech == "WLAN" and packet_size != "1400B") else False
        
        # BT specific: Force IO -> PLC for baseline only, use worst-case for loads
        dir_filter = {"5IO": "IO -> PLC"} if tech == "BT" else None
        
        # WLAN: secondary axis text is forced to black in plot_engine, 
        # so we let the lines (spines) stay in their original green color (secondary_color=None)
        sec_color = None
        
        # WLAN QoS 1400B: Force density axis to 50 to accommodate the peak
        h_ylim_p = (0, 50) if (tech == "WLAN" and packet_size == "1400B" and suffix == "QoS") else None

        plot_comparison(files, title, str(out_path), hist_xlim=xlim, 
                        split_groups=split, hist_dual_x=dual_xy, hist_dual_y=h_dual_y,
                        box_dual_y=False, ccdf_dual_x=ccdf_dual, hist_xlim_primary=hist_p_xlim,
                        split_groups_ccdf=split_ccdf, direction_filter=dir_filter,
                        ccdf_log_x=ccdf_log, secondary_color=sec_color,
                        hist_ylim_primary=h_ylim_p)

for tech in ["BT", "WLAN"]:
    for packet_size in ["1400B", "64B"]:
        base_dir = ROOT / tech / "P2_Load"
        if tech == "WLAN":
            generate_load_comparison(tech, packet_size, base_dir / "NoQoS", "NoQoS")
            generate_load_comparison(tech, packet_size, base_dir / "QoS", "QoS")
        else:
            generate_load_comparison(tech, packet_size, base_dir)

print(f"\nDone! Curated load comparison Plots_NoTable updated in: {OUT_DIR}")
