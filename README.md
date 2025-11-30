# Seplos BMS MQTT

**Seplos BMS V3 to MQTT/InfluxDB Bridge with Home Assistant Auto-Discovery**

An enhanced, modular Python application for monitoring Seplos BMS V3 batteries via RS485 Modbus RTU. Publishes data to MQTT with Home Assistant auto-discovery and optionally to InfluxDB for time-series storage.

> **Fork Info**: This project is a significantly enhanced fork of [Seplos3MQTT](https://github.com/ferelarg/Seplos3MQTT) with major refactoring, new features, and improved reliability.

## Features

### Core Features
- **RS485 Modbus RTU Snooper** - Passive listening on the RS485 bus (no active polling)
- **Multi-Battery Support** - Automatically detects and monitors up to 16 batteries
- **Home Assistant Auto-Discovery** - Batteries appear automatically in HA
- **Pack Aggregation** - Virtual "Pack" entity with totals/averages across all batteries

### New in v2.5
- **Configuration Validation** - Validates config at startup, catches errors early
- **Environment Variables** - Full support for Docker env vars (no config file needed)
- **Improved Health Check** - Docker healthcheck verifies MQTT connection and data freshness
- **Modular Architecture** - Clean separation into reusable components
- **InfluxDB Integration** - Optional time-series database storage
- **MQTT Command Subscription** - On-demand value requests via `R/seplos/#` topic
- **Health Monitoring** - Periodic health checks with stale data detection
- **Smart Publish Modes** - `changed` (only on value change) or `all` (every update)
- **Automatic Reconnection** - MQTT and InfluxDB reconnect with exponential backoff
- **File Logging** - Optional log file output
- **Docker Ready** - Optimized Alpine-based container with proper healthcheck

### Data Published

For each battery:
- **Cell Voltages** (1-16) - Individual cell voltage readings
- **Temperature Sensors** (1-6) - Temperature readings from all sensors
- **Pack Voltage** - Total battery voltage
- **Current** - Charge/discharge current (positive = charging)
- **SOC** - State of Charge percentage
- **SOH** - State of Health percentage
- **Capacity** - Remaining and rated capacity
- **Cycle Count** - Battery charge cycles
- **Alarms** - Active alarm flags
- **Status** - Charging/Discharging/Standby

Pack Aggregate:
- **Total Voltage** - Sum of all battery voltages
- **Total Current** - Sum of all currents
- **Average SOC** - Average state of charge
- **Min/Max Values** - Lowest/highest cell voltages across all batteries
- **Batteries Online** - Count of active batteries

## Architecture

```
seplos-bms-mqtt/
├── seplos/                      # Python package
│   ├── __init__.py              # Package exports
│   ├── config.py                # Configuration loader + validation
│   ├── logging_setup.py         # Logging configuration
│   ├── mqtt_manager.py          # MQTT connection & publishing
│   ├── influxdb_manager.py      # InfluxDB integration
│   ├── serial_snooper.py        # RS485 Modbus RTU parser
│   ├── pack_aggregator.py       # Multi-battery aggregation
│   ├── health_monitor.py        # Health checks & watchdog
│   └── utils.py                 # Shared utilities
├── seplos_bms_mqtt.py           # Main entry point
├── healthcheck.py               # Docker healthcheck script
├── Dockerfile                   # Docker image definition
├── service.yaml                 # Service definition with variables
└── docker-compose.example.yml   # Example docker-compose for deployment
```

## Quick Start

### Prerequisites
- USB to RS485 adapter connected to Seplos BMS RS485 port
- MQTT Broker (e.g., Mosquitto)
- Docker (recommended) or Python 3.9+

### 1. Clone the Repository

```bash
git clone https://github.com/sm26449/diysolar-toolkit.git
cd diysolar-toolkit/seplos-bms-mqtt
```

### 2. Create Deployment Directory

```bash
# Create directory structure
export DOCKER_ROOT=/opt/docker
sudo mkdir -p ${DOCKER_ROOT}/seplos-bms-mqtt/config

# Copy example config
sudo cp seplos_bms_mqtt.ini.example ${DOCKER_ROOT}/seplos-bms-mqtt/config/seplos_bms_mqtt.ini
```

### 3. Configure

You have two options: **config file** or **environment variables** (or both).

#### Option A: Config File

Edit the config file:

```bash
sudo nano ${DOCKER_ROOT}/seplos-bms-mqtt/config/seplos_bms_mqtt.ini
```

```ini
[general]
log_level = INFO
log_file =

[serial]
port = /dev/ttyUSB0
baudrate = 19200

[mqtt]
server = 192.168.1.100
port = 1883
username = seplos
password = your_password
prefix = seplos
publish_mode = changed

[influxdb]
enabled = false
url = http://localhost:8086
token = your-influxdb-token
org = your-org
bucket = seplos
write_interval = 5
publish_mode = changed

[health]
check_interval = 60
stale_timeout = 120
```

#### Option B: Environment Variables (No Config File Needed)

All settings can be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SERIAL_PORT` | /dev/ttyUSB0 | Serial port for RS485 adapter |
| `SERIAL_BAUDRATE` | 19200 | Baud rate (19200 for Seplos V3) |
| `MQTT_SERVER` | localhost | MQTT broker address |
| `MQTT_PORT` | 1883 | MQTT broker port |
| `MQTT_USERNAME` | (empty) | MQTT username |
| `MQTT_PASSWORD` | (empty) | MQTT password |
| `MQTT_PREFIX` | seplos | Topic prefix |
| `MQTT_PUBLISH_MODE` | changed | `changed` or `all` |
| `INFLUXDB_ENABLED` | false | Enable InfluxDB |
| `INFLUXDB_URL` | http://localhost:8086 | InfluxDB URL |
| `INFLUXDB_TOKEN` | (empty) | InfluxDB API token |
| `INFLUXDB_ORG` | (empty) | InfluxDB organization |
| `INFLUXDB_BUCKET` | seplos | InfluxDB bucket |
| `INFLUXDB_WRITE_INTERVAL` | 5 | Min seconds between writes |
| `INFLUXDB_PUBLISH_MODE` | changed | `changed` or `all` |
| `HEALTH_CHECK_INTERVAL` | 60 | Health check interval (0 = disable) |
| `HEALTH_STALE_TIMEOUT` | 120 | Mark battery offline after N seconds |
| `GENERAL_LOG_LEVEL` | INFO | DEBUG, INFO, WARNING, ERROR |

### 4. Build Docker Image

```bash
# Build the image
docker build -t seplos-bms-mqtt:v2.5 .
```

### 5. Deploy

#### Option A: Docker Run (with config file)

```bash
docker run -d \
  --name seplos-bms-mqtt \
  --restart unless-stopped \
  --network=host \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  -v ${DOCKER_ROOT}/seplos-bms-mqtt/config/seplos_bms_mqtt.ini:/app/seplos_bms_mqtt.ini:ro \
  seplos-bms-mqtt:v2.5
```

#### Option B: Docker Run (with environment variables)

```bash
docker run -d \
  --name seplos-bms-mqtt \
  --restart unless-stopped \
  --network=host \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  -e MQTT_SERVER=192.168.1.100 \
  -e MQTT_USERNAME=seplos \
  -e MQTT_PASSWORD=your_password \
  -e INFLUXDB_ENABLED=true \
  -e INFLUXDB_URL=http://localhost:8086 \
  -e INFLUXDB_TOKEN=your-token \
  -e INFLUXDB_ORG=your-org \
  seplos-bms-mqtt:v2.5
```

#### Option C: Docker Compose

```bash
# Copy example compose file
cp docker-compose.example.yml docker-compose.yml

# Edit with your settings
nano docker-compose.yml

# Deploy
docker-compose up -d
```

### 6. Verify Deployment

```bash
# Check container status
docker ps | grep seplos

# Check logs
docker logs -f seplos-bms-mqtt

# Check health status
docker inspect --format='{{.State.Health.Status}}' seplos-bms-mqtt
```

## Docker Compose Example

See `docker-compose.example.yml` for a complete example:

```yaml
services:
  seplos-bms-mqtt:
    build:
      context: .
      dockerfile: Dockerfile
    image: seplos-bms-mqtt:v2.5
    container_name: seplos-bms-mqtt
    restart: unless-stopped
    network_mode: host
    devices:
      - ${SERIAL_PORT:-/dev/ttyUSB0}:${SERIAL_PORT:-/dev/ttyUSB0}
    environment:
      - MQTT_SERVER=${MQTT_SERVER:-localhost}
      - MQTT_PORT=${MQTT_PORT:-1883}
      - MQTT_USERNAME=${MQTT_USERNAME:-}
      - MQTT_PASSWORD=${MQTT_PASSWORD:-}
      - MQTT_PREFIX=${MQTT_PREFIX:-seplos}
      - INFLUXDB_ENABLED=${INFLUXDB_ENABLED:-false}
      - INFLUXDB_URL=${INFLUXDB_URL:-http://localhost:8086}
      - INFLUXDB_TOKEN=${INFLUXDB_TOKEN:-}
      - INFLUXDB_ORG=${INFLUXDB_ORG:-}
      - INFLUXDB_BUCKET=${INFLUXDB_BUCKET:-seplos}
    volumes:
      - ${DOCKER_ROOT:-/opt/docker}/seplos-bms-mqtt/config/seplos_bms_mqtt.ini:/app/seplos_bms_mqtt.ini:ro
    healthcheck:
      test: ["CMD", "python3", "/app/healthcheck.py"]
      interval: 60s
      timeout: 10s
      start_period: 60s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## Infrastructure Setup

### MQTT (Mosquitto) - Create User

```bash
# Enter the mosquitto container
docker exec -it mosquitto sh

# Create password file and add user
mosquitto_passwd -c /mosquitto/config/pwfile seplos
# Enter password when prompted

# Restart container
docker restart mosquitto
```

### InfluxDB - Create Bucket and Token

```bash
# Create bucket for Seplos data
docker exec influxdb influx bucket create \
  --name seplos \
  --org your-org \
  --retention 0

# Create API token with read/write access
docker exec influxdb influx auth create \
  --org your-org \
  --description "Seplos BMS MQTT token" \
  --read-buckets \
  --write-buckets

# Copy the token from output and use in config/env var
```

### Home Assistant Integration

Batteries will auto-discover via MQTT. Ensure your HA `configuration.yaml` has:

```yaml
mqtt:
  broker: 192.168.1.100
  port: 1883
  username: homeassistant
  password: your_ha_mqtt_password
  discovery: true
  discovery_prefix: homeassistant
```

## MQTT Topics

### Published Topics

```
seplos/battery_1/soc          # State of Charge
seplos/battery_1/voltage      # Pack voltage
seplos/battery_1/current      # Current (+ charging, - discharging)
seplos/battery_1/cell_1       # Cell 1 voltage
...
seplos/battery_1/cell_16      # Cell 16 voltage
seplos/battery_1/temp_1       # Temperature sensor 1
...
seplos/battery_1/state        # online/offline
seplos/pack/total_voltage     # Aggregate voltage
seplos/pack/total_current     # Aggregate current
seplos/pack/average_soc       # Average SOC
seplos/pack/batteries_online  # Count of online batteries
seplos/health/uptime          # Service uptime
seplos/health/mqtt_connected  # MQTT connection status
```

### Command Topics (On-Demand Requests)

When using `publish_mode = changed`, values only publish when they change. To request current values on-demand:

```bash
# Request single value
mosquitto_pub -t "R/seplos/battery_1/soc" -m ""

# Request all values for a battery
mosquitto_pub -t "R/seplos/battery_1/all" -m ""

# Request pack aggregate
mosquitto_pub -t "R/seplos/pack/all" -m ""
```

## Hardware Wiring

### RS485 Pinout

![Seplos RS485 Pinout](img/rs485pinout.jpeg)

### Wiring Diagram

![Seplos v3 Wiring](img/seplos_wiring.jpeg)
![Seplos v4 Wiring](img/seplosV4_wiring.png)

Connect USB-RS485 adapter to any available RS485 port on the Seplos BMS. The software operates in snooper/passive mode, listening to communication between the BMS master and batteries.

## Troubleshooting

### No Data Received
1. Check serial port permissions: `sudo chmod 666 /dev/ttyUSB0`
2. Verify baud rate (19200 for Seplos V3)
3. Check RS485 wiring (A/B connections)
4. Enable DEBUG logging: `GENERAL_LOG_LEVEL=DEBUG`

### MQTT Connection Issues
1. Verify broker is running: `docker logs mosquitto`
2. Test connection: `mosquitto_pub -h HOST -u USER -P PASS -t test -m "hello"`
3. Check firewall for port 1883

### InfluxDB Connection Issues
1. Verify token has read/write permissions
2. Check bucket exists in correct organization
3. Test with: `docker exec influxdb influx ping`

### Docker Health Check Failing
```bash
# Check health status
docker inspect --format='{{json .State.Health}}' seplos-bms-mqtt | jq

# Check healthcheck output
docker exec seplos-bms-mqtt python3 /app/healthcheck.py
```

### Device Disconnected Error
```
device reports readiness to read but returned no data
```
This usually means another process is using the serial port. Check with:
```bash
lsof /dev/ttyUSB0
fuser /dev/ttyUSB0
```

## Release Notes

### v2.5 (Current)
- Added configuration validation at startup
- Added environment variables support for all settings
- Improved Docker healthcheck (verifies MQTT connection and data freshness)
- Added healthcheck.py script for Docker
- Health monitor writes status file for Docker to check
- Logging configuration with rotation in docker-compose

### v2.4
- Added MQTT command subscription for on-demand value requests
- Added `mqtt_commands_received` health metric
- Fixed topic prefix duplication in republish handler

### v2.3
- Complete modular refactoring
- Added InfluxDB integration with reconnection
- Added Pack Aggregator for multi-battery systems
- Added Health Monitor with stale detection
- Added publish_mode support (changed/all)
- Added file logging support
- Improved MQTT reconnection with exponential backoff

### v1.0 (Original)
- Basic Seplos BMS V3 to MQTT bridge
- Home Assistant auto-discovery

## Credits

- **Original Project**: [Seplos3MQTT](https://github.com/ferelarg/Seplos3MQTT)
- **Enhanced Fork**: DIYSolar.ro

## License

MIT License - See [LICENSE](LICENSE) file.

## Contact

- **Email**: sm26449@diysolar.ro
- **Project**: https://github.com/sm26449/diysolar-toolkit

---

**Disclaimer**: THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND. Use at your own risk when working with battery systems.
