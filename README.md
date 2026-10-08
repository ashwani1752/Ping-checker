# Network Device Connectivity Checker using Ping

A Flask web app that checks whether a device is reachable using the
operating system's ping command and stores the results in SQLite.

## Run
1. python -m venv venv
2. Activate it (Windows: venv\Scripts\activate | Linux/macOS: source venv/bin/activate)
3. pip install -r requirements.txt
4. python app.py
5. Open http://127.0.0.1:5000

`database.db` is created automatically on the first run.

## Features
- Ping an IPv4 address or hostname (validated, no shell=True)
- Status, latency, packets sent/received, packet loss
- Dashboard with totals, average response time and chart
- History page with Clear History button

## Test inputs
- 127.0.0.1 or localhost -> Online
- Your router (e.g. 192.168.1.1) -> Online
- 192.168.1.250 (unused address) -> Offline
- 999.1.1.1 or "8.8.8.8; dir" -> Validation error

## Tech
Python, Flask, SQLite, HTML5, CSS3, JavaScript
