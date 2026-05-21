"""
Generate_thesis_Plots.py
========================
Discovers all *_latencies.csv files, generates:
  1) Individual 6-panel analysis per file  (saved next to CSV)
  2) Cross-technology & cross-scenario comparison plots (saved in Plots/)

Usage:  python Generate_thesis_Plots.py
"""
import os, re, glob
from pathlib import Path
from plot_engine import plot_individual, plot_comparison

BASE = Path(__file__).resolve().parent
PLOTS_DIR = BASE / "Plots"

# ═══════════════════════════════════════════════════════════════════════════
#  CSV discovery
# ═══════════════════════════════════════════════════════════════════════════
def find_csvs(tech):
    """Return sorted list of all *_latencies.csv under a technology folder."""
    root = BASE / tech
    return sorted(glob.glob(str(root / "**" / "*_latencies.csv"), recursive=True))

def extract_cycle_time(path):
    m = re.search(r'(\d+)ms', os.path.basename(path))
    return int(m.group(1)) if m else None

def extract_rate(path):
    m = re.search(r'(\d+[,.]?\d*)Mbps', os.path.basename(path))
    if m:
        return m.group(1).replace(',', '.')
    return None

def short_label(path):
    stem = Path(path).stem.replace('_latencies', '').replace('_End2End', '')
    return stem.replace('_', ' ')


# ═══════════════════════════════════════════════════════════════════════════
#  Phase 1: Individual plots for every CSV
# ═══════════════════════════════════════════════════════════════════════════
def generate_individual_plots():
    print("\n" + "="*60)
    print("  PHASE 1: Individual 6-panel plots")
    print("="*60)
    for tech in ("BT", "WLAN", "Wired"):
        csvs = find_csvs(tech)
        print(f"\n--- {tech}: {len(csvs)} CSV files ---")
        for c in csvs:
            plot_individual(c)


# ═══════════════════════════════════════════════════════════════════════════
#  Phase 2: Comparison plots
# ═══════════════════════════════════════════════════════════════════════════
def generate_comparison_plots():
    print("\n" + "="*60)
    print("  PHASE 2: Comparison plots")
    print("="*60)

    # ── 2a) Baseline: BT vs WLAN vs Wired per cycle time ──────────────────
    _compare_baselines()
    # ── 2b) BT baseline across cycle times ────────────────────────────────
    _compare_cycle_times("BT")
    # ── 2c) WLAN baseline across cycle times ──────────────────────────────
    _compare_cycle_times("WLAN")
    # ── 2d) BT Load tests ────────────────────────────────────────────────
    _compare_load("BT")
    # ── 2e) WLAN Load tests ──────────────────────────────────────────────
    _compare_load("WLAN")
    # ── 2f) WLAN QoS vs NoQoS ────────────────────────────────────────────
    _compare_qos()
    # ── 2g) Attenuation ──────────────────────────────────────────────────
    _compare_attenuation("BT")
    _compare_attenuation("WLAN")
    # ── 2h) Seamless Handover ────────────────────────────────────────────
    _compare_handover()
    # ── 2i) Wired configs ────────────────────────────────────────────────
    _compare_wired()


# ── Helper: Baseline comparison ───────────────────────────────────────────
def _compare_baselines():
    print("\n--- Baseline: BT vs WLAN vs Wired ---")
    out_dir = PLOTS_DIR / "Baseline_Comparison"

    # Per cycle time: BT vs WLAN
    for ct in [16, 32, 64, 128]:
        d = {}
        bt = BASE / "BT" / "P1_Baseline" / f"{ct}ms"
        wl = BASE / "WLAN" / "P1_Baseline" / f"{ct}ms"
        bt_csv = list(bt.glob("*End2End_latencies.csv"))
        wl_csv = list(wl.glob("*End2End_latencies.csv"))
        if bt_csv: d[f"BT {ct}ms"] = str(bt_csv[0])
        if wl_csv: d[f"WLAN {ct}ms"] = str(wl_csv[0])
        if ct == 64:
            # Add wired reference
            for wc in ("NoPRP", "PRP", "SeriePRP/NoCablePulls"):
                wp = BASE / "Wired" / wc
                wcsv = list(wp.glob("*End2End_latencies.csv"))
                if wcsv:
                    lbl = wc.replace("/NoCablePulls", "").replace("NoPRP", "No PRP").replace("SeriePRP", "Series PRP")
                    d[f"Wired {lbl}"] = str(wcsv[0])
        if len(d) >= 2:
            plot_comparison(d, f"Baseline Comparison — {ct}ms Cycle Time",
                            str(out_dir / f"Baseline_{ct}ms_BT_vs_WLAN.svg"))

    # All-in-one: BT + WLAN at 64ms + Wired
    d_all = {}
    for tech, prefix in [("BT", "BT"), ("WLAN", "WLAN")]:
        p = BASE / tech / "P1_Baseline" / "64ms"
        csvs = list(p.glob("*End2End_latencies.csv"))
        if csvs: d_all[f"{prefix} 64ms"] = str(csvs[0])
    for wc in ("NoPRP", "PRP"):
        wp = BASE / "Wired" / wc
        wcsv = list(wp.glob("*End2End_latencies.csv"))
        if wcsv: d_all[f"Wired {wc}"] = str(wcsv[0])
    if len(d_all) >= 2:
        plot_comparison(d_all, "All Technologies — 64ms Baseline",
                        str(out_dir / "Baseline_64ms_All_Technologies.svg"))


# ── Helper: Cycle time comparison within a technology ─────────────────────
def _compare_cycle_times(tech):
    print(f"\n--- {tech}: Cycle Time Comparison ---")
    d = {}
    for ct in [16, 32, 64, 128]:
        p = BASE / tech / "P1_Baseline" / f"{ct}ms"
        csvs = list(p.glob("*End2End_latencies.csv"))
        if csvs: d[f"{ct}ms"] = str(csvs[0])
    if len(d) >= 2:
        out = PLOTS_DIR / f"{tech}_Baseline" / f"{tech}_Cycle_Time_Comparison.svg"
        plot_comparison(d, f"{tech} Baseline — Cycle Time Comparison", str(out))


# ── Helper: Load comparison ───────────────────────────────────────────────
def _compare_load(tech):
    print(f"\n--- {tech}: Load Comparison ---")
    load_root = BASE / tech / "P2_Load"
    if not load_root.exists():
        return

    # Group CSVs by (packet_size, cycle_time)
    groups = {}
    for csv_path in sorted(glob.glob(str(load_root / "**" / "*End2End_latencies.csv"), recursive=True)):
        bn = os.path.basename(csv_path)
        ct = extract_cycle_time(csv_path)
        rate = extract_rate(csv_path)

        # Determine packet size category
        if "1400B" in bn:
            pkt = "1400B"
        elif "64B" in bn:
            pkt = "64B"
        elif "NoUDP" in bn:
            pkt = "NoUDP"
        else:
            pkt = "NoUDP"

        # Determine QoS (WLAN only)
        qos = ""
        if tech == "WLAN":
            if "QoS" in csv_path and "NoQoS" not in csv_path:
                qos = "_QoS"
            else:
                qos = "_NoQoS"

        key = f"{pkt}_{ct}ms{qos}"
        if key not in groups:
            groups[key] = {}

        if rate:
            label = f"{rate} Mbps"
        else:
            label = "No UDP"
        groups[key][label] = csv_path

    # Also add baseline reference to each group
    for key, traces in groups.items():
        ct_match = re.search(r'(\d+)ms', key)
        if ct_match:
            ct_val = ct_match.group(1)
            bl = BASE / tech / "P1_Baseline" / f"{ct_val}ms"
            bl_csvs = list(bl.glob("*End2End_latencies.csv"))
            if bl_csvs:
                traces[f"Baseline {ct_val}ms"] = str(bl_csvs[0])

    for key, traces in sorted(groups.items()):
        if len(traces) < 2:
            continue
        # Sort by rate numerically, but baseline always first
        def rate_sort(item):
            lbl = item[0]
            if 'Baseline' in lbl:
                return -999  # Always first
            m = re.search(r'([\d.]+)', lbl)
            return float(m.group(1)) if m else -1
        sorted_traces = dict(sorted(traces.items(), key=rate_sort))

        out = PLOTS_DIR / f"{tech}_Load" / f"{tech}_Load_{key}.svg"
        plot_comparison(sorted_traces, f"{tech} Load — {key.replace('_', ' ')}",
                        str(out))


# ── Helper: QoS comparison ───────────────────────────────────────────────
def _compare_qos():
    print("\n--- WLAN: QoS vs NoQoS ---")
    load_root = BASE / "WLAN" / "P2_Load"
    if not load_root.exists():
        return

    # Find matching QoS/NoQoS pairs at 64ms
    noqos_root = load_root / "NoQoS"
    qos_root = load_root / "QoS"
    if not noqos_root.exists() or not qos_root.exists():
        return

    # Compare NoUDP
    d = {}
    for subdir, label_prefix in [("NoQoS", "NoQoS"), ("QoS", "QoS")]:
        for ct in [16, 64]:
            p = load_root / subdir / "5IO_NoUDP" / f"{ct}ms"
            csvs = list(p.glob("*End2End_latencies.csv"))
            if csvs:
                d[f"{label_prefix} {ct}ms NoUDP"] = str(csvs[0])
    if len(d) >= 2:
        out = PLOTS_DIR / "WLAN_QoS" / "WLAN_QoS_vs_NoQoS_NoUDP.svg"
        plot_comparison(d, "WLAN QoS vs NoQoS — 5 IO No UDP", str(out))

    # Compare 1400B at common rates
    for pkt_size in ["5IO_1400B_UDP", "5IO_64B_UDP"]:
        for ct in [64]:
            noqos_csvs = sorted(glob.glob(str(noqos_root / pkt_size / f"{ct}ms" / "**" / "*End2End_latencies.csv"), recursive=True))
            qos_csvs = sorted(glob.glob(str(qos_root / pkt_size / f"{ct}ms" / "**" / "*End2End_latencies.csv"), recursive=True))

            # Build rate-indexed dicts
            nq_by_rate = {}
            for c in noqos_csvs:
                r = extract_rate(c)
                if r: nq_by_rate[r] = c
            q_by_rate = {}
            for c in qos_csvs:
                r = extract_rate(c)
                if r: q_by_rate[r] = c

            common = set(nq_by_rate.keys()) & set(q_by_rate.keys())
            if common:
                d = {}
                for rate in sorted(common, key=lambda x: float(x)):
                    d[f"NoQoS {rate}Mbps"] = nq_by_rate[rate]
                    d[f"QoS {rate}Mbps"] = q_by_rate[rate]
                pkt_label = pkt_size.replace("5IO_", "").replace("_UDP", "")
                out = PLOTS_DIR / "WLAN_QoS" / f"WLAN_QoS_vs_NoQoS_{pkt_label}_{ct}ms.svg"
                plot_comparison(d, f"WLAN QoS vs NoQoS — {pkt_label} {ct}ms", str(out))


# ── Helper: Attenuation comparison ────────────────────────────────────────
def _compare_attenuation(tech):
    print(f"\n--- {tech}: Attenuation Comparison ---")
    att_root = BASE / tech / "P3_Attenuation"
    if not att_root.exists():
        return

    csvs = sorted(glob.glob(str(att_root / "**" / "*End2End_latencies.csv"), recursive=True))
    if not csvs:
        return

    d = {}
    for c in csvs:
        # Extract attenuation info from parent folder
        parent = Path(c).parent.name
        label = parent.replace("LineA_", "A:").replace("LineB_", " B:").replace("_", "")
        d[label] = c

    # Add baseline reference FIRST
    ordered = {}
    bl = BASE / tech / "P1_Baseline" / "64ms"
    bl_csvs = list(bl.glob("*End2End_latencies.csv"))
    if bl_csvs:
        ordered["Baseline 64ms"] = str(bl_csvs[0])
    ordered.update(d)

    if len(ordered) >= 2:
        out = PLOTS_DIR / f"{tech}_Attenuation" / f"{tech}_Attenuation_Comparison.svg"
        plot_comparison(ordered, f"{tech} Attenuation — 64ms 5IO", str(out))


# ── Helper: Seamless Handover ─────────────────────────────────────────────
def _compare_handover():
    print("\n--- Seamless Handover: BT vs WLAN ---")
    d = {}
    for tech, folder in [("BT", "P4_Seamless_Handover"), ("WLAN", "P4_seamless_handover")]:
        p = BASE / tech / folder
        if p.exists():
            csvs = list(p.glob("*End2End_latencies.csv"))
            if csvs:
                d[f"{tech} Handover"] = str(csvs[0])
    # Add baseline references FIRST, then handover traces
    ordered = {}
    for tech in ("BT", "WLAN"):
        bl = BASE / tech / "P1_Baseline" / "64ms"
        bl_csvs = list(bl.glob("*End2End_latencies.csv"))
        if bl_csvs:
            ordered[f"{tech} Baseline"] = str(bl_csvs[0])
    ordered.update(d)
    if len(ordered) >= 2:
        out = PLOTS_DIR / "Seamless_Handover" / "Handover_BT_vs_WLAN.svg"
        plot_comparison(ordered, "Seamless Handover — BT vs WLAN (64ms)", str(out))


# ── Helper: Wired configs ─────────────────────────────────────────────────
def _compare_wired():
    print("\n--- Wired: Config Comparison ---")
    d = {}
    for wc, label in [("NoPRP", "No PRP"), ("PRP", "PRP"), ("SeriePRP/NoCablePulls", "Series PRP")]:
        wp = BASE / "Wired" / wc
        csvs = list(wp.glob("*End2End_latencies.csv"))
        if csvs:
            d[label] = str(csvs[0])
    if len(d) >= 2:
        out = PLOTS_DIR / "Wired" / "Wired_Config_Comparison.svg"
        plot_comparison(d, "Wired — PRP Configuration Comparison (64ms)", str(out))


# ═══════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    os.makedirs(PLOTS_DIR, exist_ok=True)
    print(f"Base directory: {BASE}")
    print(f"Plots output : {PLOTS_DIR}")

    # generate_individual_plots()
    generate_comparison_plots()

    print("\n" + "="*60)
    print("  ALL PLOTS GENERATED SUCCESSFULLY")
    print("="*60)
