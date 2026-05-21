"""
plot_engine.py — Reusable plotting primitives for thesis graphs.
All individual & comparison plots are driven from CSV latency files.
"""
import os, re
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from scipy.stats import gaussian_kde
from pcap_analyzer import load_cache

# --- Configure Fonts to match LaTeX (Sans-Serif Style) ---
plt.rcParams.update({
    "text.usetex": False,
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"],
    "mathtext.fontset": "dejavusans", # More robust for symbols like mu
    "font.size": 20, 
    "axes.labelsize": 22,
    "axes.titlesize": 24,
    "legend.fontsize": 18,
    "xtick.labelsize": 18,
    "ytick.labelsize": 18,
    "figure.titlesize": 26,
    "grid.alpha": 0.3,
    "figure.dpi": 300,
    "savefig.bbox": 'tight',
    "savefig.pad_inches": 0.2,
    "svg.fonttype": 'none',
    "lines.linewidth": 3.0,
    "axes.linewidth": 1.5,
    "patch.linewidth": 1.5,
})

# ── Thesis-grade style ────────────────────────────────────────────────────
plt.style.use('seaborn-v0_8-whitegrid')

COLORS_DIR = ['#1f77b4', '#ff7f0e']  # PLC->IO, IO->PLC
ROLLING_WINDOW = 50
MIN_BIN_WIDTH_MS = 0.001

# ── Helpers ───────────────────────────────────────────────────────────────
def load_csv(path):
    df = pd.read_csv(path)
    if 'e2e_latency_ms' in df.columns:
        df['e2e_latency_ms'] = df['e2e_latency_ms'].astype(float)
    df['rel_time_s'] = df['rel_time_s'].astype(float)
    return df

def fd_bin_width(data, cap=0.1):
    q25, q75 = np.percentile(data, [25, 75])
    iqr = q75 - q25
    n = len(data)
    fd = (2 * iqr / (n ** (1/3))) if (iqr > 0 and n > 0) else cap
    return max(MIN_BIN_WIDTH_MS, min(fd, cap))

def plot_metric_comparison(csv_dict, column_name, title, ylabel, out_path, cap=0.5):
    """
    General purpose comparison for Skew or IPG metrics.
    csv_dict: {label: csv_path, ...}
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(title, fontsize=15, y=1.05)

    all_data = []
    for idx, (label, csv_path) in enumerate(csv_dict.items()):
        df = load_csv(csv_path)
        if column_name not in df.columns:
            continue
        data = df[column_name].values
        if len(data) == 0:
            continue
        color = MULTI_COLORS[idx % len(MULTI_COLORS)]
        
        # 1) Histogram overlay
        bw = fd_bin_width(data, cap=cap)
        axes[0].hist(data, bins=np.arange(data.min(), data.max() + bw, bw), 
                     alpha=0.4, color=color, label=label, density=True)
        
        all_data.append({'label': label, 'data': data, 'color': color})

    if not all_data:
        plt.close(fig)
        return

    axes[0].set(title=f'{column_name} Distribution Overlay', xlabel=ylabel, ylabel='Density')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # 2) Box plot comparison
    bp_data = [d['data'] for d in all_data]
    bp_labels = [d['label'] for d in all_data]
    bp = axes[1].boxplot(bp_data, labels=bp_labels, patch_artist=True, showfliers=False)
    for patch, d in zip(bp['boxes'], all_data):
        patch.set_facecolor(d['color'])
        patch.set_alpha(0.5)
    
    axes[1].set(title=f'{column_name} Summary', ylabel=ylabel)
    axes[1].tick_params(axis='x', rotation=30)
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, format='svg')
    plt.close(fig)
    print(f"  [Saved Comparison] {out_path}")

def compute_jitter_mean_abs_diff(lats):
    if len(lats) < 2:
        return 0.0
    return float(np.mean(np.abs(np.diff(lats))))

def stats_block(lats):
    return {
        'n': len(lats), 'mean': np.mean(lats), 'std': np.std(lats, ddof=1),
        'min': np.min(lats), 'max': np.max(lats),
        'p50': np.percentile(lats, 50), 'p95': np.percentile(lats, 95),
        'p99': np.percentile(lats, 99), 'p999': np.percentile(lats, 99.9),
        'jitter': compute_jitter_mean_abs_diff(lats),
        'loss_pct': lats.get('Packet Loss (%)', 0.0) if hasattr(lats, 'get') else 0.0
    }

import re

def label_from_path(csv_path):
    stem = os.path.splitext(os.path.basename(csv_path))[0].replace('_latencies', '')
    
    if "NoUDP" in stem:
        stem = stem.replace("5IO_NoUDP", "5IO").replace("NoUDP", "5IO")
    elif "UDP" in stem or "M" in stem:
        match = re.search(r'([0-9]+(?:,[0-9]+)?)M', stem, re.IGNORECASE)
        if match:
            mbps = match.group(1)
            stem = re.sub(r'5IO_.*?M.*?(?:_|$)', f'5IO + UDP {mbps} Mbps_', stem)
            stem = stem.rstrip('_')
        else:
            stem = re.sub(r'5IO_.*?UDP', '5IO + UDP', stem)
            
    return stem.replace('_', ' ')


# ═══════════════════════════════════════════════════════════════════════════
#  PLOT TYPE 1: Individual 6-panel analysis (matches notebook style)
# ═══════════════════════════════════════════════════════════════════════════
def plot_individual(csv_path, out_dir=None):
    """6-panel combo plot for a single End2End CSV, saved next to CSV."""
    df = load_csv(csv_path)
    if df.empty:
        return
    label = label_from_path(csv_path)
    if out_dir is None:
        out_dir = os.path.dirname(csv_path)

    # Extract cycle time from filename (e.g., '64ms' -> 64)
    ct_match = re.search(r'(\d+)ms', os.path.basename(csv_path))
    cycle_time_ms = int(ct_match.group(1)) if ct_match else 64

    # Lookup cache for packet loss
    cache = load_cache()
    pcap_path = str(csv_path).replace("_latencies.csv", ".pcap")
    cached_loss = cache.get(pcap_path, {}).get('metrics', {}).get('Packet Loss (%)', 0.0)
    if cached_loss == "": cached_loss = 0.0
    cached_loss = float(cached_loss)

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()
    fig.suptitle(f'PROFINET End-to-End Latency: {label}', fontsize=18, y=1.002)

    streams = list(df.groupby('direction'))
    all_lats = df['e2e_latency_ms'].values
    zoom_xmin = np.percentile(all_lats, 0.5)
    zoom_xmax = np.percentile(all_lats, 99) * 1.10

    for (direction, vdf), color in zip(streams, COLORS_DIR):
        lats = vdf['e2e_latency_ms'].values
        lats_sorted = np.sort(lats)
        n = len(lats)
        if n == 0:
            continue

        s = stats_block(lats)
        bw_zoom = fd_bin_width(lats, cap=0.1)
        bw_full = fd_bin_width(lats, cap=0.5)
        line_c = 'navy' if color == COLORS_DIR[0] else 'darkred'

        # ── 1) Time series + rolling mean ─────────────────────────────────
        axes[0].plot(vdf['rel_time_s'], lats, '.', ms=2.5, alpha=0.25,
                     color=color, label=f'{direction}')
        if n >= ROLLING_WINDOW:
            rm = vdf['e2e_latency_ms'].rolling(ROLLING_WINDOW, center=True).mean()
            axes[0].plot(vdf['rel_time_s'], rm, color=line_c, lw=2.5,
                         label=f'{direction} rolling mean')

        # ── 2) Zoomed histogram + KDE ─────────────────────────────────────
        zd = lats[(lats >= zoom_xmin) & (lats <= zoom_xmax)]
        if len(zd) > 1:
            bins = np.arange(zd.min(), zd.max() + bw_zoom, bw_zoom)
            axes[1].hist(zd, bins=bins, alpha=0.45, color=color, density=True, label=direction)
            kde = gaussian_kde(zd, bw_method='silverman')
            xs = np.linspace(zoom_xmin, zoom_xmax, 800)
            axes[1].plot(xs, kde(xs), color=color, lw=2.0)
            axes[1].axvline(s['mean'], color=color, ls='--', lw=1.2,
                            label=f"mean {s['mean']:.3f} ms")

        # ── 3) Full-range log histogram + KDE ─────────────────────────────
        fb = np.arange(0, s['max'] + bw_full, bw_full)
        counts, edges = np.histogram(lats, bins=fb)
        cp = counts.astype(float); cp[cp == 0] = np.nan
        axes[2].bar(edges[:-1], cp, width=bw_full, align='edge', alpha=0.45,
                    color=color, label=direction)
        axes[2].set_yscale('log')
        if n > 5:
            kde_f = gaussian_kde(lats, bw_method='silverman')
            x_f = np.linspace(max(0, s['min']), s['max'], 1000)
            kde_v = kde_f(x_f) * n * bw_full
            kde_m = np.where(kde_v >= 1.0, kde_v, np.nan)
            axes[2].plot(x_f, kde_m, color=color, lw=2.0)
        axes[2].axvline(s['p99'], color=color, ls=':', lw=1.2, label=f"P99 {s['p99']:.3f}")
        axes[2].axvline(s['p999'], color=color, ls='--', lw=1.2, label=f"P99.9 {s['p999']:.3f}")

        # ── 4) CCDF ──────────────────────────────────────────────────────
        ccdf_y = np.arange(n, 0, -1) / n
        axes[3].step(lats_sorted, ccdf_y, where='post', alpha=0.85,
                     color=color, lw=1.2, label=direction)
        axes[3].set_xscale('log'); axes[3].set_yscale('log')
        x_off = 0.02 if color == COLORS_DIR[0] else 0.52
        std_pct = (s['std'] / cycle_time_ms) * 100.0
        jitter_pct = (s['jitter'] / cycle_time_ms) * 100.0
        txt = (f"{direction}\n{'─'*32}\n"
               f"Std (Jitter)     : {s['std']:>8.3f} ms ({std_pct:.2f}%)\n"
               f"RFC 3550 (Jitter): {s['jitter']:>8.3f} ms ({jitter_pct:.2f}%)\n"
               f"P50              : {s['p50']:>8.3f} ms\n"
               f"P95              : {s['p95']:>8.3f} ms\n"
               f"P99              : {s['p99']:>8.3f} ms\n"
               f"Max              : {s['max']:>8.3f} ms")
        axes[3].text(x_off, 0.04, txt, transform=axes[3].transAxes, fontsize=6.5,
                     va='bottom', horizontalalignment='left', fontfamily='monospace',
                     bbox=dict(boxstyle='round,pad=0.45', fc='white', ec=color, alpha=0.88))
        
        # ── 5) Rolling std ────────────────────────────────────────────────
        if n >= ROLLING_WINDOW:
            rs = vdf['e2e_latency_ms'].rolling(ROLLING_WINDOW, center=True).std(ddof=1)
            axes[4].plot(vdf['rel_time_s'], rs, color=color, lw=1.2, alpha=0.85,
                         label=direction)
        axes[4].axhline(s['jitter'], color=color, ls='--', lw=1.0, alpha=0.7,
                        label=f"Jitter={s['jitter']:.3f} ms")

        # ── 6) Rolling jitter (mean |ΔL|) ────────────────────────────────
        if n >= ROLLING_WINDOW:
            diffs = np.abs(np.diff(lats))
            rj = pd.Series(diffs).rolling(ROLLING_WINDOW, center=True).mean()
            t_j = vdf['rel_time_s'].values[1:]
            axes[5].plot(t_j, rj, color=color, lw=1.5, alpha=0.85,
                         label=f'{direction} (rolling)')
            axes[5].axhline(s['jitter'], color=color, ls='--', lw=1.2,
                            label=f"mean |ΔL| = {s['jitter']:.3f} ms")

    # ── Axis formatting ──────────────────────────────────────────────────
    ymax_ts = np.percentile(all_lats, 99.9) * 1.20
    axes[0].set_ylim(bottom=0, top=ymax_ts)
    axes[0].set(title='Latency over time + rolling mean', xlabel='Time (s)', ylabel='Latency (ms)')
    axes[0].legend(fontsize=9, loc='upper right', markerscale=3); axes[0].grid(True, alpha=0.5)

    axes[1].set_xlim(zoom_xmin, zoom_xmax)
    axes[1].set(title=f'Zoomed histogram + KDE (p0.5–p99)', xlabel='Latency (ms)', ylabel='Density')
    axes[1].legend(fontsize=9, loc='upper right'); axes[1].grid(True, alpha=0.5)
    axes[1].xaxis.set_minor_locator(mticker.AutoMinorLocator())

    axes[2].set(title='Full-range log histogram', xlabel='Latency (ms)', ylabel='Count (log)')
    axes[2].set_ylim(bottom=0.5); axes[2].grid(True, which='both', ls='--', alpha=0.4)
    axes[2].legend(fontsize=9, loc='upper right')

    axes[3].set(title='CCDF (log-log) — P(latency > x)', xlabel='Latency (ms)', ylabel='P(exceed)')
    axes[3].set_ylim(bottom=1e-4); axes[3].grid(True, which='both', ls='--', alpha=0.4)
    axes[3].legend(fontsize=9, loc='upper right')
    
    formatter = mticker.ScalarFormatter()
    formatter.set_scientific(False)
    axes[3].xaxis.set_major_formatter(formatter)
    axes[3].xaxis.set_minor_formatter(formatter)

    axes[4].set(title=f'Rolling std (σ, {ROLLING_WINDOW}-pkt)', xlabel='Time (s)', ylabel='Std dev (ms)')
    axes[4].legend(fontsize=8, loc='upper right'); axes[4].grid(True, alpha=0.5)

    axes[5].set(title='Rolling jitter mean(|ΔL|)', xlabel='Time (s)', ylabel='Jitter (ms)')
    axes[5].legend(fontsize=8, loc='upper right'); axes[5].grid(True, alpha=0.5)

    # ── Dedicated Packet Loss Table (Neatly above the stats boxes) ──────
    actual_loss = cache.get(pcap_path, {}).get('metrics', {}).get("Packet Loss (%)", "0.00")
    loss_table_text = [[f"{actual_loss}%"]]
    loss_table = axes[3].table(cellText=loss_table_text, colLabels=["PNIO Loss"],
                               loc='lower left', cellLoc='center', bbox=[0.05, 0.35, 0.2, 0.12])
    loss_table.auto_set_font_size(False)
    loss_table.set_fontsize(7)
    for cell in loss_table.get_celld().values():
        cell.get_text().set_color('darkred')
        cell.get_text().set_weight('bold')
        cell.set_alpha(0.95)

    plt.tight_layout(rect=[0, 0, 1, 0.995])
    out = os.path.join(out_dir, os.path.basename(csv_path).replace('_latencies.csv', '_E2E_Plot.svg'))
    plt.savefig(out, format='svg'); plt.close(fig)
    print(f"  [Saved] {out}")
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  PLOT TYPE 2: Multi-trace overlay (compare cycle times, load rates, etc.)
# ═══════════════════════════════════════════════════════════════════════════
MULTI_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

print("DEBUG: plot_engine.py loaded (v3)")

def plot_comparison(csv_dict, title, out_path, direction_filter=None, cycle_time_ms=64.0, split_groups=None, hist_dual_x=True, hist_xlim=None, hist_dual_y=False, box_dual_y=False, ccdf_dual_x=False, hist_xlim_primary=None, split_groups_ccdf=None, ccdf_log_x=False, secondary_color=None, hist_ylim_primary=None, primary_ylabel=None, hist_dual_both=False, hist_ylim_secondary=None, include_table=False):
    """
    Generates a 2x2 comparison plot (CCDF, Hist, Box, Mean/Max).
    split_groups: list of two lists of labels, e.g. [['16ms', '128ms'], ['32ms', '64ms']]
    hist_dual_x: If True, uses dual-axis for the histogram X-axis when split_groups is active.
    hist_dual_y: If True, uses dual-axis for the histogram Y-axis (Density) when split_groups is active.
    hist_xlim: Optional (min, max) for the histogram x-axis.
    """
    num_traces = len(csv_dict)
    
    if include_table:
        base_plot_height = 16.0
        table_header_height = 2.0
        table_row_height = 0.8
        table_height = table_header_height + (num_traces * table_row_height)
        total_height = base_plot_height + table_height
        width = 16.0
    else:
        # Larger plot without table
        table_height = 0.0
        total_height = 18.0
        width = 20.0
    
    # Use 16xTotalHeight for a tall, readable layout (or 20x18 if no table)
    fig, axes = plt.subplots(2, 2, figsize=(width, total_height))
    axes = axes.flatten()
    fig.suptitle(title, fontsize=20, fontweight='bold', y=0.98)

    # Base colors
    primary_c = MULTI_COLORS[0]
    sec_c = secondary_color or MULTI_COLORS[2]
    sec_text_c = 'black'  # Force secondary text to black as requested

    first_df = load_csv(next(iter(csv_dict.values())))
    is_skew = 'skew_ms' in first_df.columns
    val_col = 'skew_ms' if is_skew else 'e2e_latency_ms'
    unit_label = 'PRP Skew (μs)' if is_skew else 'Latency (ms)'
    all_stats = []
    
    # Load cache for PNIO loss lookup
    cache = load_cache()
    
    for label, csv_path in csv_dict.items():
        df = load_csv(csv_path)
        if df.empty or val_col not in df.columns:
            continue
            
        # Calculate stats for directions (respecting filter if provided)
        active_filter = direction_filter
        if isinstance(direction_filter, dict):
            active_filter = direction_filter.get(label)

        if active_filter:
            dirs = [active_filter] if 'direction' in df.columns and active_filter in df['direction'].unique() else []
        else:
            dirs = df['direction'].unique() if 'direction' in df.columns else [None]
            
        candidates = []
        
        for d in dirs:
            d_df = df[df['direction'] == d] if d else df
            if d_df.empty: continue
            
            lats = d_df[val_col].values
            s = stats_block(lats)
            
            # Get loss from cache for this specific direction if possible, else the file loss
            pcap_path = str(csv_path).replace("_prpskew.csv", "_End2End.pcap").replace("_latencies.csv", ".pcap")
            s['loss_pct'] = cache.get(pcap_path, {}).get('metrics', {}).get('Packet Loss (%)', 0.0)
            
            s['lats'] = lats
            s['dir_name'] = d
            candidates.append(s)
            
        if candidates:
            # Pick the candidate with the highest P99
            worst_s = max(candidates, key=lambda x: x['p99'])
            worst_s['label'] = label
            worst_s['color'] = MULTI_COLORS[len(all_stats) % len(MULTI_COLORS)]
            
            # Pull dynamic PN base load from the analysis cache and divide by 2 (captured twice)
            pcap_path = str(csv_path).replace("_prpskew.csv", "_End2End.pcap").replace("_latencies.csv", ".pcap")
            dynamic_pn_mbps = cache.get(pcap_path, {}).get('metrics', {}).get('PN Throughput (Mbps)', 0.0) / 2.0

            # Extract target UDP load from the label
            udp_target_mbps = 0.0
            m = re.search(r'UDP\s+([\d.]+)\s*Mbps', label, re.IGNORECASE)
            if m:
                udp_target_mbps = float(m.group(1))

            # Heuristic to detect if UDP traffic was missing from the PCAP (common in WLAN datasets)
            # If measured throughput is significantly lower than the target UDP load, we add the target.
            if "1 IO Baseline" in label:
                worst_s['total_net_mbps'] = 0.0208
            elif "4 IO Load" in label:
                worst_s['total_net_mbps'] = 16 * 0.0208  # 0.3328 Mbps (16x baseline load as requested)
            elif udp_target_mbps > 0 and dynamic_pn_mbps < (udp_target_mbps * 0.8):
                worst_s['total_net_mbps'] = dynamic_pn_mbps + udp_target_mbps
            elif dynamic_pn_mbps > 0.005:
                # Either no UDP load, or it's already accounted for in the PCAP measurement
                worst_s['total_net_mbps'] = dynamic_pn_mbps
            else:
                # Fallback for baseline or cases with missing cache data
                is_1400 = "1400" in title
                if "5IO" in label or "Baseline" in label or "5 (IO-Islands)" in title or "5 IO-Islands" in title:
                    worst_s['total_net_mbps'] = 0.875 if is_1400 else 0.1035
                else:
                    worst_s['total_net_mbps'] = 0.0
            
            # Jitter as percentage of cycle time (both types)
            # Dynamically determine the cycle time of this specific trace from the label or filename
            active_cycle_time = cycle_time_ms
            if "16ms" in label or "16ms" in str(csv_path):
                active_cycle_time = 16.0
            elif "32ms" in label or "32ms" in str(csv_path):
                active_cycle_time = 32.0
            elif "64ms" in label or "64ms" in str(csv_path):
                active_cycle_time = 64.0
            elif "128ms" in label or "128ms" in str(csv_path):
                active_cycle_time = 128.0

            worst_s['jitter_pct'] = (worst_s['jitter'] / active_cycle_time) * 100.0
            worst_s['std_pct'] = (worst_s['std'] / active_cycle_time) * 100.0
            
            # Calculate total packets per second (pps)
            num_devices = 1
            if "5IO" in label or "5 IO" in label or "5 IO-Devices" in title or "5 IO" in title or "5minInterval" in str(csv_path) or "4minInterval" in str(csv_path):
                num_devices = 5
            elif "4 IO" in label or "4IO" in label:
                num_devices = 4
            
            pni_pps = (1000.0 / active_cycle_time) * 2.0 * num_devices
            
            udp_pps = 0.0
            if udp_target_mbps > 0.0:
                is_64B = "64B" in label or "64B" in title or "64B" in str(csv_path)
                is_1400B = "1400B" in label or "1400B" in title or "1400B" in str(csv_path) or "1400" in title
                pkt_sz = 64 if is_64B else (1400 if is_1400B else 0)
                if pkt_sz > 0:
                    udp_pps = (udp_target_mbps * 1000000.0) / (8.0 * pkt_sz)
            
            worst_s['total_pps'] = pni_pps + udp_pps
            
            all_stats.append(worst_s)

        # ── Group assignment for Dual-Axis ──────────────────────────────
        group_idx = 0
        if split_groups:
            if label in split_groups[1]:
                group_idx = 1
        
        # ── CCDF overlay ──────────────────────────────────────────────────
        ls = np.sort(worst_s['lats'])
        ccdf = np.arange(len(ls), 0, -1) / len(ls)

        # ── Group assignment for CCDF ──────────────────────────────
        ccdf_group_idx = group_idx
        if split_groups_ccdf:
            ccdf_group_idx = 0
            if label in split_groups_ccdf[1]:
                ccdf_group_idx = 1

        target_ax_ccdf = axes[0]
        if ccdf_dual_x and (split_groups_ccdf or split_groups) and ccdf_group_idx == 1:
            if not hasattr(axes[0], 'twin_ax'):
                axes[0].twin_ax = axes[0].twiny()
                # Format secondary CCDF X-axis
                axes[0].twin_ax.set_xlabel('Latency (UDP Load) [ms]', color='black', fontsize=16)
                axes[0].twin_ax.tick_params(axis='x', labelcolor='black', labelsize=18)
                axes[0].set_xlabel('Latency (Baseline) [ms]', color=MULTI_COLORS[0], fontsize=16)
                axes[0].tick_params(axis='x', labelcolor=MULTI_COLORS[0], labelsize=18)
            target_ax_ccdf = axes[0].twin_ax
        
        target_ax_ccdf.step(ls, ccdf, where='post', color=worst_s['color'], lw=2.0, label=label, alpha=0.85)

        # ── Histogram overlay + KDE line ──────────────────────────────────
        bw = fd_bin_width(worst_s['lats'], cap=0.15)
        p1, p99 = np.percentile(worst_s['lats'], [1, 99])
        zd = worst_s['lats'][(worst_s['lats'] >= p1) & (worst_s['lats'] <= p99 * 1.05)]
        
        target_ax_hist = axes[1]
        if split_groups and group_idx == 1:
            if hist_dual_x and hist_dual_y:
                if not hasattr(axes[1], 'twin_ax_both'):
                    # Create the twin axes properly
                    twin_y = axes[1].twinx()
                    axes[1].twin_ax_both = twin_y.twiny()
                    
                    # Format the secondary (UDP Load) axes
                    twin_y.set_ylabel('Density (UDP Load)', color='black', fontsize=16)
                    twin_y.tick_params(axis='y', labelcolor='black', labelsize=18)
                    axes[1].twin_ax_both.set_xlabel('Latency (UDP Load) [ms]', color='black', fontsize=16)
                    axes[1].twin_ax_both.tick_params(axis='x', labelcolor='black', labelsize=18)
                    
                    # Format the primary baseline axes
                    axes[1].set_ylabel('Density (Baseline)', color=MULTI_COLORS[0], fontsize=16)
                    axes[1].tick_params(axis='y', labelcolor=MULTI_COLORS[0], labelsize=18)
                    axes[1].set_xlabel('Latency (Baseline) [ms]', color=MULTI_COLORS[0], fontsize=16)
                    axes[1].tick_params(axis='x', labelcolor=MULTI_COLORS[0], labelsize=18)
                    
                    if hist_xlim:
                        axes[1].set_xlim(hist_xlim)
                        axes[1].twin_ax_both.set_xlim(hist_xlim)
                target_ax_hist = axes[1].twin_ax_both
            elif hist_dual_both:
                if not hasattr(axes[1], 'twin_ax_both'):
                    # Create secondary Y first, then secondary X on top of it
                    twin_y = axes[1].twinx()
                    axes[1].twin_ax_both = twin_y.twiny()
                    
                    # Labels for Attenuation vs Load
                    is_atten = "Attenuation" in title
                    primary_tag = "Active Line A" if is_atten else "Baseline"
                    secondary_tag = "Line A OFF" if is_atten else "UDP Load"
                    primary_c = 'black' if is_atten else MULTI_COLORS[0]
                    
                    # Format the secondary axes
                    twin_y.set_ylabel(f'Density ({secondary_tag})', color='black', fontsize=16)
                    twin_y.tick_params(axis='y', labelcolor='black', labelsize=18)
                    axes[1].twin_ax_both.set_xlabel(f'Latency ({secondary_tag}) [ms]', color='black', fontsize=16)
                    axes[1].twin_ax_both.tick_params(axis='x', labelcolor='black', labelsize=18)
                    
                    # Format the primary axes
                    axes[1].set_ylabel(f'Density ({primary_tag})', color=primary_c, fontsize=16)
                    axes[1].tick_params(axis='y', labelcolor=primary_c, labelsize=18)
                    axes[1].set_xlabel(f'Latency ({primary_tag}) [ms]', color=primary_c, fontsize=16)
                    axes[1].tick_params(axis='x', labelcolor=primary_c, labelsize=18)
                    
                    if hist_ylim_secondary:
                        twin_y.set_ylim(hist_ylim_secondary)
                        
                    if hist_xlim:
                        axes[1].twin_ax_both.set_xlim(hist_xlim)
                target_ax_hist = axes[1].twin_ax_both
            elif hist_dual_x:
                if not hasattr(axes[1], 'twin_ax_x'):
                    axes[1].twin_ax_x = axes[1].twiny()
                    # Format secondary X-axis
                    axes[1].twin_ax_x.set_xlabel('Latency (UDP Load) [ms]', color='black', fontsize=16)
                    axes[1].twin_ax_x.tick_params(axis='x', labelcolor='black', labelsize=18)
                    
                    # Format primary X-axis
                    axes[1].set_xlabel('Latency (Baseline) [ms]', color=MULTI_COLORS[0], fontsize=16)
                    axes[1].tick_params(axis='x', labelcolor=MULTI_COLORS[0], labelsize=18)
                target_ax_hist = axes[1].twin_ax_x
            elif hist_dual_y:
                if not hasattr(axes[1], 'twin_ax_y'):
                    axes[1].twin_ax_y = axes[1].twinx()
                    # Color the secondary axis for clarity
                    axes[1].twin_ax_y.set_ylabel('Density (UDP Load)', color='black', fontsize=16)
                    axes[1].twin_ax_y.tick_params(axis='y', labelcolor='black', labelsize=18)
                    axes[1].set_ylabel('Density (Baseline)', color=MULTI_COLORS[0], fontsize=16)
                    axes[1].tick_params(axis='y', labelcolor=MULTI_COLORS[0], labelsize=18)
                    # If xlim is set, ensure it's applied to the secondary axis too if needed
                    if hist_xlim:
                        axes[1].twin_ax_y.set_xlim(hist_xlim)
                target_ax_hist = axes[1].twin_ax_y

        if len(zd) > 1:
            bins = np.arange(zd.min(), zd.max() + bw, bw)
            target_ax_hist.hist(zd, bins=bins, alpha=0.25, color=worst_s['color'], density=True, label=label)
            kde = gaussian_kde(zd, bw_method='silverman')
            xs = np.linspace(zd.min(), zd.max(), 800)
            target_ax_hist.plot(xs, kde(xs), color=worst_s['color'], lw=2.2)

    if not all_stats:
        plt.close(fig)
        return

    # ── Box plot ──────────────────────────────────────────────────────────
    if box_dual_y and split_groups:
        ax1 = axes[2]
        ax2 = ax1.twinx()
        
        indices1 = [i for i, s in enumerate(all_stats) if s['label'] in split_groups[0]]
        indices2 = [i for i, s in enumerate(all_stats) if s['label'] in split_groups[1]]
        
        if indices1:
            data1 = [all_stats[i]['lats'] for i in indices1]
            bp1 = ax1.boxplot(data1, positions=indices1, widths=0.6, patch_artist=True, showfliers=False)
            for patch, idx in zip(bp1['boxes'], indices1):
                patch.set_facecolor(all_stats[idx]['color']); patch.set_alpha(0.5)
        
        if indices2:
            data2 = [all_stats[i]['lats'] for i in indices2]
            bp2 = ax2.boxplot(data2, positions=indices2, widths=0.6, patch_artist=True, showfliers=False)
            for patch, idx in zip(bp2['boxes'], indices2):
                patch.set_facecolor(all_stats[idx]['color']); patch.set_alpha(0.5)
        
        ax1.set_ylabel(f'{unit_label} (Baseline)', color=MULTI_COLORS[0], fontsize=18)
        ax1.tick_params(axis='y', labelcolor=MULTI_COLORS[0])
        ax2.set_ylabel(f'{unit_label} (UDP Load)', color=MULTI_COLORS[2], fontsize=18)
        ax2.tick_params(axis='y', labelcolor=MULTI_COLORS[2])
        
        ax1.set_xlim(-0.5, len(all_stats) - 0.5)
        ax1.set_xticks(range(len(all_stats)))
        ax1.set_xticklabels([s['label'] for s in all_stats], rotation=45)
    else:
        bp_data = [s['lats'] for s in all_stats]
        bp_labels = [s['label'] for s in all_stats]
        bp = axes[2].boxplot(bp_data, labels=bp_labels, patch_artist=True,
                             showfliers=False, widths=0.6)
        for patch, s in zip(bp['boxes'], all_stats):
            patch.set_facecolor(s['color'])
            patch.set_alpha(0.5)
        axes[2].tick_params(axis='x', rotation=45)
    
    axes[2].set_xlabel('', labelpad=30) # Push label/table area down

    # ── Summary bar chart (mean + max) ────────────────────────────────────
    x = np.arange(len(all_stats))
    w = 0.35
    means = [s['mean'] for s in all_stats]
    maxes = [s['max'] for s in all_stats]
    bars1 = axes[3].bar(x - w/2, means, w, label='Mean', color='#2196F3', alpha=0.7)
    bars2 = axes[3].bar(x + w/2, maxes, w, label='Max', color='#F44336', alpha=0.7)
    axes[3].set_xticks(x)
    axes[3].set_xticklabels([s['label'] for s in all_stats], rotation=45, ha='right')
    axes[3].bar_label(bars1, fmt='%.2f', fontsize=20, padding=2)
    axes[3].bar_label(bars2, fmt='%.2f', fontsize=20, padding=2)

    # ── Stats summary table (spanning the full width) ────────────────────
    if include_table:
        col_labels = ['Net Load\n(%/ 100 Mbps cable)', 'Total Rate\n(pps)', 'Mean\n(ms)', 'Max\n(ms)', 'P95\n(ms)', 'P99\n(ms)',
                      'Jitter Std. Dev.\n(% cycle)', 'Jitter RFC 3550\n(% cycle)', 'PNIO\nLoss']
        cell_text = []
        row_labels = []
        row_colors = []
        for s in all_stats:
            row_labels.append(s['label'])
            row_colors.append(s['color'])
            
            net_load_str = f"{s.get('total_net_mbps', 0.0):.4f}%"
            pps_str = f"{s.get('total_pps', 0.0):.1f}"
            cell_text.append([net_load_str, pps_str, f"{s['mean']:.4f}", f"{s['max']:.4f}",
                              f"{s['p95']:.4f}", f"{s['p99']:.4f}",
                              f"{s.get('std_pct', 0.0):.3f}%",
                              f"{s.get('jitter_pct', 0.0):.3f}%",
                              f"{s['loss_pct']:.3f}%"])

        # Adjust layout to make room for table at the bottom
        # Calculate bottom margin as a ratio of table height to total height
        bottom_margin = table_height / total_height
        fig.tight_layout(rect=[0, bottom_margin, 1, 0.96])
        
        # Create a dedicated axis for the table at the bottom of the figure
        table_area_height = bottom_margin - 0.03
        ax_table = fig.add_axes([0.015, 0.02, 0.97, table_area_height])
        ax_table.axis('off')

        tbl = ax_table.table(cellText=cell_text, colLabels=col_labels,
                             rowLabels=row_labels, loc='center', cellLoc='center')
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(14)
        tbl.scale(1.0, 3.2) # Very tall cells for thesis visibility
        for i, rc in enumerate(row_colors):
            # Indexing in table is (row, col). row 0 is header.
            tbl[i + 1, -1].set_facecolor(rc)
            tbl[i + 1, -1].set_alpha(0.3)
    else:
        fig.tight_layout(rect=[0, 0, 1, 0.96])
    
    # Tighter spacing so plots expand
    plt.subplots_adjust(hspace=0.45, wspace=0.3)

    # ── Formatting ────────────────────────────────────────────────────────
    axes[0].set_yscale('log')
    axes[0].set(title='CCDF Comparison', ylabel='P(exceed)')
    axes[0].set_ylim(bottom=1e-4)
    if ccdf_log_x:
        axes[0].set_xscale('log')
        axes[0].set_xlabel('Latency [ms] (Log Scale)', fontsize=18)
        axes[0].grid(True, which="both", ls="-", alpha=0.2)
        axes[0].legend(loc='upper right')
    elif split_groups and hasattr(axes[0], 'twin_ax'):
        axes[0].grid(True, which='both', ls='--', alpha=0.4)
        axes[0].set_xlabel('Latency (Baseline) [ms]', color=MULTI_COLORS[0], fontsize=16)
        axes[0].twin_ax.set_xlabel('Latency (UDP Load) [ms]', color='black', fontsize=16)
        axes[0].tick_params(axis='x', labelcolor=MULTI_COLORS[0], labelsize=18)
        axes[0].twin_ax.tick_params(axis='x', labelcolor='black', labelsize=18)
        
        # Combined legend
        h1, l1 = axes[0].get_legend_handles_labels()
        h2, l2 = axes[0].twin_ax.get_legend_handles_labels()
        ncol = 2 if (len(l1) + len(l2)) > 5 else 1
        axes[0].legend(h1 + h2, l1 + l2, loc='upper right', fontsize=20, ncol=ncol, framealpha=0.8)
    else:
        axes[0].grid(True, which='both', ls='--', alpha=0.4)
        axes[0].set_xlabel(unit_label, fontsize=16)
        axes[0].xaxis.set_major_locator(mticker.AutoLocator())
        axes[0].xaxis.set_minor_locator(mticker.AutoMinorLocator())
        axes[0].xaxis.set_major_formatter(mticker.ScalarFormatter())
        ncol = 2 if len(all_stats) > 5 else 1
        axes[0].legend(loc='upper right', fontsize=20, ncol=ncol, framealpha=0.8)

    # Finalize labels and grid
    is_atten = "Attenuation" in title
    primary_tag = "Active Line A" if is_atten else "Baseline"
    
    final_ylabel = primary_ylabel if primary_ylabel else (f'Density ({primary_tag})' if split_groups else 'Density')
    final_y_color = 'black' if is_atten else (MULTI_COLORS[0] if split_groups else 'black')
    
    axes[1].set_title('Histogram + KDE (p1–p99)', fontsize=16)
    axes[1].set_ylabel(final_ylabel, color=final_y_color, fontsize=16)
    axes[1].tick_params(axis='y', labelcolor=final_y_color, labelsize=18)
    axes[1].tick_params(axis='x', labelsize=18)
    axes[1].grid(True, alpha=0.5)
    
    if hist_ylim_primary:
        axes[1].set_ylim(hist_ylim_primary)
    
    if split_groups:
        h1, l1 = axes[1].get_legend_handles_labels()
        h2, l2 = [], []
        
        if hasattr(axes[1], 'twin_ax_both'):
            h2, l2 = axes[1].twin_ax_both.get_legend_handles_labels()
        elif hasattr(axes[1], 'twin_ax_x'):
            h2, l2 = axes[1].twin_ax_x.get_legend_handles_labels()
            axes[1].twin_ax_x.set_xlabel('Latency (UDP Load) [ms]', color='black')
            axes[1].set_xlabel('Latency (Baseline) [ms]', color=MULTI_COLORS[0])
        elif hasattr(axes[1], 'twin_ax_y'):
            h2, l2 = axes[1].twin_ax_y.get_legend_handles_labels()

        # Combined legend for histogram
        ncol = 2 if (len(l1) + len(l2)) > 5 else 1
        axes[1].legend(h1 + h2, l1 + l2, loc='upper right', fontsize=20, ncol=ncol, framealpha=0.8)
    else:
        ncol = 2 if len(all_stats) > 5 else 1
        axes[1].legend(loc='upper right', fontsize=20, ncol=ncol, framealpha=0.8)
        
    # Apply X-limits to Histogram (always)
    if hist_xlim_primary:
        axes[1].set_xlim(hist_xlim_primary)
    elif hist_xlim:
        axes[1].set_xlim(hist_xlim)

    if hasattr(axes[1], 'twin_ax_both'):
        if hist_xlim:
            axes[1].twin_ax_both.set_xlim(hist_xlim)
    elif hasattr(axes[1], 'twin_ax_x'):
        if hist_xlim:
            axes[1].twin_ax_x.set_xlim(hist_xlim)
    elif hasattr(axes[1], 'twin_ax_y'):
        if hist_xlim:
            axes[1].twin_ax_y.set_xlim(hist_xlim)

    axes[2].set_title('Box Plot (no outliers)', fontsize=16)
    if not (box_dual_y and split_groups):
        axes[2].set_ylabel(unit_label, fontsize=16)
    axes[2].tick_params(axis='both', which='major', labelsize=18)
    axes[2].grid(True, alpha=0.5)

    axes[3].set_title('Mean & Max Latency', fontsize=16)
    axes[3].set_ylabel(unit_label, fontsize=16)
    # axes[3].legend(fontsize=20) # Table axis doesn't usually need a legend
    axes[3].grid(True, alpha=0.5)

    # Final save
    dn = os.path.dirname(out_path)
    if dn:
        os.makedirs(dn, exist_ok=True)
    plt.savefig(out_path, format='svg'); plt.close(fig)
    print(f"  [Saved] {out_path}")

# ═══════════════════════════════════════════════════════════════════════════
#  PLOT TYPE 3: PRP Skew Analysis
# ═══════════════════════════════════════════════════════════════════════════
def plot_prp_skew(csv_path, out_dir=None):
    """Plot PRP Skew timeseries and histogram."""
    df = load_csv(csv_path)
    if 'skew_ms' not in df.columns:
        if 'skew_us' in df.columns:
            df['skew_ms'] = df['skew_us'] / 1000.0
        else:
            df['skew_ms'] = df.iloc[:, 3] # Fallback if named differently
    df['skew_ms'] = df['skew_ms'].astype(float)
    if df.empty:
        return
    label = label_from_path(csv_path)
    if out_dir is None:
        out_dir = os.path.dirname(csv_path)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    fig.suptitle(f'PRP Inter-Frame Skew: {label}', fontsize=16, y=1.05)
    
    skews = df['skew_ms'].values
    color = '#9467bd'
    s = stats_block(skews)
    
    # 1) Time series
    axes[0].plot(df['rel_time_s'], skews, '.', ms=3, alpha=0.5, color=color)
    if len(skews) >= ROLLING_WINDOW:
        rm = df['skew_ms'].rolling(ROLLING_WINDOW, center=True).mean()
        axes[0].plot(df['rel_time_s'], rm, color='indigo', lw=2)
    axes[0].set(title='PRP Skew over time', xlabel='Time (s)', ylabel='Skew (ms)')
    axes[0].grid(True, alpha=0.5)
    
    # 2) Histogram
    bw = fd_bin_width(skews, cap=0.5)
    if np.isclose(skews.min(), skews.max()):
        bins = np.array([skews.min() - bw, skews.max() + bw])
    else:
        bins = np.arange(0, s['max'] + bw, bw)
        if len(bins) < 2:
            bins = np.array([0, s['max'] + bw])
    axes[1].hist(skews, bins=bins, color=color, alpha=0.7)
    axes[1].axvline(s['mean'], color='k', ls='--', label=f"Mean: {s['mean']:.4f}ms")
    axes[1].axvline(s['p99'], color='r', ls=':', label=f"P99: {s['p99']:.4f}ms")
    axes[1].set(title='Skew Distribution', xlabel='Skew (ms)', ylabel='Count')
    axes[1].legend()
    axes[1].grid(True, alpha=0.5)
    
    plt.tight_layout()
    out = os.path.join(out_dir, os.path.basename(csv_path).replace('.csv', '_Plot.svg'))
    plt.savefig(out, format='svg')
    plt.close(fig)
    print(f"  [Saved] {out}")
    return out

# ═══════════════════════════════════════════════════════════════════════════
#  PLOT TYPE 4: Injection Jitter (IPG)
# ═══════════════════════════════════════════════════════════════════════════
def plot_injection_jitter(csv_path, out_dir=None):
    """Plot Inter-Packet Gap (IPG) to show injection jitter."""
    df = load_csv(csv_path)
    if 'ipg_ms' not in df.columns:
        df['ipg_ms'] = df.iloc[:, 3]
    df['ipg_ms'] = df['ipg_ms'].astype(float)
    if df.empty:
        return
    label = label_from_path(csv_path)
    if out_dir is None:
        out_dir = os.path.dirname(csv_path)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    fig.suptitle(f'Injection Inter-Packet Gap (IPG): {label}', fontsize=16, y=1.05)
    
    ipgs = df['ipg_ms'].values
    color = '#2ca02c'
    s = stats_block(ipgs)
    
    # 1) Time series
    axes[0].plot(df['rel_time_s'], ipgs, '.', ms=3, alpha=0.5, color=color)
    axes[0].axhline(s['p50'], color='darkgreen', ls='--', label=f"Median IPG: {s['p50']:.2f}ms")
    axes[0].set(title='IPG over time', xlabel='Time (s)', ylabel='IPG (ms)')
    axes[0].legend()
    axes[0].grid(True, alpha=0.5)
    
    # 2) Histogram
    bw = fd_bin_width(ipgs, cap=0.1)
    lo, hi = ipgs.min(), ipgs.max()
    if np.isclose(lo, hi):
        bins = np.array([lo - bw, hi + bw])
    else:
        bins = np.arange(max(0, lo - bw), hi + bw, bw)
        if len(bins) < 2:
            bins = np.array([lo - bw, hi + bw])
    axes[1].hist(ipgs, bins=bins, color=color, alpha=0.7)
    axes[1].axvline(s['mean'], color='k', ls='--', label=f"Mean: {s['mean']:.3f}ms")
    axes[1].set(title='IPG Distribution', xlabel='IPG (ms)', ylabel='Count')
    axes[1].legend()
    axes[1].grid(True, alpha=0.5)
    
    plt.tight_layout()
    out = os.path.join(out_dir, os.path.basename(csv_path).replace('.csv', '_Plot.svg'))
    plt.savefig(out, format='svg')
    plt.close(fig)
    print(f"  [Saved] {out}")
    return out

def plot_latency_vs_load(latency_csv_path, load_csv_path, title, out_path, is_skew=False):
    """
    Plots Latency or Skew on the left Y-axis and Throughput (Mbps) on the right Y-axis.
    """
    df_lat = load_csv(latency_csv_path)
    df_load = load_csv(load_csv_path)
    if df_lat.empty or df_load.empty:
        return

    fig, ax1 = plt.subplots(figsize=(12, 5))
    fig.suptitle(title, fontsize=16, y=0.95)

    # Plot Latency/Skew (Left Y-axis)
    color_lat = 'tab:blue' if not is_skew else 'tab:red'
    col_name = 'skew_ms' if is_skew else 'e2e_latency_ms'
    ylabel = 'PRP Skew (ms)' if is_skew else 'End-to-End Latency (ms)'
    
    if is_skew:
        ax1.plot(df_lat['rel_time_s'], df_lat[col_name], '.', ms=2.5, color=color_lat, alpha=0.5, label=ylabel)
    else:
        for direction, color in zip(['PLC -> IO', 'IO -> PLC'], ['tab:blue', 'tab:orange']):
            mask = df_lat['direction'] == direction
            if mask.sum() > 0:
                ax1.plot(df_lat[mask]['rel_time_s'], df_lat[mask][col_name], '.', ms=2.5, color=color, alpha=0.5, label=direction)

    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel(ylabel, color='black')
    ax1.tick_params(axis='y', labelcolor='black')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left')

    # Plot Load (Right Y-axis)
    ax2 = ax1.twinx()
    color_load = 'tab:green'
    ax2.plot(df_load['rel_time_s'], df_load['throughput_mbps'], '-', color=color_load, lw=2, drawstyle='steps-post', label='UDP Load (Mbps)')
    ax2.fill_between(df_load['rel_time_s'], df_load['throughput_mbps'], step='post', color=color_load, alpha=0.1)
    ax2.set_ylabel('UDP Throughput (Mbps)', color=color_load)
    ax2.tick_params(axis='y', labelcolor=color_load)
    ax2.set_ylim(bottom=0)
    ax2.legend(loc='upper right')

    plt.tight_layout()
    dn = os.path.dirname(out_path)
    if dn:
        os.makedirs(dn, exist_ok=True)
    plt.savefig(out_path, format='svg')
    plt.close(fig)
    print(f"  [Saved Overlay] {out_path}")

def plot_metric_comparison(csv_dict, val_col, title, ylabel, out_path, cap=None):
    num_traces = len(csv_dict)
    base_height = 6.0
    table_height = 1.0 + (num_traces * 0.4)
    total_height = base_height + table_height
    
    fig, ax = plt.subplots(figsize=(10, total_height))
    all_stats = []
    
    for label, csv_path in csv_dict.items():
        df = load_csv(csv_path)
        if df.empty or val_col not in df.columns:
            continue
            
        # Worst-case direction lookup
        dirs = df['direction'].unique() if 'direction' in df.columns else [None]
        worst_s = None
        
        for d in dirs:
            d_df = df[df['direction'] == d] if d else df
            if d_df.empty: continue
            
            vals = pd.to_numeric(d_df[val_col], errors='coerce').dropna().values
            if len(vals) == 0: continue
            s = stats_block(vals)
            
            if worst_s is None or s['p99'] > worst_s['p99']:
                worst_s = s
                worst_s['vals'] = vals
        
        if worst_s:
            worst_s['label'] = label
            worst_s['color'] = MULTI_COLORS[len(all_stats) % len(MULTI_COLORS)]
            all_stats.append(worst_s)
            
            sns.kdeplot(worst_s['vals'], ax=ax, label=label, color=worst_s['color'], lw=2)

    ax.set(title=title, xlabel=ylabel, ylabel='Density')
    if cap: ax.set_xlim(0, cap)
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    if all_stats:
        col_labels = ['Mean', 'P99', 'Max', 'Jitter']
        cell_text = [[f"{s['mean']:.3f}", f"{s['p99']:.3f}", f"{s['max']:.3f}", f"{s['jitter']:.3f}"] for s in all_stats]
        row_labels = [s['label'] for s in all_stats]
        
        # Calculate bottom margin ratio
        bottom_margin = table_height / total_height
        
        # Adjust layout to make room for the table
        fig.tight_layout(rect=[0, bottom_margin, 1, 0.92])
        
        # Create a dedicated axis for the table
        table_area_height = bottom_margin - 0.03
        ax_table = fig.add_axes([0.05, 0.02, 0.9, table_area_height])
        ax_table.axis('off')
        
        tbl = ax_table.table(cellText=cell_text, colLabels=col_labels, rowLabels=row_labels, loc='center', cellLoc='center')
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(11)
        tbl.scale(1.0, 2.0)
    else:
        fig.tight_layout()
    dn = os.path.dirname(out_path)
    if dn: os.makedirs(dn, exist_ok=True)
    plt.savefig(out_path, format='svg'); plt.close(fig)
    print(f"  [Saved Comparison] {out_path}")
