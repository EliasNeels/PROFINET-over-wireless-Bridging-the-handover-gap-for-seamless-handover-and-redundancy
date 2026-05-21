# Master Thesis Repository

This repository contains the data, plots, and code used for the measurements and analysis of my Master's Thesis. 

## Repository Structure

The repository is organized into the following main components:

### 📁 Plots and Results
Contains the generated SVG, CSV, and plot files visualizing the measurement results. These are grouped by the specific type of experiment or scenario:
- **`Plots/`**: The primary directory containing visual results (SVG format) and processed data (CSV format). 
  - `Baseline_Comparison/`: Results from the baseline measurements across different configurations.
  - `Load_Comparison/`: Results showcasing performance under varying load conditions.
  - `Attenuation_Comparison/`: Results analyzing the effects of signal attenuation.
  - `Handover_Comparison/`: Results from seamless handover scenarios.
- **`Plots_NoTable/`**: Contains plots formatted without accompanying data tables.
- **`Interference screenshots/`**: Screenshots documenting interference during measurements.

### 📁 Code
- **`Code/`**: Contains the Python scripts used for analyzing the PCAP files, processing data, and generating the plots. Key scripts include:
  - `pcap_analyzer.py`: Core logic for parsing and analyzing PCAP files.
  - `plot_engine.py` / `plot_engine_fixed.py`: Engines responsible for rendering the plots.
  - `generate_all_plots.py` and other `generate_*.py` scripts: Scripts to generate specific sets of plots (baseline, load, attenuation, handover).
  - `run_*_analysis.py`: Scripts to execute the analysis pipeline on different measurement phases.

### 📦 PCAP Data (Zipped)
The raw `.pcap` capture files from the measurements have been compressed into a `.zip` file for easier distribution and storage. The original folder structure for the measurements is divided by the type of connection and the phase of the experiment:
- **`Wired/`**: Baseline wired network measurements.
- **`WLAN/`**: Wi-Fi measurements.
- **`BT/`**: Bluetooth measurements.
- **`1AP_2CL/`**: Measurements involving 1 Access Point and 2 Clients.

Due to file size limits, the raw `.pcap` captures for the are hosted in the Releases section. 

👉 [Download the Thesis_PCAP_Data.zip here](https://github.com/EliasNeels/PROFINET-over-wireless-Bridging-the-handover-gap-for-seamless-handover-and-redundancy/releases)

*Note: Extracting this zip file will automatically place all `.pcap` files into their correct folder structures alongside the Python analysis scripts.*

Within each connection type (e.g., `WLAN`, `BT`), the data is further organized by the experiment phase:
- `P1_Baseline/`: Baseline measurements (often categorized by cycle times like `16ms`, `32ms`, `64ms`, `128ms`).
- `P2_Load/`: Measurements taken under network load.
- `P3_Attenuation/`: Measurements involving signal attenuation.
- `P4_Seamless_Handover/`: Measurements testing seamless handover between access points.

### 📁 Documentation
- **`Thesis_Measurements_Overview.xlsx`**: An Excel spreadsheet providing a high-level overview and summary of all the measurements taken.

