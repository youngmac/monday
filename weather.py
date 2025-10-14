import requests
from datetime import datetime, timedelta

def get_coordinates(address):
    base_url = "https://api.mapbox.com/geocoding/v5/mapbox.places"
    url = f"{base_url}/{address}.json"
    
    params = {
        "access_token": "pk.eyJ1IjoiZ29uZnJlZWNzcyIsImEiOiJjbWdweG1tMnEyZWtvMm5vazJtZW4yeTVrIn0.L8xXekK6sMvGCDnlfeAK7Q",
        "limit": 1  # Only get the top result
    }

    response = requests.get(url, params=params)
    data = response.json()

    if response.status_code == 200 and data["features"]:
        coords = data["features"][0]["geometry"]["coordinates"]
        return coords[1], coords[0]  # Return (lat, lon)
    else:
        return None, None

def get_forecast(lat, lon):
    if lat is None or lon is None:
        raise ValueError("Invalid latitude or longitude provided.")
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

    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()



def check_extreme_temps(forecast):
    """
    Check if any daily temperature is over 80 or under 30°F.
    """
    days = forecast["daily"]
    for max_temp, min_temp in zip(days["temperature_2m_max"], days["temperature_2m_min"]):
        if max_temp > 80 or min_temp < 30:
            return days  # Return full daily forecast if any extreme found
    return None


def get_alerting_forecast(address):
    lat, lon = get_coordinates(address)
    forecast = get_forecast(lat, lon)
    result = check_extreme_temps(forecast)
    return result


# 🔍 Example usage:
if __name__ == "__main__":
    address = "Dallas, TX"  # Replace with any address
    try:
        forecast = get_alerting_forecast(address)
        if forecast:
            print("⚠️ Extreme temperatures found:")
            for date, tmax, tmin in zip(forecast["time"], forecast["temperature_2m_max"], forecast["temperature_2m_min"]):
                print(f"{date}: High {tmax}°F, Low {tmin}°F")
        else:
            print("✅ No extreme temperatures in the 10-day forecast.")
    except Exception as e:
        print(f"Error: {e}")