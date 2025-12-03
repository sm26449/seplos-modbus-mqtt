# Changelog

All notable changes to Seplos BMS MQTT will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.5.0] - 2024-12-03

### Added
- **Thread Safety in PackAggregator**
  - Added `threading.Lock()` for battery data dictionary access
  - Protected methods: `update_battery_data()`, `get_battery_data()`, `get_all_batteries()`, `get_online_batteries()`, `get_stale_batteries()`
  - Getter methods now return copies of data to prevent external modification

### Fixed
- **Docker Volume Mount Path**
  - Added `/app/config/seplos_bms_mqtt.ini` to config search paths
  - Fixes issue when using docker-setup template which mounts config to `/app/config/`
- **Version Consistency**
  - All files now report version 2.5:
    - `seplos/__init__.py`
    - `seplos/pack_aggregator.py` (MQTT autodiscovery)
    - `seplos/serial_snooper.py` (MQTT autodiscovery)
    - `Dockerfile`

### Changed
- Config search order in `config.py`:
  1. Constructor provided path
  2. `/app/seplos_bms_mqtt.ini`
  3. `/app/config/seplos_bms_mqtt.ini` (Docker volume mount)
  4. `seplos_bms_mqtt.ini` (current directory)
  5. Relative to module directory

## [2.4.0] - 2024-11-30

### Added
- **InfluxDB Integration**
  - Direct write to InfluxDB v2
  - Configurable write interval per battery
  - Publish mode: 'changed' or 'all'
- **Pack Aggregator**
  - Calculates aggregate values for entire battery pack
  - MQTT autodiscovery for Home Assistant
  - Metrics: total voltage, current, power, SOC stats, cell voltages, temperatures
- **Health Monitor**
  - Periodic health checks
  - Stale data detection
  - Battery online/offline status
- **Configuration Validation**
  - Validates config at startup
  - Checks for valid values, ranges, and formats
  - Warnings for unusual but valid configurations

### Changed
- Modular architecture with separate manager classes
- Section-based INI configuration (backwards compatible)
- Improved logging with configurable levels and file output

## [2.3.0] - 2024-11-28

### Added
- **MQTT Manager**
  - Reconnection handling
  - `publish_if_changed()` for reduced traffic
  - Retain flag support
- **Logging Setup**
  - Configurable log levels
  - Optional file logging
  - Structured log format

### Fixed
- MQTT connection stability issues
- Message queue handling during disconnection

## [2.2.0] - 2024-11-26

### Added
- **Serial Snooper**
  - Modbus RTU protocol parsing
  - CRC16 validation
  - Multi-battery support (addresses 0x00-0x0F)
- **MQTT Autodiscovery**
  - Home Assistant integration
  - Device grouping per battery
  - Sensor state classes and units

### Changed
- Separated serial communication from data processing
- Improved error handling for malformed frames

## [2.1.0] - 2024-11-24

### Added
- **Docker Support**
  - Dockerfile with Python 3.11-slim
  - Health check script
  - docker-compose.example.yml
- **Environment Variables**
  - Override config values via environment
  - Legacy format support (SECTION_KEY)

## [2.0.0] - 2024-11-22

### Added
- **Complete Rewrite**
  - Modular Python package structure
  - Type hints throughout
  - Comprehensive error handling
- **Seplos V3 Protocol Support**
  - All register ranges (0x1000-0x10FF)
  - Cell voltages, temperatures, SOC, SOH
  - Alarms, protections, balancing status
  - Current limits (charge/discharge)

### Changed
- From single script to package structure
- Configuration from command line to INI file

## [1.0.0] - 2024-11-01

### Added
- Initial release
- Basic Seplos BMS serial communication
- MQTT publishing
- Single battery support

---

## Version History Summary

| Version | Date | Highlights |
|---------|------|------------|
| 2.5.0 | 2024-12-03 | Thread safety, Docker volume path fix, version consistency |
| 2.4.0 | 2024-11-30 | InfluxDB integration, Pack Aggregator, Health Monitor |
| 2.3.0 | 2024-11-28 | MQTT Manager improvements, Logging setup |
| 2.2.0 | 2024-11-26 | Serial Snooper, MQTT Autodiscovery |
| 2.1.0 | 2024-11-24 | Docker support, Environment variables |
| 2.0.0 | 2024-11-22 | Complete rewrite, Seplos V3 protocol |
| 1.0.0 | 2024-11-01 | Initial release |

---

## Files Modified in v2.5.0

### `seplos/config.py`
```python
paths_to_try = [
    self.config_path,
    '/app/seplos_bms_mqtt.ini',
    '/app/config/seplos_bms_mqtt.ini',  # NEW: Docker volume mount path
    'seplos_bms_mqtt.ini',
    os.path.join(os.path.dirname(__file__), '..', 'seplos_bms_mqtt.ini')
]
```

### `seplos/pack_aggregator.py`
```python
import threading

class PackAggregator:
    def __init__(self, ...):
        self._lock = threading.Lock()  # NEW: Thread safety

    def update_battery_data(self, batt_id, data_type, value):
        with self._lock:  # Protected access
            ...

    def get_battery_data(self, batt_id):
        with self._lock:
            return self.batteries.get(batt_id, {}).copy()  # Return copy
```

### `seplos/serial_snooper.py`
- Version updated from 2.4 to 2.5 in MQTT autodiscovery payloads
