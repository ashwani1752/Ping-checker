"""
Network Device Connectivity Checker using Ping
----------------------------------------------
A Flask web app that checks whether a device is reachable by running
the operating system's ping command, and stores every test in SQLite.
"""

import ipaddress
import os
import platform
import re
import sqlite3
import subprocess
from datetime import datetime

from flask import Flask, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)

# ---------------------------------------------------------------- settings
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")  # SQLite file location
PING_COUNT = 1          # number of packets to send
TIMEOUT_SECONDS = 2     # how long ping waits for a reply

# A hostname is made of labels separated by dots (e.g. www.google.com).
# Each label: letters/digits/hyphens, cannot start or end with a hyphen.
HOSTNAME_PATTERN = re.compile(
    r"^(?=.{1,253}$)[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
)


# ---------------------------------------------------------------- database
def get_db():
    """Open a database connection. Rows can be read like dictionaries."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the ping_history table if it does not exist yet."""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ping_history (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                host             TEXT    NOT NULL,
                tested_at        TEXT    NOT NULL,
                status           TEXT    NOT NULL,
                response_time    REAL,
                packets_sent     INTEGER NOT NULL,
                packets_received INTEGER NOT NULL,
                packet_loss      REAL    NOT NULL
            )
            """
        )


def save_result(result):
    """Insert one ping result into the history table."""
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO ping_history
            (host, tested_at, status, response_time,
             packets_sent, packets_received, packet_loss)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["host"], result["tested_at"], result["status"],
                result["response_time"], result["packets_sent"],
                result["packets_received"], result["packet_loss"],
            ),
        )


# -------------------------------------------------------------- validation
def validate_host(raw_host):
    """
    Check the user's input. Returns (True, cleaned_host) when valid,
    or (False, error_message) when invalid.
    This protects us from malicious input such as '8.8.8.8; rm -rf /'
    or options like '-t' being passed to the ping command.
    """
    host = (raw_host or "").strip()

    if not host:
        return False, "Please enter an IP address or hostname."
    if len(host) > 253:
        return False, "Input is too long."

    # If it only contains digits and dots, it must be a valid IPv4 address.
    if re.fullmatch(r"[0-9.]+", host):
        try:
            ipaddress.IPv4Address(host)
        except ValueError:
            return False, "Invalid IPv4 address. Example: 192.168.1.1"
        return True, host

    # Otherwise it must look like a valid hostname (this also blocks a
    # leading '-', spaces, semicolons, pipes, etc.).
    if HOSTNAME_PATTERN.match(host):
        return True, host

    return False, "Invalid hostname. Use letters, digits, hyphens and dots only."


# -------------------------------------------------------------------- ping
def build_ping_command(host):
    """Build the ping command as a LIST (never a single shell string)."""
    system = platform.system().lower()
    if system == "windows":
        # -n = count, -w = timeout in milliseconds
        return ["ping", "-n", str(PING_COUNT), "-w", str(TIMEOUT_SECONDS * 1000), host]
    if system == "darwin":  # macOS: -W is in milliseconds
        return ["ping", "-c", str(PING_COUNT), "-W", str(TIMEOUT_SECONDS * 1000), host]
    # Linux: -c = count, -W = timeout in seconds
    return ["ping", "-c", str(PING_COUNT), "-W", str(TIMEOUT_SECONDS), host]


def run_ping(host):
    """Run ping for a validated host and return a result dictionary."""
    command = build_ping_command(host)
    online = False
    latency = None
    message = ""

    try:
        # shell=False (default) means the OS runs 'ping' directly with the
        # arguments we give, so user input can never be run as a command.
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=TIMEOUT_SECONDS + 8,
            shell=False,
        )
        output = completed.stdout + completed.stderr

        # A real reply contains a TTL value. On Windows, a "Destination host
        # unreachable" message also returns code 0, so we check TTL too.
        got_reply = completed.returncode == 0 and re.search(r"ttl=", output, re.I)

        if got_reply:
            online = True
            # Matches "time=12ms", "time<1ms" and "time=0.045 ms"
            match = re.search(r"time[=<]\s*([\d.]+)\s*ms", output, re.I)
            if match:
                latency = float(match.group(1))
            message = f"Success! {host} is reachable."
        else:
            message = (f"{host} is unreachable. The device may be switched off, "
                       "not on the network, blocking ping, or the name cannot be resolved.")

    except subprocess.TimeoutExpired:
        message = f"The request to {host} timed out. The device is not responding."
    except FileNotFoundError:
        message = "The 'ping' command was not found on this computer."
    except OSError as error:
        message = f"Could not run ping: {error}"

    received = PING_COUNT if online else 0
    loss = round((PING_COUNT - received) / PING_COUNT * 100, 1)

    return {
        "host": host,
        "tested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Online" if online else "Offline",
        "response_time": latency,
        "packets_sent": PING_COUNT,
        "packets_received": received,
        "packet_loss": loss,
        "message": message,
    }


# --------------------------------------------------------------- statistics
def get_stats():
    """Return dashboard numbers and the 5 most recent tests."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM ping_history").fetchone()[0]
        online = conn.execute(
            "SELECT COUNT(*) FROM ping_history WHERE status = 'Online'").fetchone()[0]
        avg = conn.execute(
            "SELECT AVG(response_time) FROM ping_history "
            "WHERE status = 'Online' AND response_time IS NOT NULL").fetchone()[0]
        recent = conn.execute(
            "SELECT host, tested_at, status, response_time, packet_loss "
            "FROM ping_history ORDER BY id DESC LIMIT 5").fetchall()

    return {
        "total": total,
        "online": online,
        "offline": total - online,
        "avg_response": round(avg, 1) if avg is not None else None,
        "recent": [dict(row) for row in recent],
    }


# ------------------------------------------------------------------- routes
@app.route("/")
def index():
    """Home page: ping form + dashboard."""
    return render_template("index.html")


@app.route("/api/ping", methods=["POST"])
def api_ping():
    """Receive a host as JSON, ping it, save the result, return JSON."""
    data = request.get_json(silent=True) or {}
    valid, value = validate_host(data.get("host"))
    if not valid:
        return jsonify({"error": value}), 400

    result = run_ping(value)
    try:
        save_result(result)
    except sqlite3.Error:
        return jsonify({"error": "Could not save the result to the database."}), 500
    return jsonify(result)


@app.route("/api/stats")
def api_stats():
    """Return dashboard statistics as JSON."""
    try:
        return jsonify(get_stats())
    except sqlite3.Error:
        return jsonify({"error": "Database error."}), 500


@app.route("/history")
def history():
    """Show every saved ping test (newest first)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM ping_history ORDER BY id DESC").fetchall()
    return render_template("history.html", rows=rows)


@app.route("/history/clear", methods=["POST"])
def clear_history():
    """Delete all history, then go back to the history page."""
    with get_db() as conn:
        conn.execute("DELETE FROM ping_history")
    return redirect(url_for("history"))


# ------------------------------------------------------------------ startup
init_db()  # make sure the table exists before the first request

if __name__ == "__main__":
    app.run(debug=True)
