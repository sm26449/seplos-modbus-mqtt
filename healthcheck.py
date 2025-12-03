#!/usr/bin/env python3
"""
Docker healthcheck script for Seplos BMS MQTT

Checks:
1. Health status file exists and is recent (< 120 seconds old)
2. Status is 'healthy'
3. MQTT connection is active

Exit codes:
0 = healthy
1 = unhealthy
"""

import os
import sys
import time

HEALTH_FILE = '/tmp/seplos_health'
MAX_AGE_SECONDS = 120  # Health file should be updated within this time


def check_health():
    """Check if the service is healthy"""

    # Check if health file exists
    if not os.path.exists(HEALTH_FILE):
        print("Health file not found - service may still be starting")
        return 1

    try:
        with open(HEALTH_FILE, 'r') as f:
            lines = f.readlines()

        if len(lines) < 2:
            print("Invalid health file format")
            return 1

        # Check timestamp (first line)
        timestamp = int(lines[0].strip())
        age = time.time() - timestamp

        if age > MAX_AGE_SECONDS:
            print(f"Health file is stale ({int(age)}s old, max {MAX_AGE_SECONDS}s)")
            return 1

        # Check status (second line)
        status = lines[1].strip()
        if status != 'healthy':
            print(f"Service status: {status}")
            return 1

        # Check MQTT (third line)
        if len(lines) >= 3:
            mqtt_line = lines[2].strip()
            if mqtt_line == 'mqtt:False':
                print("MQTT disconnected")
                return 1

        print(f"Healthy (last check {int(age)}s ago)")
        return 0

    except Exception as e:
        print(f"Error reading health file: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(check_health())
