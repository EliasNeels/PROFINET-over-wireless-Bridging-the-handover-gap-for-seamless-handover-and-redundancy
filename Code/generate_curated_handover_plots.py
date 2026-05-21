#!/usr/bin/env python3
"""
generate_curated_handover_Plots_NoTable.py
==================================
Generates high-resolution academic-grade timeline (time series) Plots_NoTable
for Bluetooth (BT) and Wi-Fi (WLAN) seamless handover measurements,
compares them against their respective 64ms baseline averages,
places interval markers, shades the dead zones, and converts to PDF.
"""
import os
import re
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cairosvg

# --- Configure Styling to match Thesis Guidelines ---
plt.rcParams.update({
    "text.usetex": False,
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"],
    "mathtext.fontset": "dejavusans",
    "font.size": 14, 
    "axes.labelsize": 16,
    "axes.titlesize": 18,
    "legend.fontsize": 12,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "figure.titlesize": 20,
    "grid.alpha": 0.3,
    "figure.dpi": 300,
    "savefig.bbox": 'tight',
    "savefig.pad_inches": 0.15,
    "svg.fonttype": 'none',
})
plt.style.use('seaborn-v0_8-whitegrid')

# Colors
COLORS_DIR = ['#1f77b4', '#ff7f0e']  # PLC->IO, IO->PLC
COLOR_BASELINE = '#2ca02c'            # Baseline (Green)
ROLLING_WINDOW = 100                  # Rolling window for smooth average

ROOT = Path(r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis")
OUT_DIR = ROOT / "Plots_NoTable" / "Handover_Comparison"
os.makedirs(OUT_DIR, exist_ok=True)
LATEX_FIGS = ROOT / "Latex" / "KU-Leuven-master-thesis-template-FET" / "figs" / "results"
os.makedirs(LATEX_FIGS, exist_ok=True)

def load_data(csv_path):
    if not csv_path.exists():
        print(f"  [Error] File not found: {csv_path}")
        return None
    df = pd.read_csv(csv_path)
    df['rel_time_s'] = df['rel_time_s'].astype(float)
    df['e2e_latency_ms'] = df['e2e_latency_ms'].astype(float)
    return df

def generate_handover_plot(tech, csv_path, baseline_path, interval_s, output_filename, is_wifi=False):
    print(f"\nProcessing {tech} Handover plot...")
    df = load_data(csv_path)
    df_base = load_data(baseline_path)
    
    if df is None:
        return
        
    base_mean = df_base['e2e_latency_ms'].mean() if df_base is not None else (0.59 if is_wifi else 6.77)
    print(f"  Baseline E2E Latency Mean: {base_mean:.4f} ms")
    
    # Filter directions and remove unneeded phases to keep both Plots_NoTable uniform
    if is_wifi:
        # Filter WLAN to PLC -> IO (closest to baseline mean 0.59 ms)
        df = df[df['direction'] == 'PLC -> IO']
        # Remove the "Both Connected" phase (0s - 240s) so it starts directly with A pulled
        df = df[df['rel_time_s'] >= 240.0].copy()
        # Shift relative time by -240s so the X-axis starts exactly at 0
        df['rel_time_s'] = df['rel_time_s'] - 240.0
    else:
        # Filter BT to IO -> PLC (closest to baseline mean 6.05 ms)
        df = df[df['direction'] == 'IO -> PLC']
        
    # Calculate rolling mean
    directions = df['direction'].unique()
    
    # Setup Figure
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Scatter data and plot rolling mean
    for idx, d in enumerate(directions):
        sub_df = df[df['direction'] == d].sort_values('rel_time_s')
        color = COLORS_DIR[idx % len(COLORS_DIR)]
        
        # Keep legend anonymous and generic
        scatter_label = "Packets"
        mean_label = "Rolling Mean"
        
        # 1. Scatter latency points (very small, high transparency to prevent clutter)
        ax.scatter(sub_df['rel_time_s'], sub_df['e2e_latency_ms'], 
                   color=color, alpha=0.12, s=3.5, label=scatter_label, rasterized=True)
        
        # 2. Rolling mean curve
        if len(sub_df) >= ROLLING_WINDOW:
            rm = sub_df['e2e_latency_ms'].rolling(ROLLING_WINDOW, center=True).mean()
            # Choose a darker complementary color for rolling mean
            rm_color = 'navy' if idx == 0 else 'darkred'
            ax.plot(sub_df['rel_time_s'], rm, color=rm_color, lw=2.5, label=mean_label)

    # 3. Horizontal baseline line
    ax.axhline(base_mean, color=COLOR_BASELINE, linestyle='--', linewidth=2.0, 
               label=f"Baseline Mean ({base_mean:.2f} ms)")
    
    # 4. Vertical Phase lines & shading shifted to align with physical blackout times
    max_time = df['rel_time_s'].max()
    
    if is_wifi:
        dead_start = 487.2 - 240.0
        dead_end = 721.0 - 240.0
        phase_boundaries = [dead_start, dead_end, 720.0]
        
        # Center points for text annotations (shifted by -240s to start at 0)
        phases = [
            (dead_start/2, "Phase 1\nPull Line A"),
            ((dead_start + dead_end)/2, "Phase 2\nPull Both"),
            ((dead_end + 720.0)/2, "Phase 3\nPull Line B"),
            ((720.0 + max_time)/2, "Phase 4\nBoth Restored")
        ]
    else:
        dead_start = 329.9
        dead_end = 614.3
        phase_boundaries = [dead_start, dead_end, 900.0]
        
        # Center points for text annotations
        phases = [
            (dead_start/2, "Phase 1\nPull Line A"),
            ((dead_start + dead_end)/2, "Phase 2\nPull Both"),
            ((dead_end + 900.0)/2, "Phase 3\nPull Line B"),
            ((900.0 + max_time)/2, "Phase 4\nBoth Restored")
        ]
    
    # Draw transparent red/gray region for the interruption phase (aligns exactly with no-comm zone)
    ax.axvspan(dead_start, dead_end, color='#d62728', alpha=0.08, label='Both Pulled (Interruption)')
    
    # Add vertical dashed lines for each phase change (aligns with actual physical pull times)
    for x_val in phase_boundaries:
        if x_val < max_time:
            ax.axvline(x_val, color='grey', linestyle=':', alpha=0.8, linewidth=1.5)
        
    # Phase text annotations at the top of the plot
    # We will compute safe vertical positions
    y_max = 1.0 if is_wifi else 20.0  # Wi-Fi is zoomed in way more (1.0 ms) to see detailed variance!
    ax.set_ylim(0, y_max)
    text_y = y_max * 0.90
        
    for x_center, label in phases:
        if x_center < max_time:
            ax.text(x_center, text_y, label, ha='center', va='center', 
                    fontsize=11, fontweight='bold', color='#333333',
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.85))

    # Formatting Title & Labels
    tech_name = "Wi-Fi" if is_wifi else "Bluetooth"
    ax.set_title(f"PROFINET E2E Latency: {tech_name} Seamless Handover (64 ms Cycle Time)", fontsize=18, fontweight='bold', pad=15)
    ax.set_xlabel("Relative Measurement Time (seconds)", fontsize=14, labelpad=10)
    ax.set_ylabel("End-to-End Latency (ms)", fontsize=14, labelpad=10)
    
    ax.set_xlim(0, max_time)
    if is_wifi:
        ax.xaxis.set_major_locator(mticker.MultipleLocator(240))
    else:
        ax.xaxis.set_major_locator(mticker.MultipleLocator(150))
    ax.xaxis.set_minor_locator(mticker.AutoMinorLocator(2))
    
    ax.legend(loc='lower left', frameon=True, framealpha=0.9, facecolor='white', edgecolor='gray')
    ax.grid(True, which='both', linestyle='--', alpha=0.5)
    
    # Save SVG
    svg_path = OUT_DIR / f"{output_filename}.svg"
    plt.savefig(svg_path, format='svg')
    print(f"  [Saved SVG] {svg_path}")
    
    # Also save directly in original folders to replace outdated versions
    orig_dir = ROOT / ("WLAN/P4_seamless_handover" if is_wifi else "BT/P4_Seamless_Handover")
    orig_svg_path = orig_dir / f"{output_filename}.svg"
    plt.savefig(orig_svg_path, format='svg')
    print(f"  [Saved Original Folder SVG] {orig_svg_path}")
    
    plt.close(fig)
    
    # Convert to PDF for LaTeX inclusion
    pdf_path = LATEX_FIGS / f"{output_filename}.pdf"
    try:
        cairosvg.svg2pdf(url=str(svg_path), write_to=str(pdf_path))
        print(f"  [Converted to PDF] {pdf_path}")
    except Exception as e:
        print(f"  [Error during PDF conversion] {e}")

def main():
    # 1. Bluetooth Handover Paths
    bt_csv = ROOT / "BT" / "P4_Seamless_Handover" / "BT_64ms_SeamlessHandover_PullA_PullBoth_PullB_Both_5minInterval_End2End_latencies.csv"
    bt_base = ROOT / "BT" / "P1_Baseline" / "64ms" / "BT_64ms_Base_End2End_latencies.csv"
    bt_out_name = "BT_64ms_SeamlessHandover_PullA_PullBoth_PullB_Both_5minInterval_End2End_E2E_Plot"
    
    # 2. WLAN Handover Paths
    wlan_csv = ROOT / "WLAN" / "P4_seamless_handover" / "WLAN_64ms_SeamlessHandover_PullA_PullBoth_PullB_Both_4minInterval_End2End_latencies.csv"
    wlan_base = ROOT / "WLAN" / "P1_Baseline" / "64ms" / "WLAN_64ms_Base_End2End_latencies.csv"
    wlan_out_name = "WLAN_64ms_SeamlessHandover_PullA_PullBoth_PullB_Both_4minInterval_End2End_E2E_Plot"
    
    # Generate Bluetooth Handover Plot (5min interval = 300s)
    generate_handover_plot("BT", bt_csv, bt_base, 300, bt_out_name, is_wifi=False)
    
    # Generate WLAN Handover Plot (4min interval = 240s)
    generate_handover_plot("WLAN", wlan_csv, wlan_base, 240, wlan_out_name, is_wifi=True)
    
    print("\nAll curated handover timeline Plots_NoTable generated successfully!")

if __name__ == "__main__":
    main()
