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

def validate_ip(ip):
    """Validate IP address format."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        logging.error(f"Invalid IP address: {ip}")
        return False

def get_device_type(ip, username, password):
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
        return None

def get_config(ip, username, password, device_type):
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
    username = 'admin'  # Replace with your username
    password = 'password'  # Replace with your password
    output_dir = 'configs'  # Directory to store configs
    
    # Read IP addresses from file
    ip_list = read_ip_list(ip_file)
    if not ip_list:
        logging.error("No valid IP addresses found in the file. Exiting.")
        return
    
    for ip in ip_list:
        if not validate_ip(ip):
            continue
            
        logging.info(f"Processing device: {ip}")
        
        # Detect device type
        device_type = get_device_type(ip, username, password)
        if not device_type:
            logging.error(f"Could not determine device type for {ip}")
            continue
            
        # Get configuration
        config = get_config(ip, username, password, device_type)
        if config:
            # Save configuration
            save_config(ip, config, output_dir)

if __name__ == '__main__':
    main()
