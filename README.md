# Pico Display Scripts

MicroPython scripts for Raspberry Pi Pico W with Pimoroni Inky Pack display, showing real-time environmental sensor data from InfluxDB.

## Hardware

- **Raspberry Pi Pico W**
- **Pimoroni Inky Pack** - E-ink display (296x128 pixels)

## Features

- Fetches temperature, humidity, and CO2 data from InfluxDB
- Dynamic partial display updates (only updates changed values to preserve e-ink lifespan)
- Real-time clock synchronization via NTP
- WiFi connectivity with automatic reconnection
- Error handling with on-screen display
- Low memory footprint with garbage collection

## Setup

### 1. Configuration Files

Create two configuration files (not included in this repository):

**`WIFI_CONFIG.py`**
```python
COUNTRY = "DE"  # Your country code
SSID = "your-wifi-ssid"
PSK = "your-wifi-password"
```

**`INFLUX_CONFIG.py`**
```python
INFLUXDB_URL = "https://your-influxdb-server.com"
INFLUXDB_ORG = "your-org"
INFLUXDB_TOKEN = "your-token"
INFLUXDB_BUCKET = "your-temperature-humidity-bucket"
INFLUXDB_BUCKET_CO2 = "your-co2-bucket"
```

### 2. Dependencies

Install Pimoroni's MicroPython firmware with the required libraries:
- `picographics` - Display driver
- `network_manager` - WiFi management
- `urequests` - HTTP requests
- `ujson` - JSON parsing
- `ntptime` - NTP time sync

Download from: https://github.com/pimoroni/pimoroni-pico/releases

### 3. Upload to Pico

Transfer the following files to your Pico W:
- `main.py` - Current implementation
- `WIFI_CONFIG.py` - Your WiFi credentials
- `INFLUX_CONFIG.py` - Your InfluxDB settings

## How It Works

1. **WiFi Connection**: Connects to WiFi on startup
2. **Time Sync**: Sets RTC using NTP
3. **Data Fetching**: Queries InfluxDB every 30 seconds for latest sensor readings
4. **Smart Updates**: Static labels drawn once at startup, only dynamic values refresh when changed:
   - Temperature: ±0.3°C threshold
   - Humidity: ±2.0% threshold
   - CO2: ±50 ppm threshold
5. **Display**: Shows temperature (°C), humidity (%), CO2 (ppm), and current date/time

## Files

- **`main.py`** - Current active implementation with optimized partial updates
- **`backup_inky.py`** - Previous version with full-screen refresh approach

## Display Layout

```
┌─────────────────────────────────┐
│  DD/MM/YYYY : HH:MM:SS          │
├─────────────────────────────────┤
│  Celsius:    XX.X               │
├─────────────────────────────────┤
│  Humidity:   XX.X%              │
├─────────────────────────────────┤
│  CO2:        XXXX               │
└─────────────────────────────────┘
```

## Optimization Notes

The current implementation uses optimized partial updates to minimize e-ink refresh cycles:
- **Static elements drawn once**: Labels ("Celsius:", "Humidity:", "CO2:") and separator lines are drawn only once at startup and after errors
- **Value-only updates**: Only numeric values refresh when they change significantly
- **Configurable delta thresholds**: Temperature ±0.3°C, Humidity ±2.0%, CO2 ±50 ppm
- **30-second refresh interval**: Balances data freshness with display longevity
- **Memory management**: Active garbage collection with `gc.collect()`
- **Fast update speed**: Mode 2 used for partial refreshes
