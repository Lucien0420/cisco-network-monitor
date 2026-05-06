"""
Professional Switch Simulator: Paramiko-based SSH server for Netmiko (main.py) to connect.
Run in WSL, listen on port 2222. devices.json: WSL IP, port 2222, device_type: cisco_ios.
Supports: show processes cpu, show interfaces status, show memory, show vlan brief, show inventory.
"""
import os
import random
import socket
import threading
import logging
import sys
import argparse
import time
import math
from datetime import datetime

import paramiko

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - SwitchSimulator - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default credentials
DEFAULT_USER = os.environ.get("SIM_SWITCH_USER", "switch")
DEFAULT_PASS = os.environ.get("SIM_SWITCH_PASS", "switch123")
LISTEN_HOST = os.environ.get("SIM_SWITCH_HOST", "0.0.0.0")

# Global vars, updated by args
SIM_USER = DEFAULT_USER
SIM_PASS = DEFAULT_PASS
LISTEN_PORT = 2222

# Simulation state
START_TIME = time.time()

# Netmiko prompt (cisco_ios expects #)
PROMPT = "Switch# "


class SwitchPersonality:
    """Holds unique behavior parameters for a specific SSH session."""
    def __init__(self):
        # Base values with some randomness per session
        self.cpu_base = random.uniform(10.0, 30.0)
        self.mem_base = random.uniform(35.0, 55.0)
        self.temp_base = random.uniform(38.0, 44.0)
        
        # Timing offsets so spikes don't happen at the same time
        self.start_time = time.time() - random.randint(0, 1000)
        self.spike_interval = random.randint(40, 80)
        self.spike_duration = random.randint(4, 10)
        self.spike_value = random.uniform(60.0, 90.0)
        
        # Trend factors (some devices leak memory, some are stable)
        self.mem_leak_rate = random.choice([0.0, 0.0, 0.02, 0.05]) # 50% chance of no leak
        self.temp_drift = random.uniform(-0.5, 0.5)
        
        # Interface Gi0/3 toggle interval
        self.port_toggle_interval = random.randint(20, 50)

    def get_temperature(self):
        # Base temperature around 40C, with a slow sinusoidal wave + noise
        elapsed = time.time() - self.start_time
        wave = 2.0 * math.sin(elapsed / 60.0)  # 1-minute cycle
        v = self.temp_base + wave + (elapsed * 0.001 * self.temp_drift) + random.gauss(0, 0.2)
        return max(30, min(65, v))

    def get_cpu(self):
        # Base CPU with a slow sinusoidal wave + spikes + noise
        elapsed = time.time() - self.start_time
        wave = 5.0 * math.sin(elapsed / 45.0)  # 45-second cycle
        is_spike = (int(elapsed) % self.spike_interval) < self.spike_duration
        base = self.spike_value if is_spike else (self.cpu_base + wave)
        v = base + random.gauss(0, 1.5)
        return max(2, min(99, v))

    def get_memory(self):
        elapsed = time.time() - self.start_time
        leak = (elapsed / 10.0) * self.mem_leak_rate
        v = self.mem_base + leak + random.gauss(0, 0.1)
        return max(20, min(98, v))

    def get_interfaces_status(self):
        elapsed = time.time() - self.start_time
        gi03_up = (int(elapsed) % (self.port_toggle_interval * 2)) < self.port_toggle_interval
        gi03_status = "connected" if gi03_up else "notconnect"
        return (
            "Port      Name               Status       Vlan       Duplex  Speed Type\r\n"
            "Gi0/1     Uplink             connected    trunk      a-full  a-1000 10/100/1000BaseTX\r\n"
            "Gi0/2     Server_A           connected    20         a-full  a-1000 10/100/1000BaseTX\r\n"
            f"Gi0/3     Test_Port          {gi03_status:<12} 20         a-full  a-1000 10/100/1000BaseTX\r\n"
        )


def process_command(line: str, p: SwitchPersonality) -> str:
    """Process a command using the session's personality."""
    line = (line or "").strip()
    if not line:
        return PROMPT
    
    line_lower = line.lower()
    
    if any(x in line_lower for x in ["terminal width", "terminal length", "terminal"]):
        return f"{line}\r\n{PROMPT}"
    
    if "temperature" in line_lower or ("show" in line_lower and "temp" in line_lower):
        t = p.get_temperature()
        return f"{line}\r\nSystem Temperature:\r\n  Inlet Temperature: {t:.1f} °C\r\n  Threshold: 85°C\r\n  Status: OK\r\n{PROMPT}"
    
    if "processes" in line_lower and "cpu" in line_lower or "cpu" in line_lower:
        c = p.get_cpu()
        c1, c2 = max(0, c - 2), max(0, c - 4)
        return f"{line}\r\nCPU Load:\r\n  5-second CPU: {c:.1f} %\r\n  1-minute CPU: {c1:.1f} %\r\n  5-minute CPU: {c2:.1f} %\r\n{PROMPT}"
    
    if "chassis" in line_lower and "environment" in line_lower:
        t = p.get_temperature()
        return f"{line}\r\nChassis Environment:\r\n  Temperature: {t:.1f} C\r\n  Status: OK\r\n{PROMPT}"
    
    if "interfaces status" in line_lower:
        return f"{line}\r\n{p.get_interfaces_status()}{PROMPT}"

    if "interfaces summary" in line_lower:
        # Simple summary based on Gi0/3 status in personality
        status_raw = p.get_interfaces_status()
        gi03_up = "connected" in status_raw.splitlines()[3]
        gi03_marker = "*" if gi03_up else " "
        return (
            f"{line}\r\n"
            " *: interface is up\r\n"
            "  Interface              IHQ   IQD   OHQ   OQD  RXBS  RXPS  TXBS  TXPS  TRNP\r\n"
            "* GigabitEthernet0/1       0     0     0     0  1000     2  2000     4     0\r\n"
            "* GigabitEthernet0/2       0     0     0     0   500     1   800     2     0\r\n"
            f"{gi03_marker} GigabitEthernet0/3       0     0     0     0     0     0     0     0     0\r\n"
            f"{PROMPT}"
        )
    
    if "memory" in line_lower:
        m_used_pct = p.get_memory()
        total = 2000000000
        used = int(total * (m_used_pct / 100.0))
        free = total - used
        return (
            f"{line}\r\n"
            "                Head    Total(b)     Used(b)     Free(b)   Lowest(b)  Largest(b)\r\n"
            f"Processor   60000000  {total}  {used}  {free}   {free-1000}   {free-500}\r\n"
            f"{PROMPT}"
        )
    
    if "vlan" in line_lower:
        return (
            f"{line}\r\n"
            "VLAN Name                             Status    Ports\r\n"
            "---- -------------------------------- --------- -------------------------------\r\n"
            "1    default                          active    Gi0/1, Gi0/2, Gi0/3\r\n"
            "10   Management                       active\r\n"
            f"{PROMPT}"
        )

    if "inventory" in line_lower:
        return (
            f"{line}\r\n"
            "NAME: \"Switch System\", DESCR: \"Cisco Catalyst 9300-24T\"\r\n"
            "PID: C9300-24T         , VID: V01  , SN: FOC2134L05X\r\n"
            f"{PROMPT}"
        )
    
    if "version" in line_lower:
        return f"{line}\r\nCisco IOS Software, Version 12.2(58)SE2\r\nSystem uptime is 45 days.\r\n{PROMPT}"
    
    if "exit" in line_lower or "quit" in line_lower:
        return ""
    
    return f"{line}\r\n% Invalid command\r\n{PROMPT}"
    
    if "exit" in line_lower or "quit" in line_lower:
        return ""
    
    return f"{line}\r\n% Invalid command\r\n{PROMPT}"


class SwitchSimulatorServer(paramiko.ServerInterface):
    def __init__(self):
        self.event = threading.Event()

    def check_auth_password(self, username: str, password: str) -> int:
        if username == SIM_USER and password == SIM_PASS:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_channel_request(self, kind: str, chanid: int) -> int:
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_shell_request(self, channel) -> bool:
        self.event.set()
        return True

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes) -> bool:
        return True


def handle_client(transport, server):
    channel = transport.accept(20)
    if channel is None:
        return
    # Wait for client to request shell
    server.event.wait(10)
    server.event.clear()
    
    # Create a unique personality for this session
    personality = SwitchPersonality()
    
    # Send prompt for Netmiko to recognize
    try:
        channel.send(PROMPT.encode())
    except Exception:
        channel.close()
        return
    
    buf = ""
    command_count = 0
    last_log_time = time.time()
    log_templates = [
        "%SYS-5-CONFIG_I: Configuration changed",
        "%LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to up",
        "%LINEPROTO-5-UPDOWN: Line protocol on Interface GigabitEthernet0/1, changed state to up",
    ]
    
    try:
        while not channel.closed:
            try:
                data = channel.recv(256)
            except Exception:
                break
            if not data:
                break
            buf += data.decode("utf-8", errors="replace")
            # Process commands line by line
            while "\n" in buf or "\r" in buf:
                line, _, buf = buf.partition("\n")
                line = line.replace("\r", "").strip()
                logger.info("command: %s", line[:80] if line else "(empty line)")
                out = process_command(line, personality)
                if out:
                    channel.send(out.encode())
                
                # Send log every few commands (after command response)
                command_count += 1
                current_time = time.time()
                if command_count % 2 == 0 and (current_time - last_log_time) >= 2:
                    try:
                        log_msg = datetime.now().strftime("%b %d %H:%M:%S") + " switch " + random.choice(log_templates) + "\r\n"
                        channel.send(log_msg.encode())
                        last_log_time = current_time
                    except Exception:
                        pass
    except Exception as e:
        logger.error("handle_client: %s", e)
    finally:
        try:
            channel.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Professional Switch Simulator")
    parser.add_argument("--port", type=int, default=2222, help="Port to listen on (default: 2222)")
    parser.add_argument("--user", type=str, default=DEFAULT_USER, help="SSH username")
    parser.add_argument("--password", type=str, default=DEFAULT_PASS, help="SSH password")
    args = parser.parse_args()

    # Update globals
    global SIM_USER, SIM_PASS, LISTEN_PORT
    SIM_USER = args.user
    SIM_PASS = args.password
    LISTEN_PORT = args.port

    host_key = paramiko.RSAKey.generate(2048)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((LISTEN_HOST, LISTEN_PORT))
    sock.listen(5)
    logger.info("Switch Simulator SSH listening on %s:%s (user=%s)", LISTEN_HOST, LISTEN_PORT, SIM_USER)

    while True:
        try:
            client, addr = sock.accept()
            logger.info("connection from %s", addr)
            t = paramiko.Transport(client)
            t.add_server_key(host_key)
            server = SwitchSimulatorServer()
            try:
                t.start_server(server=server)
            except paramiko.SSHException as e:
                logger.warning("SSH neg failed: %s", e)
                t.close()
                continue
            thread = threading.Thread(target=handle_client, args=(t, server), daemon=True)
            thread.start()
        except KeyboardInterrupt:
            logger.info("shutdown")
            break
        except Exception as e:
            logger.error("accept: %s", e)
    sock.close()


if __name__ == "__main__":
    main()
