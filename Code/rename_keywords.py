import os
import argparse

def rename_files(directory):
    renamed_count = 0
    for root, _, files in os.walk(directory):
        for filename in files:
            new_name = filename
            
            # Replace occurrences
            if '2AP' in new_name:
                new_name = new_name.replace('2AP', 'BT')
            if 'VLAN' in new_name:
                new_name = new_name.replace('VLAN', 'WLAN')
            if '_00001' in new_name:
                new_name = new_name.replace('_00001', '')
            
            # Check if name has actually changed
            if new_name != filename:
                old_path = os.path.join(root, filename)
                new_path = os.path.join(root, new_name)
                
                # Check for existing file to avoid unintentional overwrites
                if not os.path.exists(new_path):
                    try:
                        os.rename(old_path, new_path)
                        print(f"Renamed: '{filename}' -> '{new_name}'")
                        renamed_count += 1
                    except Exception as e:
                        print(f"Error renaming '{filename}': {e}")
                else:
                    print(f"Skipped: Cannot rename '{filename}' because '{new_name}' already exists.")
                    
    print(f"\nTotal files renamed: {renamed_count}")

if __name__ == "__main__":
    # Setup argument parser so the directory can be passed easily
    parser = argparse.ArgumentParser(description="Rename files replacing '2AP' with 'BT', 'VLAN' with 'WLAN', and removing '_00001'.")
    parser.add_argument("directory", nargs="?", default=".", help="Target directory to process (default is current directory)")
    args = parser.parse_args()
    
    target_dir = os.path.abspath(args.directory)
    print(f"Starting file rename process in: {target_dir}\n")
    rename_files(target_dir)
