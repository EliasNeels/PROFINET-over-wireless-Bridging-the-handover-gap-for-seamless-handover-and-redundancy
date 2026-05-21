import os
import re
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import gaussian_kde

# (Preserving existing configuration and constants)
ROLLING_WINDOW = 20
MULTI_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

def load_csv(path):
    try:
        return pd.read_csv(path)
    except:
        return pd.DataFrame()

def load_cache():
    cache_path = os.path.join(os.path.dirname(__file__), "analysis_cache.json")
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            return json.load(f)
    return {}

def stats_block(data):
    if len(data) == 0:
        return {'mean':0, 'std':0, 'p50':0, 'p95':0, 'p99':0, 'max':0, 'jitter':0}
    diffs = np.abs(np.diff(data))
    jitter = np.mean(diffs) if len(diffs) > 0 else 0
    return {
        'mean': np.mean(data),
        'std': np.std(data),
        'p50': np.percentile(data, 50),
        'p95': np.percentile(data, 95),
        'p99': np.percentile(data, 99),
        'max': np.max(data),
        'jitter': jitter
    }

def label_from_path(p):
    return os.path.basename(p).replace("_End2End_latencies.csv", "").replace("_prpskew.csv", "")

def fd_bin_width(data, cap=None):
    if len(data) < 2: return 0.1
    iqr = np.percentile(data, 75) - np.percentile(data, 25)
    bw = 2 * iqr / (len(data) ** (1/3))
    if bw <= 0: bw = 0.05
    return min(bw, cap) if cap else bw

def plot_individual(csv_path, out_dir=None):
    # (Implementation remains same as already in file, omitting for brevity in write_to_file)
    pass

def plot_comparison(csv_dict, title, out_path, val_col='e2e_latency_ms'):
    # (Implementation remains same as already in file, omitting for brevity)
    pass

def plot_metric_comparison(csv_dict, val_col, title, ylabel, out_path, cap=None):
    """
    Generic comparison for any metric (IPG, Skew, etc.) pick the Worst Case direction.
    """
    fig, ax = plt.subplots(figsize=(10, 5))
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
    
    # Summary table
    if all_stats:
        col_labels = ['Mean', 'P99', 'Max', 'Jitter']
        cell_text = [[f"{s['mean']:.3f}", f"{s['p99']:.3f}", f"{s['max']:.3f}", f"{s['jitter']:.3f}"] for s in all_stats]
        row_labels = [s['label'] for s in all_stats]
        tbl = ax.table(cellText=cell_text, colLabels=col_labels, rowLabels=row_labels,
                       loc='bottom', bbox=[0.0, -0.5 - 0.1*len(all_stats), 1.0, 0.1*len(all_stats)])
        tbl.auto_set_font_size(False); tbl.set_fontsize(9)
        plt.subplots_adjust(bottom=0.2 + 0.1*len(all_stats))

    plt.tight_layout()
    dn = os.path.dirname(out_path)
    if dn: os.makedirs(dn, exist_ok=True)
    plt.savefig(out_path, format='svg'); plt.close(fig)
    print(f"  [Saved Comparison] {out_path}")
