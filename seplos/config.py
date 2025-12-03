"""
Configuration loader with section support and backwards compatibility
"""

import os
import sys
import configparser
from .logging_setup import get_logger


def print_help():
    """Print usage help"""
    print("\nUsage:")
    print("  python seplos_bms_mqtt.py")
    print("")
    print("Seplos BMS MQTT gets the configuration from seplos_bms_mqtt.ini")
    print("Configuration file format (section-based):")
    print("")
    print("[general]")
    print("# Logging level: DEBUG, INFO, WARNING, ERROR")
    print("log_level = INFO")
    print("# Log file path (optional, leave empty to disable)")
    print("log_file = /var/log/seplos_bms_mqtt.log")
    print("")
    print("[serial]")
    print("# Serial port for Seplos BMS RS485 connection")
    print("port = /dev/ttyUSB0")
    print("# Baud rate (default 19200 for Seplos V3)")
    print("baudrate = 19200")
    print("")
    print("[mqtt]")
    print("# MQTT Broker settings")
    print("server = 192.168.1.100")
    print("port = 1883")
    print("username = ")
    print("password = ")
    print("# Topic prefix for all MQTT messages")
    print("prefix = seplos")
    print("# Publish mode: 'changed' (only when values change) or 'all' (every update)")
    print("publish_mode = changed")
    print("")
    print("[influxdb]")
    print("# Enable InfluxDB integration")
    print("enabled = false")
    print("url = http://localhost:8086")
    print("token = your-influxdb-token")
    print("org = your-org")
    print("bucket = seplos")
    print("# Minimum interval between writes per battery (seconds)")
    print("write_interval = 5")
    print("# Publish mode: 'changed' or 'all'")
    print("publish_mode = changed")
    print("")
    print("[health]")
    print("# Health check interval in seconds (0 to disable)")
    print("check_interval = 60")
    print("# Stale data timeout in seconds (mark battery offline if no data)")
    print("stale_timeout = 120")
    print("")
    print("publish_mode options:")
    print("  changed - Only publish/write when values change (reduces traffic)")
    print("  all     - Publish/write all data at each interval")
    print("")


class ConfigLoader:
    """Configuration loader with section support and backwards compatibility"""
    _instance = None
    _config = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ConfigLoader()
        return cls._instance

    def __init__(self, config_path='/app/seplos_bms_mqtt.ini'):
        self.config = configparser.ConfigParser()
        self.config_loaded = False
        self.config_path = config_path
        self._load_config()

    def _load_config(self):
        """Load configuration file"""
        log = get_logger()
        try:
            # Try multiple paths
            paths_to_try = [
                self.config_path,
                '/app/seplos_bms_mqtt.ini',
                '/app/config/seplos_bms_mqtt.ini',  # Docker volume mount path
                'seplos_bms_mqtt.ini',
                os.path.join(os.path.dirname(__file__), '..', 'seplos_bms_mqtt.ini')
            ]

            for path in paths_to_try:
                if os.path.exists(path):
                    self.config.read(path)
                    if self.config.sections():
                        self.config_loaded = True
                        self.config_path = path
                        log.debug(f"Config loaded from: {path}")
                        break
        except Exception as e:
            log.warning(f"Could not load config file: {e}")

    def get(self, section, key, default='mandatory', env_var=None):
        """Get config value from section/key with optional environment variable override"""
        log = get_logger()

        # First try environment variable if specified
        if env_var:
            value = os.getenv(env_var)
            if value is not None:
                return value

        # Also try legacy environment variable format (section_key)
        legacy_env = f"{section}_{key}".upper()
        value = os.getenv(legacy_env)
        if value is not None:
            return value

        # Try new section-based config
        try:
            if self.config_loaded and section in self.config:
                return self.config[section][key]
        except KeyError:
            pass

        # Try legacy flat config for backwards compatibility
        try:
            if self.config_loaded and 'seplos3mqtt' in self.config:
                # Map new names to old names for backwards compatibility
                legacy_map = {
                    ('serial', 'port'): 'serial',
                    ('mqtt', 'server'): 'mqtt_server',
                    ('mqtt', 'port'): 'mqtt_port',
                    ('mqtt', 'username'): 'mqtt_user',
                    ('mqtt', 'password'): 'mqtt_pass',
                    ('mqtt', 'prefix'): 'mqtt_prefix',
                    ('influxdb', 'enabled'): 'influxdb_enabled',
                    ('influxdb', 'url'): 'influxdb_url',
                    ('influxdb', 'token'): 'influxdb_token',
                    ('influxdb', 'org'): 'influxdb_org',
                    ('influxdb', 'bucket'): 'influxdb_bucket',
                    ('influxdb', 'write_interval'): 'influxdb_write_interval',
                    ('influxdb', 'publish_mode'): 'influxdb_publish_mode',
                    ('health', 'check_interval'): 'health_check_interval',
                    ('general', 'log_level'): 'log_level',
                }
                legacy_key = legacy_map.get((section, key), key)
                return self.config['seplos3mqtt'][legacy_key]
        except KeyError:
            pass

        if default != 'mandatory':
            return default
        else:
            print(f'Error: Parameter [{section}] {key} not found in config')
            print_help()
            sys.exit(1)


# Global config instance
_config_instance = None


def get_config(section, key, default='mandatory', env_var=None):
    """Helper function to get config values"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader.get_instance()
    return _config_instance.get(section, key, default, env_var)


class ConfigValidationError(Exception):
    """Configuration validation error"""
    pass


def validate_config():
    """
    Validate configuration values at startup.
    Raises ConfigValidationError for critical issues, logs warnings for others.
    """
    log = get_logger()
    errors = []
    warnings = []

    # Valid values for enums
    VALID_PUBLISH_MODES = ('changed', 'all')
    VALID_LOG_LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    VALID_BAUDRATES = (9600, 19200, 38400, 57600, 115200)

    # Validate serial port
    serial_port = get_config('serial', 'port', default=None)
    if serial_port:
        if not serial_port.startswith('/dev/') and not serial_port.startswith('COM'):
            warnings.append(f"Serial port '{serial_port}' doesn't look like a valid device path")

    # Validate baudrate
    baudrate = get_config('serial', 'baudrate', default='19200')
    try:
        baudrate_int = int(baudrate)
        if baudrate_int not in VALID_BAUDRATES:
            warnings.append(f"Baudrate {baudrate_int} is unusual. Valid options: {VALID_BAUDRATES}")
    except ValueError:
        errors.append(f"Invalid baudrate value: '{baudrate}' (must be integer)")

    # Validate MQTT port
    mqtt_port = get_config('mqtt', 'port', default='1883')
    try:
        mqtt_port_int = int(mqtt_port)
        if not 1 <= mqtt_port_int <= 65535:
            errors.append(f"MQTT port {mqtt_port_int} out of range (1-65535)")
    except ValueError:
        errors.append(f"Invalid MQTT port value: '{mqtt_port}' (must be integer)")

    # Validate MQTT publish_mode
    mqtt_publish_mode = get_config('mqtt', 'publish_mode', default='changed')
    if mqtt_publish_mode.lower() not in VALID_PUBLISH_MODES:
        errors.append(f"Invalid MQTT publish_mode: '{mqtt_publish_mode}'. Valid: {VALID_PUBLISH_MODES}")

    # Validate InfluxDB settings if enabled
    influxdb_enabled = get_config('influxdb', 'enabled', default='false')
    if influxdb_enabled.lower() == 'true':
        influxdb_publish_mode = get_config('influxdb', 'publish_mode', default='changed')
        if influxdb_publish_mode.lower() not in VALID_PUBLISH_MODES:
            errors.append(f"Invalid InfluxDB publish_mode: '{influxdb_publish_mode}'. Valid: {VALID_PUBLISH_MODES}")

        influxdb_url = get_config('influxdb', 'url', default='')
        if not influxdb_url.startswith('http://') and not influxdb_url.startswith('https://'):
            errors.append(f"Invalid InfluxDB URL: '{influxdb_url}' (must start with http:// or https://)")

        influxdb_token = get_config('influxdb', 'token', default='')
        if not influxdb_token or influxdb_token == 'your-influxdb-token':
            warnings.append("InfluxDB token not configured or using placeholder value")

        write_interval = get_config('influxdb', 'write_interval', default='5')
        try:
            write_interval_int = int(write_interval)
            if write_interval_int < 1:
                warnings.append(f"InfluxDB write_interval {write_interval_int}s is very low, may cause high load")
        except ValueError:
            errors.append(f"Invalid InfluxDB write_interval: '{write_interval}' (must be integer)")

    # Validate log_level
    log_level = get_config('general', 'log_level', default='INFO')
    if log_level.upper() not in VALID_LOG_LEVELS:
        warnings.append(f"Unknown log_level: '{log_level}'. Valid: {VALID_LOG_LEVELS}")

    # Validate health settings
    check_interval = get_config('health', 'check_interval', default='60')
    try:
        check_interval_int = int(check_interval)
        if check_interval_int < 0:
            errors.append(f"Health check_interval cannot be negative: {check_interval_int}")
    except ValueError:
        errors.append(f"Invalid health check_interval: '{check_interval}' (must be integer)")

    stale_timeout = get_config('health', 'stale_timeout', default='120')
    try:
        stale_timeout_int = int(stale_timeout)
        if stale_timeout_int < 0:
            errors.append(f"Health stale_timeout cannot be negative: {stale_timeout_int}")
    except ValueError:
        errors.append(f"Invalid health stale_timeout: '{stale_timeout}' (must be integer)")

    # Log warnings
    for warning in warnings:
        log.warning(f"Config warning: {warning}")

    # Raise on errors
    if errors:
        for error in errors:
            log.error(f"Config error: {error}")
        raise ConfigValidationError(f"Configuration validation failed with {len(errors)} error(s)")
