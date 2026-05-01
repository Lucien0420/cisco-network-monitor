from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
from logger_config import setup_logger

driver_logger = setup_logger('driver')

class ProfessionalSwitchDriver:
    def __init__(self, device_info):
        """device_info: dict with ip, username, password, device_type."""
        self.device_info = device_info
        self.conn = None

    def connect(self):
        """Establish connection; handle common network exceptions."""
        try:
            # Netmiko ConnectHandler supported keys (adjust per Netmiko version)
            netmiko_supported_keys = [
                'host', 'ip', 'username', 'password', 'device_type', 'port',
                'secret', 'global_delay_factor', 'use_keys', 'key_file',
                'timeout', 'keepalive', 'conn_timeout', 'alt_prompt_autodetect_tentative',
                'banner_timeout', 'auth_timeout', 'session_log', 'fast_cli', 'blocking_timeout',
                'proxies', 'ssh_config_file', 'system_host_keys', 'alt_hostnames',
                'serial_settings', 'platform', 'extras', 'verbose', 'cmd_verify',
                'allow_footprint', 'encoding', 'ssh_autodetect', 'auto_close'
            ]

            # Filter device_info to Netmiko params only
            netmiko_params = {
                k: self.device_info[k]
                for k in netmiko_supported_keys if k in self.device_info
            }

            # Map 'ip' to 'host' for Netmiko
            if 'ip' in netmiko_params and 'host' not in netmiko_params:
                netmiko_params['host'] = netmiko_params.pop('ip')
            
            # Default timeout for slow SSH init
            if 'timeout' not in netmiko_params:
                netmiko_params['timeout'] = 15
            
            # Default delay factor for slow SSH servers
            if 'global_delay_factor' not in netmiko_params:
                netmiko_params['global_delay_factor'] = 2
            
            self.conn = ConnectHandler(**netmiko_params)
            driver_logger.info(f"Connected to {netmiko_params.get('host', 'unknown')}")
            return True
        except NetmikoTimeoutException:
            host = self.device_info.get('host') or self.device_info.get('ip', 'unknown')
            driver_logger.error(f"{host} Connection timeout. Check network.")
        except NetmikoAuthenticationException:
            host = self.device_info.get('host') or self.device_info.get('ip', 'unknown')
            driver_logger.error(f"{host} Authentication failed.")
        except Exception as e:
            host = self.device_info.get('host') or self.device_info.get('ip', 'unknown')
            driver_logger.error(f"Connection to {host} failed: {e}", exc_info=True)
        return False

    def send_command(self, command, use_textfsm=False):
        """Execute command and return result (raw string or structured)."""
        if not self.conn:
            return None
        
        try:
            return self.conn.send_command(command, use_textfsm=use_textfsm)
        except Exception as e:
            driver_logger.error(f"Command '{command}' failed: {e}", exc_info=True)
            return None

    def get_structured_data(self, command):
        """Execute command and return structured data (list of dicts) via TextFSM."""
        if not self.conn:
            return None
        
        try:
            # use_textfsm=True invokes community templates for parsing
            return self.conn.send_command(command, use_textfsm=True)
        except Exception as e:
            driver_logger.error(f"Command '{command}' failed: {e}", exc_info=True)
            return None

    def read_channel(self):
        """Read passive logs from channel (wraps Netmiko read_channel)."""
        if not self.conn:
            return ""
        
        try:
            return self.conn.read_channel()
        except Exception as e:
            driver_logger.error(f"Read channel failed: {e}", exc_info=True)
            return ""

    def is_alive(self):
        """Return True if the SSH transport is still active."""
        if not self.conn:
            return False
        try:
            return self.conn.is_alive()
        except Exception:
            return False

    def reconnect(self):
        """Close the current connection and attempt to re-establish it."""
        self.close()
        return self.connect()

    def close(self):
        """Close connection and handle exceptions."""
        if self.conn:
            try:
                self.conn.disconnect()
                driver_logger.debug("Connection closed")
            except Exception as e:
                driver_logger.warning(f"Close connection error: {e}", exc_info=True)
            finally:
                self.conn = None

    def __enter__(self):
        """Context manager entry — connect on enter, raise on failure."""
        if not self.connect():
            host = self.device_info.get('ip') or self.device_info.get('host', 'unknown')
            raise ConnectionError(f"Failed to connect to {host}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — always close the connection."""
        self.close()
        return False