import netmiko
from netmiko import ConnectHandler
import logging
import os
from datetime import datetime
import ipaddress

# Set up logging
logging.basicConfig(filename='network_backup.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def read_ip_list(file_path):
    """Read IP addresses from a file."""
    try:
        with open(file_path, 'r') as f:
            # Read lines, strip whitespace, and filter out empty lines
            ip_list = [line.strip() for line in f if line.strip()]
        return ip_list
    except Exception as e:
        logging.error(f"Failed to read IP list from {file_path}: {str(e)}")
        return []

def write_failed_connection(ip, failed_file):
    """Append IP to failed connections file."""
    try:
        with open(failed_file, 'a') as f:
            f.write(f"{ip}\n")
        logging.info(f"Logged failed connection for {ip} to {failed_file}")
    except Exception as e:
        logging.error(f"Failed to write to {failed_file} for {ip}: {str(e)}")

def update_ip_list(file_path, successful_ips):
    """Rewrite IP list file to include only successful IPs."""
    try:
        with open(file_path, 'w') as f:
            for ip in successful_ips:
                f.write(f"{ip}\n")
        logging.info(f"Updated {file_path} with successful IPs")
    except Exception as e:
        logging.error(f"Failed to update {file_path}: {str(e)}")

def validate_ip(ip):
    """Validate IP address format."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        logging.error(f"Invalid IP address: {ip}")
        return False

def get_device_type(ip, username, password, failed_file):
    """Attempt to determine device type by connecting and checking platform."""
    device = {
        'device_type': 'autodetect',
        'ip': ip,
        'username': username,
        'password': password,
        'timeout': 30,
        'conn_timeout': 10
    }
    
    try:
        with ConnectHandler(**device) as conn:
            # Get prompt or platform information
            prompt = conn.find_prompt()
            if '>' in prompt or '#' in prompt:
                output = conn.send_command('show version', use_textfsm=True)
                if output and isinstance(output, list) and len(output) > 0:
                    version = output[0].get('version', '').lower()
                    platform = output[0].get('hardware', '').lower()
                    
                    if 'nexus' in platform or 'nx-os' in version:
                        return 'cisco_nxos'
                    elif 'wlc' in platform or 'aireos' in version:
                        return 'cisco_wlc'
                    elif 'fibre channel' in platform or 'mds' in platform:
                        return 'cisco_mds'
                    elif 'juniper' in platform or 'junos' in version:
                        return 'juniper_junos'
                    else:
                        return 'cisco_ios'
    except Exception as e:
        logging.error(f"Failed to detect device type for {ip}: {str(e)}")
        write_failed_connection(ip, failed_file)
        return None

def get_config(ip, username, password, device_type, failed_file):
    """Connect to device and retrieve configuration."""
    device = {
        'device_type': device_type,
        'ip': ip,
        'username': username,
        'password': password,
        'timeout': 30,
        'conn_timeout': 10
    }
    
    config_commands = {
        'cisco_ios': 'show running-config',
        'cisco_nxos': 'show running-config',
        'cisco_wlc': 'show run-config commands',
        'cisco_mds': 'show running-config',
        'juniper_junos': 'show configuration | display set'
    }
    
    try:
        with ConnectHandler(**device) as conn:
            logging.info(f"Connected to {ip} ({device_type})")
            config = conn.send_command(config_commands[device_type])
            return config
    except Exception as e:
        logging.error(f"Failed to retrieve config from {ip}: {str(e)}")
        write_failed_connection(ip, failed_file)
        return None

def save_config(ip, config, output_dir):
    """Save configuration to a file."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{output_dir}/{ip}_{timestamp}.cfg"
    
    try:
        with open(filename, 'w') as f:
            f.write(config)
        logging.info(f"Configuration saved for {ip} to {filename}")
        return True
    except Exception as e:
        logging.error(f"Failed to save config for {ip}: {str(e)}")
        return False

def main():
    # Configuration
    ip_file = 'ip_list.txt'  # File containing IP addresses
    failed_file = 'failed_connections.txt'  # File for failed connections
    username = 'admin'  # Replace with your username
    password = 'password'  # Replace with your password
    output_dir = 'configs'  # Directory to store configs
    
    # Read IP addresses from file
    ip_list = read_ip_list(ip_file)
    if not ip_list:
        logging.error("No valid IP addresses found in the file. Exiting.")
        return
    
    successful_ips = []
    
    for ip in ip_list:
        if not validate_ip(ip):
            write_failed_connection(ip, failed_file)
            continue
            
        logging.info(f"Processing device: {ip}")
        
        # Detect device type
        device_type = get_device_type(ip, username, password, failed_file)
        if not device_type:
            continue
            
        # Get configuration
        config = get_config(ip, username, password, device_type, failed_file)
        if config:
            # Save configuration
            if save_config(ip, config, output_dir):
                successful_ips.append(ip)
    
    # Update original IP list with successful IPs only
    update_ip_list(ip_file, successful_ips)

if __name__ == '__main__':
    main()
