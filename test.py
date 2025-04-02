import paramiko
import time
import re
import csv
import sys

# WLC connection details (replace with your own)
WLC_HOST = "192.168.1.100"  # WLC IP address
WLC_USERNAME = "admin"      # WLC username
WLC_PASSWORD = "password"   # WLC password
OUTPUT_CSV = "wlc_clients.csv"  # Output CSV file name
AP_PREFIX = "BB4E_FL4"      # Default AP name prefix (changeable)

def ssh_connect(host, username, password):
    """Establish SSH connection to the WLC."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=10)
    return ssh

def run_command(ssh, command, wait_time=2):
    """Execute a command on the WLC and return the output."""
    shell = ssh.invoke_shell()
    shell.send(command + "\n")
    time.sleep(wait_time)  # Wait for command to execute
    output = shell.recv(65535).decode("utf-8")
    return output

def disable_pagination(ssh):
    """Disable the 'more' pagination on the WLC."""
    run_command(ssh, "config paging disable", wait_time=1)

def get_ap_names(ssh, ap_prefix):
    """Get AP names starting with the specified prefix from 'show ap summary'."""
    output = run_command(ssh, "show ap summary", wait_time=3)
    ap_lines = output.splitlines()
    ap_names = []
    for line in ap_lines:
        if re.match(ap_prefix, line.strip()):
            ap_name = line.split()[0]  # First column is the AP name
            ap_names.append(ap_name)
    return ap_names

def get_clients_for_ap(ssh, ap_name):
    """Get MAC addresses of clients connected to the AP on 802.11a radio."""
    command = f"show client ap 802.11a {ap_name}"
    output = run_command(ssh, command, wait_time=3)
    mac_addresses = []
    for line in output.splitlines():
        # Match MAC address format (e.g., 00:11:22:33:44:55)
        match = re.search(r"([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})", line)
        if match:
            mac_addresses.append((match.group(0), ap_name))  # Tuple of (MAC, AP Name)
    return mac_addresses

def get_client_details(ssh, mac_address):
    """Get detailed info for a client and extract IP address."""
    command = f"show client detail {mac_address}"
    output = run_command(ssh, command, wait_time=2)
    ip_address = "Unknown"
    for line in output.splitlines():
        if "IP Address" in line:
            ip_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
            if ip_match:
                ip_address = ip_match.group(0)
            break
    return ip_address

def save_to_csv(data):
    """Save MAC, IP, and AP Name to a CSV file."""
    with open(OUTPUT_CSV, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["MAC Address", "IP Address", "AP Name"])  # Header
        writer.writerows(data)

def main(ap_prefix=AP_PREFIX):
    try:
        # Connect to WLC
        print("Connecting to WLC...")
        ssh = ssh_connect(WLC_HOST, WLC_USERNAME, WLC_PASSWORD)
        print("Connected successfully.")

        # Disable pagination
        disable_pagination(ssh)
        print("Pagination disabled.")

        # Get AP names starting with the specified prefix
        ap_names = get_ap_names(ssh, ap_prefix)
        if not ap_names:
            print(f"No APs found starting with '{ap_prefix}'.")
            return
        print(f"Found APs: {ap_names}")

        # Collect client data
        client_data = []
        for ap_name in ap_names:
            print(f"Processing AP: {ap_name}")
            mac_ap_pairs = get_clients_for_ap(ssh, ap_name)
            if not mac_ap_pairs:
                print(f"No clients found for {ap_name} on 802.11a.")
                continue
            for mac, ap in mac_ap_pairs:
                print(f"Getting details for MAC: {mac} on AP: {ap}")
                ip = get_client_details(ssh, mac)
                client_data.append([mac, ip, ap])  # Include AP name in data

        # Save to CSV
        if client_data:
            save_to_csv(client_data)
            print(f"Data saved to {OUTPUT_CSV}")
        else:
            print("No client data to save.")

    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        ssh.close()
        print("SSH connection closed.")

if __name__ == "__main__":
    # Check if an AP prefix is provided as a command-line argument
    if len(sys.argv) > 1:
        main(sys.argv[1])  # Use command-line argument as AP prefix
    else:
        main()  # Use default AP_PREFIX


