import os
import csv
import json
import struct
import hashlib
import re
from decimal import Decimal
import numpy as np

from collections import defaultdict
from scapy.all import PcapReader, Ether, Dot1Q, IP, conf

conf.l2types.register(240, Ether)

MAC_PLC = "d6:87:75"
MAC_IO  = "d5:55:0f"
MAC_PLC_BYTES = bytes.fromhex(MAC_PLC.replace(':', ''))
MAC_IO_BYTES  = bytes.fromhex(MAC_IO.replace(':', ''))
PROFINET_ETHERTYPE = 0x8892

CACHE_FILE = os.path.join(os.path.dirname(__file__), "analysis_cache.json")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_cache(new_data):
    # Always merge with existing cache on disk to prevent data loss
    cache = load_cache()
    cache.update(new_data)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=4)

def file_hash(file_path):
    """Produces a quick hash based on file size and modification time to validate cache."""
    try:
        stat = os.stat(file_path)
        return f"{stat.st_size}_{stat.st_mtime}"
    except OSError:
        return None

def extract_true_ethernet(raw_pkt):
    raw_bytes = bytes(raw_pkt)
    idx1 = raw_bytes.find(MAC_PLC_BYTES)
    idx2 = raw_bytes.find(MAC_IO_BYTES)
    if idx1 >= 0 and idx2 >= 0:
        # We found PROFINET headers inside something else (e.g., PRP)
        eth_start = min(idx1, idx2) - 3
        if 0 <= eth_start < 24:
            return Ether(raw_bytes[eth_start:])
    if Ether in raw_pkt:
        return raw_pkt[Ether]
    return Ether(raw_bytes)

def find_cycle_counter_offset(packets):
    if not packets:
        return None
    min_len = min(len(p) for _t, p in packets)
    possible_steps = [512, 1024, 2048, 4096]
    valid_offsets = []

    for offset in range(min_len - 1):
        values = [struct.unpack('>H', p[offset:offset+2])[0] for _t, p in packets[:1000]]
        
        # A true cycle counter increments, so it should have many unique values over 1000 packets
        num_unique = len(set(values))
        if num_unique < min(10, len(values) // 3):
            continue

        found_step = None
        is_valid = True
        for i in range(1, len(values)):
            diff = (values[i] - values[i-1]) % 65536
            if diff != 0:
                if any(diff % step == 0 for step in possible_steps):
                    for s in possible_steps:
                        if diff % s == 0:
                            found_step = s
                else:
                    is_valid = False
                    break
        if is_valid and found_step is not None:
            valid_offsets.append((num_unique, offset, found_step))

    if valid_offsets:
        # Pick the offset that generates the most unique values (most "counter-like")
        # If tied, pick the earliest offset.
        valid_offsets.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        best_unique, best_offset, detected_step = valid_offsets[0]
        return best_offset, detected_step
    return None, 1

def analyze_pcap(file_path, cycle_time_ms=64, ignore_cache=False):
    """
    Parses a PCAP and returns a dictionary with metrics:
    Avg Latency (ms), Max Latency, Min Latency, Jitter, Packet Loss
    """
    
    # --- 1. Check Cache ---
    cache = load_cache()
    f_hash = file_hash(file_path)
    if f_hash is None:
        return {} # File doesn't exist
        
    if not ignore_cache and file_path in cache and cache[file_path].get('hash') == f_hash:
        print(f"    [Cache Hit] {os.path.basename(file_path)}")
        return cache[file_path]['metrics']

    print(f"    [Analyzing] {os.path.basename(file_path)}...")
    
    plc_to_io_packets = []
    io_to_plc_packets = []

    ipv4_bytes_per_sec = defaultdict(int)
    ipv4_counts_per_sec = defaultdict(int)
    total_bytes_count = 0
    global_first_packet_time = None

    try:
        with PcapReader(file_path) as pcap:
            for raw_pkt in pcap:
                total_bytes_count += len(raw_pkt)
                exact_time = Decimal(str(raw_pkt.time))
                if global_first_packet_time is None or exact_time < global_first_packet_time:
                    global_first_packet_time = exact_time
                
                pkt = extract_true_ethernet(raw_pkt)
                
                # Extract Load Traffic
                if IP in pkt and (pkt[IP].proto == 17): # UDP only
                    sec = int(raw_pkt.time)
                    ipv4_bytes_per_sec[sec] += len(raw_pkt)
                    ipv4_counts_per_sec[sec] += 1
                    
                if Ether not in pkt:
                    continue
                is_pn = (
                    pkt[Ether].type == PROFINET_ETHERTYPE
                    or (pkt.haslayer(Dot1Q) and pkt[Dot1Q].type == PROFINET_ETHERTYPE)
                )
                if not is_pn:
                    continue
                
                src = pkt[Ether].src
                dst = pkt[Ether].dst
                payload = (bytes(pkt[Dot1Q].payload)
                           if pkt.haslayer(Dot1Q)
                           else bytes(pkt[Ether].payload))
                           
                if src.endswith(MAC_PLC) and dst.endswith(MAC_IO):
                    plc_to_io_packets.append((exact_time, payload))
                elif src.endswith(MAC_IO) and dst.endswith(MAC_PLC):
                    io_to_plc_packets.append((exact_time, payload))
    except Exception as e:
        print(f"    [!] Error parsing {file_path}: {e}")
        return {}

    # Identify cycle numbers and map them
    def group_cycles(packets):
        grouped = {}
        if not packets:
            return grouped, 0, 0, 1
            
        packets.sort(key=lambda x: x[0])
        cc_offset, detected_step = find_cycle_counter_offset(packets)
        if cc_offset is None:
            return grouped, 0, 0, 1
            
        last_cc = None
        unwrapped_id = 0
        for t, p in packets:
            cc = struct.unpack('>H', p[cc_offset:cc_offset + 2])[0]
            if last_cc is None:
                last_cc = cc
                unwrapped_id = cc
            diff = (cc - last_cc) % 65536
            if diff == 0:
                current_id = unwrapped_id
            elif diff < 32768:
                unwrapped_id += diff
                current_id = unwrapped_id
            else:
                current_id = unwrapped_id - (65536 - diff)
            last_cc = cc
            grouped.setdefault(current_id, []).append((t, p))
            
        # To determine expected cycle span, we use unwrapped IDs
        unwrapped_keys = list(grouped.keys())
        if not unwrapped_keys:
            return grouped, 0, 0, detected_step
            
        min_id = min(unwrapped_keys)
        max_id = max(unwrapped_keys)
        return grouped, min_id, max_id, detected_step

    plc_grouped, plc_min, plc_max, plc_step = group_cycles(plc_to_io_packets)
    io_grouped, io_min, io_max, io_step = group_cycles(io_to_plc_packets)
    
    # Compute combined intended cycles (the union span of both ends)
    if not plc_grouped and not io_grouped:
        return {}
    
    min_id = min(plc_min, io_min) if plc_grouped and io_grouped else (plc_min if plc_grouped else io_min)
    max_id = max(plc_max, io_max) if plc_grouped and io_grouped else (plc_max if plc_grouped else io_max)
    
    # Use the detected step (e.g. 128) to calculate the true number of expected cycles
    step = plc_step if plc_grouped else io_step
    intended_cycles = ((max_id - min_id) // step) + 1
    if intended_cycles <= 0:
        intended_cycles = 1 # Fallback safeguard
        
    latencies = []
    
    # Threshold setup
    if "Wired" in file_path:
        LOWER_THRESHOLD_SEC = Decimal('-1.0') # Fully accept all minimal latencies (even 0.0 if nanosecond timestamp resolves equally)
    else:
        LOWER_THRESHOLD_SEC = Decimal('0.0001')   # 100 us
    UPPER_THRESHOLD_SEC = Decimal(str(cycle_time_ms * 3 / 1000))
    MS_CONVERSION = Decimal('1000')

    # Calculate Latencies based on finding the same packet multiple times (End-to-End transit)
    latencies = []
    e2e_records = []
    e2e_matches = 0
    total_received_unique = 0
    
    is_end2end = "End2End" in os.path.basename(file_path)
    is_prpclient = "PRPClient" in os.path.basename(file_path) or ("PRP.pcap" in os.path.basename(file_path) and "End2End" not in os.path.basename(file_path))
    is_switchap = "SwitchAP" in os.path.basename(file_path)
    
    prp_records = []
    
    for unique_id, plc_times in plc_grouped.items():
        total_received_unique += 1
        if is_end2end and len(plc_times) >= 2:
            dt_sec = plc_times[-1][0] - plc_times[0][0]
            if LOWER_THRESHOLD_SEC < dt_sec < UPPER_THRESHOLD_SEC:
                lat = float(dt_sec * MS_CONVERSION)
                latencies.append(lat)
                e2e_matches += 1
                e2e_records.append({
                    'timestamp': float(plc_times[0][0]),
                    'direction': "PLC -> IO",
                    'e2e_latency_ms': lat
                })
        if is_prpclient and len(plc_times) >= 2:
            time_a = None
            time_b = None
            for t, p in plc_times:
                if time_a is None and b'\xa0\x34\x88\xfb' in p:
                    time_a = t
                elif time_b is None and b'\xb0\x34\x88\xfb' in p:
                    time_b = t
                if time_a is not None and time_b is not None:
                    break
            if time_a is not None and time_b is not None:
                dt_sec = abs(time_a - time_b)
                skew = float(dt_sec) * float(MS_CONVERSION) # convert to milliseconds
                # Use the earlier time as the reference timestamp
                prp_records.append({
                    'timestamp': float(min(time_a, time_b)),
                    'direction': "PLC -> IO",
                    'skew_ms': skew
                })
    for unique_id, io_times in io_grouped.items():
        total_received_unique += 1
        if is_end2end and len(io_times) >= 2:
            dt_sec = io_times[-1][0] - io_times[0][0]
            if LOWER_THRESHOLD_SEC < dt_sec < UPPER_THRESHOLD_SEC:
                lat = float(dt_sec * MS_CONVERSION)
                latencies.append(lat)
                e2e_matches += 1
                e2e_records.append({
                    'timestamp': float(io_times[0][0]),
                    'direction': "IO -> PLC",
                    'e2e_latency_ms': lat
                })
    if e2e_records:
        e2e_records.sort(key=lambda x: x['timestamp'])
        start_time = float(global_first_packet_time) if global_first_packet_time else e2e_records[0]['timestamp']
        csv_path = os.path.splitext(file_path)[0] + "_latencies.csv"
        try:
            with open(csv_path, mode='w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['timestamp', 'rel_time_s', 'direction', 'e2e_latency_ms'])
                for rec in e2e_records:
                    rel_time_s = rec['timestamp'] - start_time
                    writer.writerow([rec['timestamp'], rel_time_s, rec['direction'], rec['e2e_latency_ms']])
        except Exception as e:
            print(f"    [!] Error writing CSV {csv_path}: {e}")

    if prp_records:
        prp_records.sort(key=lambda x: x['timestamp'])
        start_time = float(global_first_packet_time) if global_first_packet_time else prp_records[0]['timestamp']
        csv_path = os.path.splitext(file_path)[0] + "_prpskew.csv"
        try:
            with open(csv_path, mode='w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['timestamp', 'rel_time_s', 'direction', 'skew_ms'])
                for rec in prp_records:
                    rel_time_s = rec['timestamp'] - start_time
                    writer.writerow([rec['timestamp'], rel_time_s, rec['direction'], rec['skew_ms']])
        except Exception as e:
            print(f"    [!] Error writing CSV {csv_path}: {e}")
    elif is_prpclient:
        print(f"      [!] No matching PRP pairs found for skew calculation in {os.path.basename(file_path)}. E2E might have 100% loss on one link.")

    if is_switchap:
        ipg_records = []
        # Calculate IPG for PLC -> IO
        all_plc_times = sorted([times[0][0] for times in plc_grouped.values() if times])
        for i in range(1, len(all_plc_times)):
            dt_sec = all_plc_times[i] - all_plc_times[i-1]
            ipg_ms = float(dt_sec * MS_CONVERSION)
            ipg_records.append({
                'timestamp': float(all_plc_times[i]),
                'direction': "PLC -> IO",
                'ipg_ms': ipg_ms
            })
            
        # Calculate IPG for IO -> PLC
        all_io_times = sorted([times[0][0] for times in io_grouped.values() if times])
        for i in range(1, len(all_io_times)):
            dt_sec = all_io_times[i] - all_io_times[i-1]
            ipg_ms = float(dt_sec * MS_CONVERSION)
            ipg_records.append({
                'timestamp': float(all_io_times[i]),
                'direction': "IO -> PLC",
                'ipg_ms': ipg_ms
            })
            
        if ipg_records:
            ipg_records.sort(key=lambda x: x['timestamp'])
            start_time = ipg_records[0]['timestamp']
            csv_path = os.path.splitext(file_path)[0] + "_ipg.csv"
            try:
                with open(csv_path, mode='w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['timestamp', 'rel_time_s', 'direction', 'ipg_ms'])
                    for rec in ipg_records:
                        rel_time_s = rec['timestamp'] - start_time
                        writer.writerow([rec['timestamp'], rel_time_s, rec['direction'], rec['ipg_ms']])
            except Exception as e:
                print(f"    [!] Error writing CSV {csv_path}: {e}")

    if ipv4_bytes_per_sec:
        load_records = sorted(ipv4_bytes_per_sec.items())
        start_sec = int(global_first_packet_time) if global_first_packet_time else load_records[0][0]
        csv_path = os.path.splitext(file_path)[0] + "_load.csv"
        try:
            with open(csv_path, mode='w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['timestamp_sec', 'rel_time_s', 'throughput_mbps'])
                for sec, bytes_count in load_records:
                    rel_sec = sec - start_sec
                    mbps = (bytes_count * 8) / 1_000_000.0
                    writer.writerow([sec, rel_sec, round(mbps, 4)])
        except Exception as e:
            print(f"    [!] Error writing CSV {csv_path}: {e}")

    udp_packet_loss = ""
    if ipv4_counts_per_sec:
        # Extract target Mbps (e.g. 0,15Mbps or 5Mbps)
        match_m = re.search(r'([0-9]+(?:,[0-9]+)?)M', os.path.basename(file_path), re.IGNORECASE)
        # Extract packet size (64B or 1400B) from path
        match_s = re.search(r'([0-9]+)B', file_path)
        
        if match_m and match_s:
            target_mbps = float(match_m.group(1).replace(',', '.'))
            if target_mbps == 0 or "NoUDP" in file_path:
                udp_packet_loss = 0.0
            else:
                payload_size = float(match_s.group(1))
                # On-wire size (L1 + L2 + L3 + L4 + Payload)
                # L1 (20B) + Eth (14B) + IP (20B) + UDP (8B) + Payload + FCS (4B)
                on_wire_bytes = 20 + 14 + 20 + 8 + payload_size + 4
                
                load_records = sorted(ipv4_counts_per_sec.items())
                if load_records:
                    # Use the full PCAP duration (from the very first IP packet to the last)
                    duration_sec = load_records[-1][0] - load_records[0][0] + 1
                    
                    if duration_sec > 0:
                        # Based on Wireshark, the '64B' is the total L2 frame size (including Eth/IP/UDP)
                        # So we use exactly 64 or 1400 bytes.
                        on_wire_bits = float(payload_size) * 8.0
                        
                        # Target Mbps calculation
                        expected_pps = (target_mbps * 1_000_000.0) / on_wire_bits
                        total_expected = expected_pps * duration_sec
                        total_actual = sum(c for _, c in load_records)
                        
                        loss_pct = 100.0 * (1.0 - (total_actual / total_expected))
                        udp_packet_loss = round(max(0.0, loss_pct), 3)
        elif "NoUDP" in file_path:
             udp_packet_loss = 0.0

    metrics = {
        "Avg Latency (ms)": "",
        "Max Latency (ms)": "",
        "Min Latency (ms)": "",
        "Jitter (ms)": "",
        "Packet Loss (%)": "",
        "UDP Packet Loss (%)": udp_packet_loss,
        "PN Throughput (Mbps)": 0.0
    }

    if latencies:
        np_lats = np.array(latencies)
        metrics["Avg Latency (ms)"] = round(float(np.mean(np_lats)), 5)
        metrics["Max Latency (ms)"] = round(float(np.max(np_lats)), 5)
        metrics["Min Latency (ms)"] = round(float(np.min(np_lats)), 5)
        
        if len(np_lats) > 1:
            metrics["Jitter (ms)"] = round(float(np.mean(np.abs(np.diff(np_lats)))), 5)
        else:
            metrics["Jitter (ms)"] = 0.0

    # Packet Loss
    # Total intended cycles (sum of intended for PLC->IO and IO->PLC)
    total_intended = 0
    if plc_grouped:
        total_intended += ((plc_max - plc_min) / plc_step) + 1
    if io_grouped:
        total_intended += ((io_max - io_min) / io_step) + 1
        
    if total_intended > 0:
        pl = 100.0 * (1.0 - (total_received_unique / float(total_intended)))
        pl = max(0.0, min(100.0, pl))
        metrics["Packet Loss (%)"] = round(pl, 3)

    # Calculate PN Throughput
    if e2e_records:
        duration = e2e_records[-1]['timestamp'] - e2e_records[0]['timestamp']
    elif prp_records:
        duration = prp_records[-1]['timestamp'] - prp_records[0]['timestamp']
    else:
        duration = 0
    
    if duration > 0:
        # Use the actual sum of unique frame bytes
        throughput = (total_bytes_count * 8) / (duration * 1_000_000.0)
        metrics["PN Throughput (Mbps)"] = round(float(throughput), 6)

    # Save to Cache (merging with existing)
    save_cache({file_path: {
        "hash": f_hash,
        "metrics": metrics
    }})
    
    return metrics

if __name__ == "__main__":
    # Test on one file
    print("Test run on analyzer")
