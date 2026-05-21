#!/usr/bin/env python3
"""Generate consistent plots for End2End latency CSVs.

Scans the workspace for *End2End_latencies.csv, loads each file,
detects whether the latency column is in seconds or milliseconds,
converts to ms, computes Freedman-Diaconis bin widths (with caps from
the notebooks), and produces per-file and per-scenario comparison plots.

Usage: python generate_all_plots.py
"""
import os
import glob
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

ROOT = Path(__file__).parent
OUT_ROOT = ROOT / "Comparison_Plots"
OUT_ROOT.mkdir(exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid")

# Notebook defaults
MIN_BIN_WIDTH_MS = 0.001

def _fd_bin_width(data_ms, zoom_cap=0.1, full_cap=0.5):
    """Compute Freedman-Diaconis bin widths in milliseconds.

    Returns (fd, zoom_bw, full_bw)
    """
    if len(data_ms) < 2:
        return MIN_BIN_WIDTH_MS, MIN_BIN_WIDTH_MS, MIN_BIN_WIDTH_MS
    q75, q25 = np.percentile(data_ms, [75, 25])
    iqr = q75 - q25
    fd = 2 * iqr / (len(data_ms) ** (1 / 3.0))
    fd = float(fd)
    zoom_bw = max(MIN_BIN_WIDTH_MS, min(fd, zoom_cap))
    full_bw = max(MIN_BIN_WIDTH_MS, min(fd, full_cap))
    return fd, zoom_bw, full_bw

def find_latency_files(root: Path):
    pattern = str(root / "**" / "*End2End_latencies.csv")
    return [Path(p) for p in glob.glob(pattern, recursive=True)]

def load_latency_csv(path: Path):
    df = pd.read_csv(path)
    # Expect column 'e2e_latency_ms' but some files store seconds; detect and convert
    if 'e2e_latency_ms' not in df.columns:
        raise ValueError(f"unexpected columns in {path}: {df.columns}")
    lat = df['e2e_latency_ms'].astype(float)
    # Heuristic: if values are all < 1, assume seconds and convert to ms
    if lat.max() < 1.0:
        lat = lat * 1000.0
    df = df.copy()
    df['lat_ms'] = lat
    return df

def scenario_key(path: Path):
    parts = path.parts
    # find top-level folder (BT/WLAN/Wired) and last two folders as scenario
    # e.g. .../BT/P1_Baseline/64ms/... -> ('BT','P1_Baseline','64ms')
    try:
        # find index of BT/WLAN/Wired
        for i, p in enumerate(parts):
            if p in ("BT", "WLAN", "Wired"):
                tech = p
                # get next two parts if available
                scen = []
                if i + 1 < len(parts):
                    scen.append(parts[i+1])
                if i + 2 < len(parts):
                    scen.append(parts[i+2])
                return tech, "/".join(scen)
    except Exception:
        pass
    return parts[0] if parts else "unknown", ""

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def savefig(fig, path: Path):
    ensure_dir(path.parent)
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)

def plot_individual(df, src_path: Path, out_dir: Path):
    lat = df['lat_ms'].dropna().values
    if len(lat) == 0:
        return
    fd, zoom_bw, full_bw = _fd_bin_width(lat)

    # Full-range histogram
    fig, ax = plt.subplots(figsize=(6,4))
    lo, hi = float(lat.min()), float(lat.max())
    if np.isclose(lo, hi):
        bins = np.array([lo - full_bw, hi + full_bw])
    else:
        bins = np.arange(lo, hi + full_bw, full_bw)
        if len(bins) < 2:
            bins = np.array([lo - full_bw, hi + full_bw])
    sns.histplot(lat, bins=bins, stat='density', element='step', fill=True, ax=ax)
    ax.set_xlabel('Latency (ms)')
    ax.set_title(f'Histogram (full) — {src_path.name}')
    savefig(fig, out_dir / (src_path.stem + '_hist_full.png'))

    # Zoom histogram: center near the mode
    center = np.median(lat)
    zoom_span = 5 * zoom_bw if zoom_bw>0 else 1.0
    zmin = max(0, center - 50*zoom_bw)
    zmax = center + 50*zoom_bw
    fig, ax = plt.subplots(figsize=(6,4))
    if np.isclose(zmin, zmax):
        zbins = np.array([zmin - zoom_bw, zmax + zoom_bw])
    else:
        zbins = np.arange(zmin, zmax + zoom_bw, zoom_bw)
        if len(zbins) < 2:
            zbins = np.array([zmin - zoom_bw, zmax + zoom_bw])
    sns.histplot(lat, bins=zbins, stat='density', element='step', fill=True, ax=ax)
    ax.set_xlim(zmin, zmax)
    ax.set_xlabel('Latency (ms)')
    ax.set_title(f'Histogram (zoom) — {src_path.name}')
    savefig(fig, out_dir / (src_path.stem + '_hist_zoom.png'))

    # CDF
    fig, ax = plt.subplots(figsize=(6,4))
    xs = np.sort(lat)
    ys = np.arange(1, len(xs)+1) / len(xs)
    ax.plot(xs, ys)
    ax.set_xlabel('Latency (ms)')
    ax.set_ylabel('CDF')
    ax.set_title(f'CDF — {src_path.name}')
    savefig(fig, out_dir / (src_path.stem + '_cdf.png'))

    # Time series
    if 'rel_time_s' in df.columns:
        fig, ax = plt.subplots(figsize=(8,3))
        ax.plot(df['rel_time_s'], df['lat_ms'], marker='.', ms=2, linestyle='none')
        ax.set_xlabel('Relative time (s)')
        ax.set_ylabel('Latency (ms)')
        ax.set_title(f'Latency over time — {src_path.name}')
        savefig(fig, out_dir / (src_path.stem + '_timeseries.png'))

    # Boxplot by direction (if present)
    if 'direction' in df.columns:
        fig, ax = plt.subplots(figsize=(6,4))
        sns.boxplot(x='direction', y='lat_ms', data=df, ax=ax)
        ax.set_ylabel('Latency (ms)')
        ax.set_title(f'Latency by direction — {src_path.name}')
        savefig(fig, out_dir / (src_path.stem + '_box_direction.png'))

def overlay_comparison(group_paths, label_map, out_dir: Path, name_prefix: str):
    # group_paths: list of Path
    # label_map: path -> label
    data = []
    for p in group_paths:
        try:
            df = load_latency_csv(p)
        except Exception as e:
            print('skip', p, e)
            continue
        lat = df['lat_ms'].dropna().values
        if len(lat)==0:
            continue
        data.append((p, lat))

    if not data:
        return

    # Histogram overlay (density)
    fig, ax = plt.subplots(figsize=(6,4))
    global_min = float(min(lat.min() for _,lat in data))
    global_max = float(max(lat.max() for _,lat in data))
    # choose a full_bw based on median fd to get sensible bins
    sample_fd = np.median([_fd_bin_width(lat)[2] for _, lat in data])
    if np.isclose(global_min, global_max):
        bins = np.array([global_min - sample_fd, global_max + sample_fd])
    else:
        bins = np.arange(global_min, global_max + sample_fd, sample_fd)
        if len(bins) < 2:
            bins = np.array([global_min - sample_fd, global_max + sample_fd])
    for p, lat in data:
        sns.histplot(lat, bins=bins, stat='density', element='step', fill=False, ax=ax, label=label_map.get(p,p.name))
    ax.set_xlabel('Latency (ms)')
    ax.set_title(f'Comparison histogram — {name_prefix}')
    ax.legend()
    savefig(fig, out_dir / (name_prefix + '_comp_hist.png'))

    # CDF overlay
    fig, ax = plt.subplots(figsize=(6,4))
    for p, lat in data:
        xs = np.sort(lat)
        ys = np.arange(1, len(xs)+1)/len(xs)
        ax.plot(xs, ys, label=label_map.get(p,p.name))
    ax.set_xlabel('Latency (ms)')
    ax.set_ylabel('CDF')
    ax.set_title(f'Comparison CDF — {name_prefix}')
    ax.legend()
    savefig(fig, out_dir / (name_prefix + '_comp_cdf.png'))

def main():
    files = find_latency_files(ROOT)
    print(f'Found {len(files)} latency CSVs')

    # map scenarios to files
    scenario_map = {}
    for f in files:
        tech, scen = scenario_key(f)
        key = (scen or 'root')
        scenario_map.setdefault(key, []).append(f)

    # Per-file plots
    for f in files:
        tech, scen = scenario_key(f)
        out_dir = OUT_ROOT / (scen or 'root') / tech / f.parent.name
        ensure_dir(out_dir)
        try:
            df = load_latency_csv(f)
        except Exception as e:
            print('Failed to load', f, e)
            continue
        plot_individual(df, f, out_dir)

    # Per-scenario comparisons: compare all techs within same scenario
    for scen, paths in scenario_map.items():
        # label by tech
        label_map = {}
        for p in paths:
            tech, _ = scenario_key(p)
            label_map[p] = tech
        out_dir = OUT_ROOT / scen
        ensure_dir(out_dir)
        overlay_comparison(paths, label_map, out_dir, f'scenario_{scen}')

    print('Done. Plots saved under', OUT_ROOT)

if __name__ == '__main__':
    main()
