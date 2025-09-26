import requests
from datetime import datetime, timedelta

DISTRICT_COORDS = {
    "Amritsar": (31.634, 74.872),
    "Ludhiana": (30.901, 75.857),
    "Patiala": (30.339, 76.386),
    "Bathinda": (30.210, 74.945),
    "Ferozepur": (30.933, 74.622),
    "Hoshiarpur": (31.532, 75.905),
    "Jalandhar": (31.326, 75.576),
}

def fetch_weather(district):
    lat, lon = DISTRICT_COORDS.get(district, (30.901, 75.857))

    # Get today's date and 5 days back
    end_date = datetime.today()
    start_date = end_date - timedelta(days=5)

    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "T2M,RH2M,PRECTOTCORR",
        "community": "ag",
        "latitude": lat,
        "longitude": lon,
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "format": "JSON"
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        data = r.json()["properties"]["parameter"]

        dates = sorted(data["T2M"].keys())
        forecast = []
        for d in dates:
            forecast.append({
                "date": d,
                "temperature": round(data["T2M"][d], 1),
                "humidity": round(data["RH2M"][d], 1),
                "rainfall": round(data.get("PRECTOTCORR", {}).get(d, 0), 1)
            })

        # Latest day = "current weather"
        latest = forecast[-1]

        return latest, forecast
    except Exception as e:
        # fallback dummy data
        today = datetime.today().strftime("%Y-%m-%d")
        return (
            {"date": today, "temperature": 25, "humidity": 70, "rainfall": 100},
            []
        )
