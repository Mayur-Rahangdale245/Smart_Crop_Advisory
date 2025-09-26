import requests
import pandas as pd

def get_mandi_prices(crop, district):
    try:
        # AGMARKNET API (example: Wheat in Punjab)
        url = f"https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
        params = {
            "api-key": "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b",  # replace with govt API key
            "format": "json",
            "limit": 10,
            "filters[State]": "Punjab",
            "filters[District]": district,
            "filters[Commodity]": crop
        }
        r = requests.get(url, params=params, timeout=20)
        data = r.json().get('records', [])
        if not data: return None
        df = pd.DataFrame(data)[['market','commodity','min_price','max_price','modal_price','arrival_date']]
        return df
    except:
        return None
