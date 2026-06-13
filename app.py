import os
import gradio as gr
import requests
from datetime import datetime

# ─────────────────────────────────────────────
#  API KEY — loaded from Hugging Face Secret
# ─────────────────────────────────────────────
API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")
BASE_URL = "https://api.openweathermap.org/data/2.5"

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
EMOJI = {
    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️",
    "Drizzle": "🌦️", "Thunderstorm": "⛈️", "Snow": "❄️",
    "Mist": "🌫️", "Smoke": "🌫️", "Haze": "🌫️",
    "Dust": "🌪️", "Fog": "🌫️", "Sand": "🌪️",
    "Ash": "🌋", "Squall": "💨", "Tornado": "🌪️",
}

def wind_direction(degrees):
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[round(degrees / 45) % 8]

def format_time(unix_ts, offset_sec):
    return datetime.utcfromtimestamp(unix_ts + offset_sec).strftime("%H:%M")

def check_api_key():
    if not API_KEY:
        return "❌ API key not configured. Please add `OPENWEATHER_API_KEY` in your Space secrets."
    return None

# ─────────────────────────────────────────────
#  CURRENT WEATHER
# ─────────────────────────────────────────────
def get_current(city: str, units: str):
    err = check_api_key()
    if err:
        return err

    unit_sym  = "°C" if units == "metric" else "°F"
    speed_sym = "m/s" if units == "metric" else "mph"

    try:
        r = requests.get(
            f"{BASE_URL}/weather",
            params={"q": city, "appid": API_KEY, "units": units},
            timeout=8,
        )
        if r.status_code == 404:
            return "❌ City not found. Check the spelling and try again."
        if r.status_code == 401:
            return "❌ Invalid API key. Please check your Hugging Face secret."
        r.raise_for_status()
        d = r.json()
    except requests.exceptions.ConnectionError:
        return "❌ Network error. Check your internet connection."
    except Exception as e:
        return f"❌ Error: {e}"

    tz_offset = d.get("timezone", 0)
    main      = d["main"]
    wind      = d["wind"]
    weather   = d["weather"][0]
    sys_info  = d.get("sys", {})
    condition = weather["main"]
    icon      = EMOJI.get(condition, "🌈")

    lines = [
        f"## {icon} {d['name']}, {sys_info.get('country', '')}",
        f"**{weather['description'].title()}**",
        "",
        f"| 🌡️ Temperature | {main['temp']:.1f}{unit_sym} (feels like {main['feels_like']:.1f}{unit_sym}) |",
        f"|---|---|",
        f"| 🔺 High / 🔻 Low | {main['temp_max']:.1f}{unit_sym} / {main['temp_min']:.1f}{unit_sym} |",
        f"| 💧 Humidity | {main['humidity']}% |",
        f"| 🌬️ Wind | {wind['speed']:.1f} {speed_sym} {wind_direction(wind.get('deg', 0))} |",
        f"| 👁️ Visibility | {d.get('visibility', 0) / 1000:.1f} km |",
        f"| ☁️ Cloud Cover | {d.get('clouds', {}).get('all', 0)}% |",
        f"| 📊 Pressure | {main['pressure']} hPa |",
    ]

    if "rain" in d:
        lines.append(f"| 🌧️ Rain (1h) | {d['rain'].get('1h', 0):.1f} mm |")
    if "snow" in d:
        lines.append(f"| ❄️ Snow (1h) | {d['snow'].get('1h', 0):.1f} mm |")
    if "sunrise" in sys_info:
        lines.append(f"| 🌅 Sunrise | {format_time(sys_info['sunrise'], tz_offset)} |")
        lines.append(f"| 🌇 Sunset  | {format_time(sys_info['sunset'],  tz_offset)} |")

    return "\n".join(lines)

# ─────────────────────────────────────────────
#  5-DAY FORECAST
# ─────────────────────────────────────────────
def get_forecast(city: str, units: str):
    err = check_api_key()
    if err:
        return err

    unit_sym  = "°C" if units == "metric" else "°F"
    speed_sym = "m/s" if units == "metric" else "mph"

    try:
        r = requests.get(
            f"{BASE_URL}/forecast",
            params={"q": city, "appid": API_KEY, "units": units, "cnt": 40},
            timeout=8,
        )
        if r.status_code == 404:
            return "❌ City not found."
        if r.status_code == 401:
            return "❌ Invalid API key."
        r.raise_for_status()
        d = r.json()
    except requests.exceptions.ConnectionError:
        return "❌ Network error."
    except Exception as e:
        return f"❌ Error: {e}"

    days: dict[str, list] = {}
    for item in d["list"]:
        dt      = datetime.utcfromtimestamp(item["dt"])
        day_key = dt.strftime("%A, %b %d")
        days.setdefault(day_key, []).append(item)

    lines = [f"## 📅 5-Day Forecast — {d['city']['name']}, {d['city']['country']}\n"]
    lines.append("| Day | Condition | High | Low | Humidity | Wind |")
    lines.append("|-----|-----------|------|-----|----------|------|")

    for day, items in list(days.items())[:5]:
        temps    = [i["main"]["temp"] for i in items]
        hum      = [i["main"]["humidity"] for i in items]
        winds    = [i["wind"]["speed"] for i in items]
        conds    = [i["weather"][0]["main"] for i in items]
        top_cond = max(set(conds), key=conds.count)
        icon     = EMOJI.get(top_cond, "🌈")
        lines.append(
            f"| **{day}** | {icon} {top_cond} "
            f"| {max(temps):.0f}{unit_sym} "
            f"| {min(temps):.0f}{unit_sym} "
            f"| {sum(hum)//len(hum)}% "
            f"| {sum(winds)/len(winds):.1f} {speed_sym} |"
        )

    return "\n".join(lines)

# ─────────────────────────────────────────────
#  AIR QUALITY
# ─────────────────────────────────────────────
AQI_LABELS = {
    1: "🟢 Good", 2: "🟡 Fair", 3: "🟠 Moderate",
    4: "🔴 Poor", 5: "🟣 Very Poor",
}

def get_air_quality(city: str):
    err = check_api_key()
    if err:
        return err

    try:
        geo = requests.get(
            "https://api.openweathermap.org/geo/1.0/direct",
            params={"q": city, "limit": 1, "appid": API_KEY},
            timeout=8,
        )
        geo.raise_for_status()
        geo_data = geo.json()
        if not geo_data:
            return "❌ City not found for Air Quality lookup."
        lat, lon = geo_data[0]["lat"], geo_data[0]["lon"]
    except Exception as e:
        return f"❌ Geocoding error: {e}"

    try:
        r = requests.get(
            f"{BASE_URL}/air_pollution",
            params={"lat": lat, "lon": lon, "appid": API_KEY},
            timeout=8,
        )
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        return f"❌ Air quality error: {e}"

    aqi  = d["list"][0]["main"]["aqi"]
    comp = d["list"][0]["components"]

    lines = [
        f"## 🌿 Air Quality — {city.title()}",
        f"**Overall AQI: {AQI_LABELS.get(aqi, 'Unknown')}**\n",
        "| Pollutant | Value (μg/m³) |",
        "|-----------|--------------|",
        f"| CO        | {comp.get('co',    0):.2f} |",
        f"| NO₂       | {comp.get('no2',   0):.2f} |",
        f"| O₃        | {comp.get('o3',    0):.2f} |",
        f"| PM2.5     | {comp.get('pm2_5', 0):.2f} |",
        f"| PM10      | {comp.get('pm10',  0):.2f} |",
        f"| SO₂       | {comp.get('so2',   0):.2f} |",
    ]
    return "\n".join(lines)

# ─────────────────────────────────────────────
#  MAIN HANDLER
# ─────────────────────────────────────────────
def weather_app(city: str, tab: str, units: str):
    city = city.strip()
    if not city:
        return "⚠️ Please enter a city name."
    if tab == "Current Weather":
        return get_current(city, units)
    elif tab == "5-Day Forecast":
        return get_forecast(city, units)
    elif tab == "Air Quality":
        return get_air_quality(city)
    return "Unknown tab."

# ─────────────────────────────────────────────
#  GRADIO UI
# ─────────────────────────────────────────────
custom_css = """
body { font-family: 'Segoe UI', sans-serif; }
.gradio-container { max-width: 780px !important; margin: auto; }
#title { text-align: center; margin-bottom: 6px; }
"""

with gr.Blocks(css=custom_css, title="🌤️ Weather App") as demo:
    gr.Markdown("# 🌤️ Weather Dashboard", elem_id="title")
    gr.Markdown("Powered by [OpenWeatherMap](https://openweathermap.org/) · Enter any city worldwide.")

    with gr.Row():
        city_input = gr.Textbox(
            label="🏙️ City Name",
            placeholder="e.g. Rawalpindi, London, New York...",
            scale=3,
        )
        unit_radio = gr.Radio(
            choices=["metric", "imperial"],
            value="metric",
            label="🌡️ Units",
            scale=1,
        )

    tab_radio = gr.Radio(
        choices=["Current Weather", "5-Day Forecast", "Air Quality"],
        value="Current Weather",
        label="📋 Data Type",
    )

    search_btn = gr.Button("🔍 Get Weather", variant="primary")
    output     = gr.Markdown(value="*Enter a city and click **Get Weather**.*")

    search_btn.click(fn=weather_app, inputs=[city_input, tab_radio, unit_radio], outputs=output)
    city_input.submit(fn=weather_app, inputs=[city_input, tab_radio, unit_radio], outputs=output)

    gr.Markdown("---\n💡 **Tip:** Switch between tabs to see forecast or air quality without re-entering the city.")

if __name__ == "__main__":
    demo.launch()
