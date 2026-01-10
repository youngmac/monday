import requests
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from config import MAX_ACCEPTABLE_TEMP, MIN_ACCEPTABLE_TEMP
import re
import time

MAPBOX_API_KEY = "pk.eyJ1IjoiZ29uZnJlZWNzcyIsImEiOiJjbWdweG1tMnEyZWtvMm5vazJtZW4yeTVrIn0.L8xXekK6sMvGCDnlfeAK7Q"
BASE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places"

def extract_zip(address):
    match = re.search(r"\b\d{5}(?:-\d{4})?\b", address)
    if match:
        return match.group()
    else:
        return None

def get_coordinates(address):
    url = f"{BASE_URL}/{address}.json"
    
    params = {
        "access_token": MAPBOX_API_KEY,
        "limit": 1  # Only get the top result
    }

    for i in range(0, 10):
        try:
            response = requests.get(url, params=params)
            break  # success → exit loop
        except:
            print("Failed to extract weather. Wait 10 seconds")
            time.sleep(10)
    data = response.json()

    # try generating coords with adddress
    if response.status_code == 200 and data["features"]:
        coords = data["features"][0]["geometry"]["coordinates"]
        return coords[1], coords[0]  # Return (lat, lon)
    else: # fallback to zip
        try:
            zip = extract_zip(address)
            geolocator = Nominatim(user_agent="weather_app")
            location = geolocator.geocode(zip)
            if location:
                return location.latitude, location.longitude
            raise Exception("Error fetching coordinates")
        except:
            return 0,0

def get_forecast(lat, lon):
    """
    Fetch 10-day forecast from Open-Meteo API using latitude and longitude.
    """
    today = datetime.today().date()
    end_date = today + timedelta(days=9)  # 10 days including today

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit",
        "timezone": "auto",
        "start_date": str(today),
        "end_date": str(end_date)
    }

    for i in range(0, 10):
        try:
            response = requests.get(url, params=params)
            break  # success → exit loop
        except:
            print("Failed to extract weather. Wait 10 seconds")
            time.sleep(10)
    response.raise_for_status()
    return response.json()



def check_extreme_temps(forecast):
    """
    Check if any daily temperature is over 88 or under 40°F.
    """
    if not forecast or "daily" not in forecast:
        raise Exception("Error fetching forecast data")
    days = forecast["daily"]
    for max_temp, min_temp in zip(days["temperature_2m_max"], days["temperature_2m_min"]):
        if max_temp > MAX_ACCEPTABLE_TEMP or min_temp < MIN_ACCEPTABLE_TEMP:
            return days  # Return full daily forecast if any extreme found
    return None


def get_alerting_forecast(address):
    # return {} # Toggle to not use api calls
    lat, lon = get_coordinates(address)
    if lat == 0 and lon == 0:
        return {}
    forecast = get_forecast(lat, lon)
    result = check_extreme_temps(forecast)
    return result