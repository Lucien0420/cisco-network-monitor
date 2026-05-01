"""
Fake SSH switch: Paramiko-based SSH server for Netmiko (main.py) to connect.
Run in WSL, listen on port 2222. devices.json: WSL IP, port 2222, device_type: cisco_ios.
Supports: show system temperature, show processes cpu, show interfaces, show chassis environment.
"""
import os
import random
import socket
import threading
import logging
import sys
import argparse
import time
from datetime import datetime

import paramiko

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - FakeSwitchSSH - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default credentials
DEFAULT_USER = os.environ.get("FAKE_SWITCH_USER", "switch")
DEFAULT_PASS = os.environ.get("FAKE_SWITCH_PASS", "switch123")
LISTEN_HOST = os.environ.get("FAKE_SWITCH_HOST", "0.0.0.0")

# Global vars, updated by args
FAKE_USER = DEFAULT_USER
FAKE_PASS = DEFAULT_PASS
LISTEN_PORT = 2222

# Netmiko prompt (cisco_ios expects #)
PROMPT = "Switch# "


def make_temperature():
    v = 40.0 + random.gauss(0, 2)
    return max(30, min(55, v))


def make_cpu():
    v = 30.0 + random.gauss(0, 5)
    return max(5, min(95, v))


def make_memory():
    v = 60.0 + random.gauss(0, 3)
    return max(40, min(85, v))


def process_command(line: str) -> str:
    """Process a command and return the response (including command echo)."""
    line = (line or "").strip()
    if not line:
        # Empty line (Netmiko newline): return prompt
        return PROMPT
    
    line_lower = line.lower()
    
    # Handle terminal commands (required for Netmiko init)
    if "terminal width" in line_lower:
        # Return command echo + newline + prompt
        return f"{line}\r\n{PROMPT}"
    
    if "terminal length" in line_lower:
        # Return command echo + newline + prompt
        return f"{line}\r\n{PROMPT}"
    
    if "terminal" in line_lower:
        return f"{line}\r\n{PROMPT}"
    
    if "temperature" in line_lower or ("show" in line_lower and "temp" in line_lower):
        t = make_temperature()
        output = f"{line}\r\nSystem Temperature:\r\n  Inlet Temperature: {t:.1f} °C\r\n  Threshold: 85°C\r\n  Status: OK\r\n{PROMPT}"
        return output
    
    if "processes" in line_lower and "cpu" in line_lower or "cpu" in line_lower:
        c = make_cpu()
        c1, c2 = max(0, c - 5), max(0, c - 8)
        output = f"{line}\r\nCPU Load:\r\n  5-second CPU: {c:.1f} %\r\n  1-minute CPU: {c1:.1f} %\r\n  5-minute CPU: {c2:.1f} %\r\n{PROMPT}"
        return output
    
    if "chassis" in line_lower and "environment" in line_lower:
        t = make_temperature()
        output = f"{line}\r\nChassis Environment:\r\n  Temperature: {t:.1f} C\r\n  Status: OK\r\n{PROMPT}"
        return output
    
    if "interface" in line_lower:
        output = (
            f"{line}\r\nGigabitEthernet0/1  up  up\r\n"
            "GigabitEthernet0/2  up  up\r\n"
            "GigabitEthernet0/3  down  down\r\n"
            f"{PROMPT}"
        )
        return output
    
    if "memory" in line_lower:
        m = make_memory()
        output = f"{line}\r\nMemory Usage: {m:.1f} %\r\n{PROMPT}"
        return output
    
    if "version" in line_lower:
        output = f"{line}\r\nCisco IOS Software, Version 12.2(58)SE2\r\nSystem uptime is 45 days.\r\n{PROMPT}"
        return output
    
    if "exit" in line_lower or "quit" in line_lower:
        return ""
    
    return f"{line}\r\n% Invalid command\r\n{PROMPT}"


class FakeSwitchSSHServer(paramiko.ServerInterface):
    def __init__(self):
        self.event = threading.Event()

    def check_auth_password(self, username: str, password: str) -> int:
        if username == FAKE_USER and password == FAKE_PASS:
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
                out = process_command(line)
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
    parser = argparse.ArgumentParser(description="Fake SSH Switch")
    parser.add_argument("--port", type=int, default=2222, help="Port to listen on (default: 2222)")
    parser.add_argument("--user", type=str, default=DEFAULT_USER, help="SSH username")
    parser.add_argument("--password", type=str, default=DEFAULT_PASS, help="SSH password")
    args = parser.parse_args()

    # Update globals
    global FAKE_USER, FAKE_PASS, LISTEN_PORT
    FAKE_USER = args.user
    FAKE_PASS = args.password
    LISTEN_PORT = args.port

    host_key = paramiko.RSAKey.generate(2048)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((LISTEN_HOST, LISTEN_PORT))
    sock.listen(5)
    logger.info("Fake switch SSH listening on %s:%s (user=%s)", LISTEN_HOST, LISTEN_PORT, FAKE_USER)

    while True:
        try:
            client, addr = sock.accept()
            logger.info("connection from %s", addr)
            t = paramiko.Transport(client)
            t.add_server_key(host_key)
            server = FakeSwitchSSHServer()
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
