"""
InfluxDB Manager with connection handling, retry logic, and write modes
"""

import time
import threading
from .logging_setup import get_logger

# Retry configuration
RETRY_MAX_ATTEMPTS = 10
RETRY_INITIAL_DELAY = 2  # seconds
RETRY_MAX_DELAY = 60  # seconds
RETRY_BACKOFF_FACTOR = 2


class InfluxDBManager:
    """
    InfluxDB Manager class - handles InfluxDB connection and writes

    Features:
    - Automatic reconnection with exponential backoff
    - Rate limiting per battery
    - Publish-on-change mode support
    - Batched writes for better performance
    - Connection statistics
    """

    def __init__(self, url, token, org, bucket, enabled=True, write_interval=5, publish_mode='changed'):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.enabled = enabled
        self.client = None
        self.write_api = None
        self.connected = False
        self.last_write_time = {}
        self.write_interval = write_interval
        self.publish_mode = publish_mode
        self.last_values = {}
        self.lock = threading.Lock()
        self.log = get_logger()

        # Reconnect settings
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5
        self.max_reconnect_delay = 300

        self.last_reconnect_attempt = 0

        # Stats
        self.writes_total = 0
        self.writes_failed = 0
        self.last_successful_write = 0
        self.reconnect_count = 0

        if self.enabled and self.url and self.token:
            self._setup_client_with_retry()

    def _setup_client(self):
        """Setup InfluxDB client"""
        try:
            from influxdb_client import InfluxDBClient, WriteOptions

            self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
            # Use batching write API for better performance
            self.write_api = self.client.write_api(write_options=WriteOptions(
                batch_size=100,
                flush_interval=10_000,
                jitter_interval=2_000,
                retry_interval=5_000,
                max_retries=3,
                max_retry_delay=30_000,
                exponential_base=2
            ))

            # Test connection with health check
            health = self.client.health()
            if health.status == "pass":
                self.connected = True
                self.reconnect_attempts = 0
                self.reconnect_delay = 5
                self.log.info(f"InfluxDB connected to {self.url}, bucket: {self.bucket}, mode: {self.publish_mode}")
            else:
                self.log.warning(f"InfluxDB health check failed: {health.message}")
                self.connected = False
        except ImportError:
            self.log.warning("influxdb-client not installed. InfluxDB disabled.")
            self.enabled = False
        except Exception as e:
            self.log.warning(f"InfluxDB connection failed: {e}")
            self.connected = False

    def _setup_client_with_retry(self):
        """Setup InfluxDB client with retry logic at startup"""
        delay = RETRY_INITIAL_DELAY

        for attempt in range(1, RETRY_MAX_ATTEMPTS + 1):
            self._setup_client()

            if self.connected:
                return  # Successfully connected

            if not self.enabled:
                return  # influxdb-client not installed

            if attempt < RETRY_MAX_ATTEMPTS:
                self.log.info(
                    f"InfluxDB connection attempt {attempt}/{RETRY_MAX_ATTEMPTS} failed, "
                    f"retrying in {delay}s..."
                )
                time.sleep(delay)
                delay = min(delay * RETRY_BACKOFF_FACTOR, RETRY_MAX_DELAY)

        self.log.warning(
            f"InfluxDB: all {RETRY_MAX_ATTEMPTS} connection attempts failed. "
            "Will retry on next write operation."
        )

    def _try_reconnect(self):
        """Attempt to reconnect with exponential backoff"""
        current_time = time.time()

        # Check if enough time has passed since last attempt
        if current_time - self.last_reconnect_attempt < self.reconnect_delay:
            return False

        if self.reconnect_attempts >= self.max_reconnect_attempts:
            # Reset after max attempts reached and long delay
            if current_time - self.last_reconnect_attempt > self.max_reconnect_delay:
                self.reconnect_attempts = 0
                self.reconnect_delay = 5
            else:
                return False

        self.last_reconnect_attempt = current_time
        self.reconnect_attempts += 1

        self.log.info(f"InfluxDB reconnect attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}")

        try:
            if self.write_api:
                try:
                    self.write_api.close()
                except Exception as e:
                    self.log.debug(f"Error closing write_api: {e}")
            if self.client:
                try:
                    self.client.close()
                except Exception as e:
                    self.log.debug(f"Error closing client: {e}")

            self._setup_client()

            if self.connected:
                self.reconnect_count += 1
                self.log.info("InfluxDB reconnected successfully")
                return True
        except Exception as e:
            self.log.error(f"InfluxDB reconnect failed: {e}")

        # Exponential backoff
        self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
        return False

    def is_enabled(self):
        """Check if InfluxDB is enabled and connected"""
        if self.enabled and not self.connected:
            self._try_reconnect()
        return self.enabled and self.connected

    def _should_write(self, key, data):
        """Check if data should be written based on publish_mode"""
        if self.publish_mode == 'all':
            return True

        # Mode 'changed' - check if values differ
        with self.lock:
            if key not in self.last_values:
                self.last_values[key] = data.copy()
                return True

            # Compare values
            changed = False
            for field, value in data.items():
                if field not in self.last_values[key] or self.last_values[key][field] != value:
                    changed = True
                    break

            if changed:
                self.last_values[key] = data.copy()

            return changed

    def write_battery_data(self, battery_id, data):
        """Write battery data to InfluxDB with rate limiting and publish_mode support"""
        if not self.is_enabled():
            return

        current_time = time.time()
        key = f"battery_{battery_id}"

        # Rate limit writes per battery
        if key in self.last_write_time:
            if current_time - self.last_write_time[key] < self.write_interval:
                return

        # Check if we should write based on publish_mode
        write_data = {k: v for k, v in data.items() if isinstance(v, (int, float)) and v is not None}
        if not self._should_write(key, write_data):
            return

        self.last_write_time[key] = current_time
        self.writes_total += 1

        try:
            from influxdb_client import Point

            # Create point for battery measurements
            point = Point("seplos_battery") \
                .tag("battery_id", str(battery_id)) \
                .tag("device", f"battery_{battery_id}")

            # Add all numeric fields
            numeric_fields = [
                'pack_voltage', 'current', 'power', 'remaining_capacity', 'total_capacity',
                'soc', 'soh', 'cycles', 'average_cell_voltage', 'average_cell_temp',
                'max_cell_voltage', 'min_cell_voltage', 'max_cell_temp', 'min_cell_temp',
                'maxdiscurt', 'maxchgcurt', 'cell_delta', 'alarm_count', 'protection_count',
                'balancing_count', 'ambient_temp', 'mosfet_temp'
            ]

            for field in numeric_fields:
                if field in data and data[field] is not None:
                    value = data[field]
                    if isinstance(value, (int, float)):
                        point = point.field(field, float(value))

            # Add cell voltages
            for i in range(1, 17):
                cell_key = f'cell_{i}'
                if cell_key in data and data[cell_key] is not None:
                    point = point.field(cell_key, float(data[cell_key]))

            # Add cell temperatures
            for i in range(1, 5):
                temp_key = f'cell_temp_{i}'
                if temp_key in data and data[temp_key] is not None:
                    point = point.field(temp_key, float(data[temp_key]))

            # Add status as tag
            if 'status' in data:
                point = point.tag("status", data['status'])

            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            self.last_successful_write = current_time

        except Exception as e:
            self.writes_failed += 1
            self.connected = False
            self.log.error(f"InfluxDB write error for battery {battery_id}: {e}")

    def write_pack_data(self, data):
        """Write pack aggregate data to InfluxDB with publish_mode support"""
        if not self.is_enabled():
            return

        current_time = time.time()
        key = "pack"

        # Rate limit writes
        if key in self.last_write_time:
            if current_time - self.last_write_time[key] < self.write_interval:
                return

        # Check if we should write based on publish_mode
        write_data = {k: v for k, v in data.items() if isinstance(v, (int, float)) and v is not None}
        if not self._should_write(key, write_data):
            return

        self.last_write_time[key] = current_time
        self.writes_total += 1

        try:
            from influxdb_client import Point

            point = Point("seplos_pack") \
                .tag("device", "pack_aggregate")

            # Add all pack fields
            pack_fields = [
                'total_voltage', 'total_current', 'total_power',
                'total_capacity', 'remaining_capacity',
                'energy_remaining', 'energy_to_full',
                'average_soc', 'min_soc', 'max_soc', 'soc_spread',
                'min_soh', 'max_cycles',
                'min_cell_voltage', 'max_cell_voltage', 'cell_delta', 'avg_cell_voltage',
                'min_temp', 'max_temp', 'avg_temp',
                'batteries_online', 'total_alarms', 'total_protections', 'balancing_cells',
                'max_discharge_current', 'max_charge_current'
            ]

            for field in pack_fields:
                if field in data and data[field] is not None:
                    value = data[field]
                    if isinstance(value, (int, float)):
                        point = point.field(field, float(value))

            # Add status as tag
            if 'status' in data:
                point = point.tag("status", data['status'])

            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            self.last_successful_write = current_time

        except Exception as e:
            self.writes_failed += 1
            self.connected = False
            self.log.error(f"InfluxDB write error for pack: {e}")

    def get_stats(self):
        """Return stats for health reporting"""
        return {
            'connected': self.connected,
            'writes_total': self.writes_total,
            'writes_failed': self.writes_failed,
            'last_successful_write': self.last_successful_write,
            'reconnect_attempts': self.reconnect_attempts,
            'reconnect_count': self.reconnect_count,
            'publish_mode': self.publish_mode
        }

    def close(self):
        """Close InfluxDB connection"""
        if self.write_api:
            try:
                self.write_api.close()
            except Exception as e:
                self.log.debug(f"Error closing write_api during shutdown: {e}")
        if self.client:
            try:
                self.client.close()
            except Exception as e:
                self.log.debug(f"Error closing client during shutdown: {e}")
        self.connected = False
