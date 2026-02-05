import gc
import time

import INFLUX_CONFIG
import machine
import ntptime
import uasyncio
import ujson
import urequests
import WIFI_CONFIG
from network_manager import NetworkManager
from picographics import DISPLAY_INKY_PACK, PicoGraphics
from pimoroni import Button


def status_handler(mode, status, ip):
    status_text = "Connecting..."
    if status is not None:
        if status:
            status_text = "Connection successful!"
        else:
            status_text = "Connection failed!"


network_manager = NetworkManager(WIFI_CONFIG.COUNTRY, status_handler=status_handler)
# uasyncio.get_event_loop().run_until_complete(network_manager.client(WIFI_CONFIG.SSID, WIFI_CONFIG.PSK))

# InfluxDB server details
INFLUXDB_URL = INFLUX_CONFIG.INFLUXDB_URL
INFLUXDB_BUCKET = INFLUX_CONFIG.INFLUXDB_BUCKET
INFLUXDB_ORG = INFLUX_CONFIG.INFLUXDB_ORG
INFLUXDB_TOKEN = INFLUX_CONFIG.INFLUXDB_TOKEN
INFLUXDB_BUCKET_CO2 = INFLUX_CONFIG.INFLUXDB_BUCKET_CO2

# InfluxDB query to retrieve the latest entry
query = f'from(bucket: "{INFLUXDB_BUCKET}") |> range(start: -15m) |> last()'
query_co2 = f'from(bucket: "{INFLUXDB_BUCKET_CO2}") |> range(start: -15m) |> last()'
# URL for the InfluxDB query API
query_url = f"{INFLUXDB_URL}/api/v2/query?org={INFLUXDB_ORG}&bucket={INFLUXDB_BUCKET}&precision=s"
query_url_co2 = f"{INFLUXDB_URL}/api/v2/query?org={INFLUXDB_ORG}&bucket={INFLUXDB_BUCKET_CO2}&precision=s"

rtc = machine.RTC()


# Function to make InfluxDB query
def query_influxdb(query):
    headers = {"Content-Type": "application/json", "Authorization": f"Token {INFLUXDB_TOKEN}"}
    try:
        response = urequests.post(query_url, headers=headers, data=ujson.dumps({"query": query}))
        if response.status_code == 200:
            data = response.text
            rows = data.split("\n")
            humidity_row = rows[1].split(",")
            temperature_row = rows[2].split(",")
            return (temperature_row[-4], humidity_row[-4])
        else:
            print("HTTP Error:", response.status_code)
            print("Response Content:", response.content.decode())
            return None
    except Exception as e:
        print("Error:", e)
        return None


def query_influxdb_co2(query):
    headers = {"Content-Type": "application/json", "Authorization": f"Token {INFLUXDB_TOKEN}"}
    try:
        response = urequests.post(query_url, headers=headers, data=ujson.dumps({"query": query}))
        if response.status_code == 200:
            data = response.text
            rows = data.split("\n")
            co2 = rows[1].split(",")[-4]
            return co2.split(".")[0]
        else:
            print("HTTP Error:", response.status_code)
            print("Response Content:", response.content.decode())
            return None
    except Exception as e:
        print("Error:", e)
        return None


# Lets print this shit

button_a = Button(12)
button_b = Button(13)
button_c = Button(14)

graphics = PicoGraphics(DISPLAY_INKY_PACK)
graphics.set_font("serif")
graphics.set_thickness(3)

WIDTH, HEIGHT = graphics.get_bounds()

# dynamic refresh rate logic
last_temp = 0
last_humidity = 0
last_co2 = 0
recently_updated = False


def dynamic_update(t, h, c):
    global last_temp, last_humidity, last_co2
    # print(last_temp,last_humidity,last_co2,t,h,c)
    if abs(last_temp - t) > 0.2:
        return True
    if abs(last_humidity - h) > 1.0:
        return True
    if abs(last_co2 - c) > 20:
        return True
    return False


def update():
    global recently_updated
    uasyncio.get_event_loop().run_until_complete(network_manager.client(WIFI_CONFIG.SSID, WIFI_CONFIG.PSK))
    co2 = query_influxdb_co2(query_co2)
    temperature, humidity = query_influxdb(query)
    if temperature is not None:
        rounded_temperature = round(float(temperature), 1)
        rounded_humidity = round(float(humidity), 1)
    else:
        print("Failed to retrieve the latest entry.")
    if not recently_updated or dynamic_update(rounded_temperature, rounded_humidity, int(co2)):
        recently_updated = True
        global last_temp, last_humidity, last_co2
        last_temp = rounded_temperature
        last_humidity = rounded_humidity
        last_co2 = int(co2)
        co2_string = "CO2:        " + str(int(co2))
        temp_string = "Celsius:     " + str(rounded_temperature)
        humidity_string = "Humidity:  " + str(rounded_humidity) + "%"
        # print(WIDTH,HEIGHT)
        graphics.set_update_speed(1)
        graphics.set_pen(15)
        graphics.clear()
        graphics.set_thickness(3)
        graphics.set_font("serif")
        graphics.set_pen(0)
        graphics.line(5, 54, 286, 54)
        graphics.line(5, 93, 286, 93)
        graphics.text(temp_string, 7, 35, wordwrap=WIDTH - 20, scale=1)
        graphics.text(humidity_string, 7, 74, scale=1)
        # graphics.set_thickness(1)
        graphics.text(co2_string, 7, 115, scale=1)
        graphics.set_thickness(1)
        year, month, day, wd, hour, minute, second, _ = rtc.datetime()
        hms = f"{hour + 1:02}:{minute:02}:{second:02}"
        dmy = f"{day:02}/{month:02}/{year:04}"
        date = f"{dmy} : {hms}"
        graphics.set_font("bitmap8")
        graphics.text(date, 60, 5, wordwrap=WIDTH - 20, scale=2)
        graphics.update()
    else:
        recently_updated = False
    gc.collect()


# Run continuously.
# Be friendly to the API you're using!
try:
    uasyncio.get_event_loop().run_until_complete(network_manager.client(WIFI_CONFIG.SSID, WIFI_CONFIG.PSK))
    ntptime.settime()
except Exception as e:
    error_message = f"Error: {e}"
    graphics.set_font("bitmap8")
    graphics.set_update_speed(1)
    graphics.set_pen(15)
    graphics.clear()
    graphics.set_pen(0)
    graphics.text(error_message, 7, 25, wordwrap=WIDTH - 20, scale=1)
    graphics.update()
    raise e

while True:
    try:
        update()
    except Exception as e:
        # Handle the exception by printing the error to the display
        error_message = f"Error Type: {type(e).__name__}\nMessage: {str(e)}"
        graphics.set_font("bitmap8")
        graphics.set_update_speed(1)
        graphics.set_pen(15)
        graphics.clear()
        graphics.set_pen(0)
        graphics.text(error_message, 7, 25, wordwrap=WIDTH - 20, scale=1)
        graphics.update()
    time.sleep(30)
