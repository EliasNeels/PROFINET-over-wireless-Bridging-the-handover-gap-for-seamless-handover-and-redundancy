import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from scipy.stats import gaussian_kde
from pcap_analyzer import load_cache

# Styling
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    "text.usetex": False,
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"],
    "mathtext.fontset": "dejavusans", 
    "font.size": 18, 
    "axes.labelsize": 20,
    "axes.titlesize": 22,
    "legend.fontsize": 16,
    "xtick.labelsize": 16,
    "ytick.labelsize": 16,
    "figure.titlesize": 24,
    "grid.alpha": 0.3,
    "figure.dpi": 300,
    "savefig.bbox": 'tight',
    "savefig.pad_inches": 0.15,
    "svg.fonttype": 'none',
})

MULTI_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

def fd_bin_width(data, cap=0.1):
    q25, q75 = np.percentile(data, [25, 75])
    iqr = q75 - q25
    n = len(data)
    fd = (2 * iqr / (n ** (1/3))) if (iqr > 0 and n > 0) else cap
    return max(0.001, min(fd, cap))

def compute_jitter_mean_abs_diff(lats):
    if len(lats) < 2: return 0.0
    return float(np.mean(np.abs(np.diff(lats))))

def stats_block(lats):
    return {
        'n': len(lats), 'mean': np.mean(lats), 'std': np.std(lats, ddof=1),
        'min': np.min(lats), 'max': np.max(lats),
        'p50': np.percentile(lats, 50), 'p95': np.percentile(lats, 95),
        'p99': np.percentile(lats, 99), 'p999': np.percentile(lats, 99.9),
        'jitter': compute_jitter_mean_abs_diff(lats),
    }

def generate_wired_plot():
    ROOT = r"C:\Users\elti5\OneDrive - KU Leuven\MasterThesis"
    OUT_PATH = os.path.join(ROOT, "Plots_NoTable", "Baseline_Comparison", "Wired_Config_Comparison.svg")
    
    csv_files = {
        'Direct (No PRP)': os.path.join(ROOT, "Wired", "NoPRP", "Wire_64ms_NoPRP_End2End_latencies.csv"),
        'Single PRP': os.path.join(ROOT, "Wired", "PRP", "Wire_64ms_PRP_End2End_latencies.csv"),
        'Cascaded PRP': os.path.join(ROOT, "Wired", "SeriePRP", "CablePulls", "Wire_64ms_SeriePRP_PRP2_PullLineAandB_5min5min_End2End_latencies.csv")
    }
    
    cache = load_cache()
    
    all_stats = []
    
    # Process CSVs
    for idx, (label, csv_path) in enumerate(csv_files.items()):
        if not os.path.exists(csv_path): continue
        df = pd.read_csv(csv_path)
        is_skew = 'skew_ms' in df.columns
        val_col = 'skew_ms' if is_skew else 'e2e_latency_ms'
        if val_col not in df.columns: continue
        
        # Determine worst direction
        dirs = df['direction'].unique()
        worst_s = None
        for d in dirs:
            d_df = df[df['direction'] == d]
            lats_ms = d_df[val_col].values
            s = stats_block(lats_ms)
            s['lats_ms'] = lats_ms
            s['lats_us'] = lats_ms * 1000.0  # Convert to microseconds
            
            # Loss and Netload from cache
            pcap_path = csv_path.replace("_latencies.csv", ".pcap")
            if "NoPRP" in pcap_path and not os.path.exists(pcap_path):
                # Handle possible mismatch
                pcap_path = pcap_path.replace("NoPRP\\", "")
                
            c_metrics = cache.get(pcap_path, {}).get('metrics', {})
            s['loss_pct'] = float(c_metrics.get('Packet Loss (%)', 0.0) or 0.0)
            s['net_load'] = float(c_metrics.get('PN Throughput (Mbps)', 0.0) or 0.0) / 2.0
            
            if worst_s is None or s['p99'] > worst_s['p99']:
                worst_s = s
        
        if worst_s:
            worst_s['label'] = label
            worst_s['color'] = MULTI_COLORS[idx % len(MULTI_COLORS)]
            all_stats.append(worst_s)
    
    if not all_stats:
        print("No data found for wired Plots_NoTable.")
        return

    fig, axes = plt.subplots(2, 2, figsize=(16, 20))
    axes = axes.flatten()
    fig.suptitle('Wired Reference Measurements (64ms Cycle and 1 IO-Island)', fontsize=24, y=0.98)
    
    # --- 1) Histogram in microseconds (Dual X and Dual Y Axis) ---
    ax_hist_1 = axes[1]
    ax_tmp = ax_hist_1.twinx()
    ax_hist_2 = ax_tmp.twiny()
    ax_hist_3 = ax_tmp.twiny()
    ax_hist_3.spines['top'].set_position(('outward', 45))
    
    for s in all_stats:
        lats_us = s['lats_us']
        bw_us = fd_bin_width(lats_us, cap=0.5)
        p1, p99 = np.percentile(lats_us, [1, 99.5])
        zd = lats_us[(lats_us >= p1) & (lats_us <= p99 * 1.05)]
        
        if len(zd) > 1:
            bins = np.arange(zd.min(), zd.max() + bw_us, bw_us)
            
            if 'No PRP' in s['label']:
                ax_hist_1.hist(zd, bins=bins, alpha=0.5, color=s['color'], density=True, label=s['label'])
                kde = gaussian_kde(zd, bw_method='silverman')
                xs = np.linspace(zd.min(), zd.max(), 500)
                ax_hist_1.plot(xs, kde(xs), color=s['color'], lw=2)
                ax_hist_1.set_xlim(max(0, zd.min() - 0.05), zd.max() + 0.05)
            elif 'Single PRP' in s['label']:
                ax_hist_2.hist(zd, bins=bins, alpha=0.5, color=s['color'], density=True, label=s['label'])
                kde = gaussian_kde(zd, bw_method='silverman')
                xs = np.linspace(zd.min(), zd.max(), 500)
                ax_hist_2.plot(xs, kde(xs), color=s['color'], lw=2, linestyle='--')
                ax_hist_2.set_xlim(zd.min() - 0.5, zd.max() + 0.5)
            else: # Cascaded
                ax_hist_3.hist(zd, bins=bins, alpha=0.5, color=s['color'], density=True, label=s['label'])
                kde = gaussian_kde(zd, bw_method='silverman')
                xs = np.linspace(zd.min(), zd.max(), 500)
                ax_hist_3.plot(xs, kde(xs), color=s['color'], lw=2, linestyle=':')
                ax_hist_3.set_xlim(zd.min() - 0.5, zd.max() + 0.5)

    ax_hist_1.set_xlabel(r'Latency No PRP ($\mu$s)', color=MULTI_COLORS[0])
    ax_hist_2.set_xlabel(r'Latency Single PRP ($\mu$s)', color=MULTI_COLORS[1])
    ax_hist_3.set_xlabel(r'Latency Cascaded PRP ($\mu$s)', color=MULTI_COLORS[2])
    ax_hist_1.set_ylabel('Density (No PRP)', color=MULTI_COLORS[0])
    ax_tmp.set_ylabel('Density (PRP Variants)', color='#444444')
    
    ax_hist_1.tick_params(axis='x', colors=MULTI_COLORS[0])
    ax_hist_2.tick_params(axis='x', colors=MULTI_COLORS[1])
    ax_hist_3.tick_params(axis='x', colors=MULTI_COLORS[2])
    ax_hist_1.tick_params(axis='y', colors=MULTI_COLORS[0])
    ax_tmp.tick_params(axis='y', colors='#444444')
    
    ax_hist_1.set_title(r'Histogram + KDE ($\mu$s)', pad=80) 
    ax_hist_1.grid(True, alpha=0.3)
    
    # Merge legends
    h1, l1 = ax_hist_1.get_legend_handles_labels()
    h2, l2 = ax_hist_2.get_legend_handles_labels()
    h3, l3 = ax_hist_3.get_legend_handles_labels()
    ax_hist_1.legend(h1 + h2 + h3, l1 + l2 + l3, loc='upper right')
    
    # --- 2) CCDF in microseconds (Triple X Axis) ---
    ax_ccdf_1 = axes[0]
    ax_ccdf_2 = ax_ccdf_1.twiny()
    ax_ccdf_3 = ax_ccdf_1.twiny()
    ax_ccdf_3.spines['top'].set_position(('outward', 45))
    
    for s in all_stats:
        ls_us = np.sort(s['lats_us'])
        ccdf = np.arange(len(ls_us), 0, -1) / len(ls_us)
        if 'No PRP' in s['label']:
            ax_ccdf_1.step(ls_us, ccdf, where='post', color=s['color'], lw=2, label=s['label'])
        elif 'Single PRP' in s['label']:
            ax_ccdf_2.step(ls_us, ccdf, where='post', color=s['color'], lw=2, label=s['label'], linestyle='--')
        else:
            ax_ccdf_3.step(ls_us, ccdf, where='post', color=s['color'], lw=2, label=s['label'], linestyle=':')

    ax_ccdf_1.set_xscale('log'); ax_ccdf_2.set_xscale('log'); ax_ccdf_3.set_xscale('log')
    ax_ccdf_1.set_yscale('log'); ax_ccdf_1.set_ylim(bottom=1e-4)
    
    ax_ccdf_1.set_xlabel(r'Latency No PRP ($\mu$s)', color=MULTI_COLORS[0])
    ax_ccdf_2.set_xlabel(r'Latency Single PRP ($\mu$s)', color=MULTI_COLORS[1])
    ax_ccdf_3.set_xlabel(r'Latency Cascaded PRP ($\mu$s)', color=MULTI_COLORS[2])
    
    ax_ccdf_1.tick_params(axis='x', which='both', colors=MULTI_COLORS[0])
    ax_ccdf_2.tick_params(axis='x', which='both', colors=MULTI_COLORS[1])
    ax_ccdf_3.tick_params(axis='x', which='both', colors=MULTI_COLORS[2])
    
    formatter = mticker.ScalarFormatter(); formatter.set_scientific(False)
    for ax in [ax_ccdf_1, ax_ccdf_2, ax_ccdf_3]:
        ax.xaxis.set_major_formatter(formatter)
        ax.xaxis.set_minor_formatter(formatter)
    
    ax_ccdf_1.set_ylabel('P(exceed)')
    ax_ccdf_1.set_title(r'CCDF Comparison ($\mu$s)', pad=80)
    ax_ccdf_1.grid(True, which='both', ls='--', alpha=0.4)
    
    h1, l1 = ax_ccdf_1.get_legend_handles_labels()
    h2, l2 = ax_ccdf_2.get_legend_handles_labels()
    h3, l3 = ax_ccdf_3.get_legend_handles_labels()
    ax_ccdf_1.legend(h1 + h2 + h3, l1 + l2 + l3, loc='lower left')
    
    # --- 3) Box Plot (in microseconds, Dual Y-Axis) ---
    # --- 3) Box Plot (in microseconds, Triple Y-Axis) ---
    ax_box_1 = axes[2]
    ax_box_2 = ax_box_1.twinx()
    ax_box_3 = ax_box_1.twinx()
    ax_box_3.spines['right'].set_position(('outward', 80))
    
    bp_data_us = [s['lats_us'] for s in all_stats]
    bp_labels = [s['label'] for s in all_stats]
    
    # Create empty datasets for each axis to handle coloring correctly
    bp1_data = [d if 'No PRP' in l else [] for d, l in zip(bp_data_us, bp_labels)]
    bp2_data = [d if 'Single PRP' in l else [] for d, l in zip(bp_data_us, bp_labels)]
    bp3_data = [d if 'Cascaded PRP' in l else [] for d, l in zip(bp_data_us, bp_labels)]
    
    bp1 = ax_box_1.boxplot(bp1_data, tick_labels=bp_labels, patch_artist=True, showfliers=False, widths=0.4)
    bp2 = ax_box_2.boxplot(bp2_data, tick_labels=bp_labels, patch_artist=True, showfliers=False, widths=0.4)
    bp3 = ax_box_3.boxplot(bp3_data, tick_labels=bp_labels, patch_artist=True, showfliers=False, widths=0.4)
    
    for i, s in enumerate(all_stats):
        if 'No PRP' in s['label']:
            bp1['boxes'][i].set_facecolor(s['color']); bp1['boxes'][i].set_alpha(0.6)
            bp1['medians'][i].set_color(s['color']); bp1['medians'][i].set_linewidth(2)
        elif 'Single PRP' in s['label']:
            bp2['boxes'][i].set_facecolor(s['color']); bp2['boxes'][i].set_alpha(0.6)
            bp2['medians'][i].set_color(s['color']); bp2['medians'][i].set_linewidth(2)
        else:
            bp3['boxes'][i].set_facecolor(s['color']); bp3['boxes'][i].set_alpha(0.6)
            bp3['medians'][i].set_color(s['color']); bp3['medians'][i].set_linewidth(2)
            
    ax_box_1.set_ylabel(r'Latency No PRP ($\mu$s)', color=MULTI_COLORS[0])
    ax_box_2.set_ylabel(r'Latency Single PRP ($\mu$s)', color=MULTI_COLORS[1])
    ax_box_3.set_ylabel('Latency Cascaded PRP (μs)', color=MULTI_COLORS[2])
    ax_box_1.tick_params(axis='y', colors=MULTI_COLORS[0])
    ax_box_2.tick_params(axis='y', colors=MULTI_COLORS[1])
    ax_box_3.tick_params(axis='y', colors=MULTI_COLORS[2])
    ax_box_1.set_title('Box Plot (μs)')
    ax_box_1.grid(True, alpha=0.4)
    ax_box_1.tick_params(axis='x', rotation=15)
    ax_box_1.set_xlabel('', labelpad=30)
    
    # --- 4) Summary Table (with Jitter % of 64ms cycle) ---
    cycle_time_ms = 64.0
    col_labels = ['Net Load\n(%/ 100 Mbps cable)', 'Total Rate\n(pps)', 'Mean\n(μs)', 'Max\n(μs)', 'P99\n(μs)', 'Jitter Std. Dev.\n(% cycle)', 'Jitter RFC 3550\n(% cycle)', 'PN Loss\n(%)']
    cell_text = []
    row_labels = []
    row_colors = []
    
    for s in all_stats:
        row_labels.append(s['label'])
        row_colors.append(s['color'])
        
        # Microseconds for absolute values
        mean_us = s['mean'] * 1000.0
        max_us = s['max'] * 1000.0
        p99_us = s['p99'] * 1000.0
        
        # Percentages for jitter
        std_pct = (s['std'] / cycle_time_ms) * 100.0
        rfc_pct = (s['jitter'] / cycle_time_ms) * 100.0
        
        # 1 IO Device, 64ms cycle time -> (1000/64) * 2 = 31.25 pps
        pps_str = f"{(1000.0 / cycle_time_ms) * 2.0 * 1:.1f}"
        
        cell_text.append([
            f"{s['net_load']:.4f}%", pps_str, f"{mean_us:.4f}", f"{max_us:.4f}",
            f"{p99_us:.4f}", f"{std_pct:.4f}%", f"{rfc_pct:.4f}%", f"{s['loss_pct']:.4f}%"
        ])

    # Hide axis 3 to make room for table area
    axes[3].axis('off')

    # Adjust layout to make room for table
    plt.tight_layout(rect=[0, 0.28, 1, 0.96])
    
    # Dedicated table axis
    table_area_height = 0.06 * len(all_stats) + 0.18
    ax_table = fig.add_axes([0.015, 0.02, 0.97, table_area_height])
    ax_table.axis('off')

    tbl = ax_table.table(cellText=cell_text, colLabels=col_labels, rowLabels=row_labels,
                         loc='center', cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(13)
    tbl.scale(1.0, 3.2) # Very tall cells for thesis visibility
    for i, rc in enumerate(row_colors):
        tbl[i + 1, -1].set_facecolor(rc)
        tbl[i + 1, -1].set_alpha(0.3)
        
    plt.subplots_adjust(wspace=0.3, hspace=0.4)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    plt.savefig(OUT_PATH, format='svg')
    plt.close()
    print(f"Generated updated wired plot: {OUT_PATH}")

if __name__ == '__main__':
    generate_wired_plot()
