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


async def ensure_wifi():
    if not network_manager.isconnected():
        await network_manager.client(WIFI_CONFIG.SSID, WIFI_CONFIG.PSK)


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
            response.close()
            return (temperature_row[-4], humidity_row[-4])
        else:
            print("HTTP Error:", response.status_code)
            print("Response Content:", response.content.decode())
            return None
    except Exception as e:
        print("Error in query_influxdb:", e)
        return None


def query_influxdb_co2(query):
    headers = {"Content-Type": "application/json", "Authorization": f"Token {INFLUXDB_TOKEN}"}
    try:
        response = urequests.post(query_url_co2, headers=headers, data=ujson.dumps({"query": query}))
        if response.status_code == 200:
            data = response.text
            rows = data.split("\n")
            co2 = rows[1].split(",")[-4]
            response.close()
            return co2.split(".")[0]
        else:
            print("HTTP Error:", response.status_code)
            print("Response Content:", response.content.decode())
            return None
    except Exception as e:
        print("Error in query_influxdb_co2:", e)
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
state = {
    "temp": None,
    "humidity": None,
    "co2": None,
}


TEMP_DELTA = 0.3
HUMIDITY_DELTA = 2.0
CO2_DELTA = 50

REGION_DATE = (40, 0, WIDTH, 20)
REGION_TEMP = (190, 23, WIDTH, 27)
REGION_HUM = (190, 60, WIDTH, 27)
REGION_CO2 = (190, 100, WIDTH, 27)


def draw_static_elements():
    """Draw static elements (labels and lines) that never change."""
    graphics.set_update_speed(2)
    graphics.set_thickness(3)
    graphics.set_font("serif")
    graphics.set_pen(0)

    # Draw static labels
    graphics.text("Celsius:", 7, 35, scale=1)
    graphics.text("Humidity:", 7, 74, scale=1)
    graphics.text("CO2:", 7, 115, scale=1)

    # Draw separator lines
    graphics.line(5, 54, 286, 54)
    graphics.line(5, 93, 286, 93)

    graphics.update()


def dynamic_update(temp, humidity, co2):
    temp_changed = state["temp"] is None or abs(state["temp"] - temp) > TEMP_DELTA

    humidity_changed = state["humidity"] is None or abs(state["humidity"] - humidity) > HUMIDITY_DELTA

    co2_changed = state["co2"] is None or abs(state["co2"] - co2) > CO2_DELTA

    return temp_changed, humidity_changed, co2_changed


def update():
    # connect to WIFI if not already connected
    uasyncio.get_event_loop().run_until_complete(ensure_wifi())

    # get readings from influxdb API
    co2_raw = query_influxdb_co2(query_co2)
    temperature, humidity = query_influxdb(query)
    if co2_raw is None or temperature is None:
        print("Failed to retrieve the latest entry.")

    co2 = int(co2_raw)
    rounded_temperature = round(float(temperature), 1)
    rounded_humidity = round(float(humidity), 1)

    temp_changed, hum_changed, co2_changed = dynamic_update(rounded_temperature, rounded_humidity, co2)
    if temp_changed or hum_changed or co2_changed:
        graphics.set_update_speed(2)
        graphics.set_pen(15)

        # Clear only the value regions
        graphics.rectangle(*REGION_TEMP)
        state["temp"] = rounded_temperature

        graphics.rectangle(*REGION_HUM)
        state["humidity"] = rounded_humidity

        graphics.rectangle(*REGION_CO2)
        state["co2"] = co2

        graphics.rectangle(*REGION_DATE)
        graphics.update()

        # Draw only the dynamic values
        graphics.set_thickness(3)
        graphics.set_font("serif")
        graphics.set_pen(0)

        graphics.text(str(rounded_temperature), 205, 35, scale=1)
        graphics.text(str(rounded_humidity) + "%", 203, 74, scale=1)
        graphics.text(str(co2), 204, 115, scale=1)

        # Draw date/time
        graphics.set_thickness(1)
        year, month, day, wd, hour, minute, second, _ = rtc.datetime()
        hms = f"{hour + 1:02}:{minute:02}:{second:02}"
        dmy = f"{day:02}/{month:02}/{year:04}"
        date = f"{dmy} : {hms}"
        graphics.set_font("bitmap8")
        graphics.text(date, 60, 5, wordwrap=WIDTH - 20, scale=2)
        graphics.update()
    gc.collect()


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
    time.sleep(20)
    graphics.set_pen(15)
    graphics.clear()
    raise e

graphics.set_pen(15)
graphics.clear()

# Draw static elements once before starting the update loop
draw_static_elements()

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
        time.sleep(20)
        graphics.set_pen(15)
        graphics.clear()
        # Redraw static elements after clearing the screen due to error
        draw_static_elements()
    time.sleep(30)
