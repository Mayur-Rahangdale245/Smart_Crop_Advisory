# punjab_crop_dashboard.py
import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import hashlib
import sqlite3
import os
from pydub import AudioSegment

# Optional voice libs
try:
    from streamlit_mic_recorder import mic_recorder
except Exception:
    mic_recorder = None
import speech_recognition as sr
from gtts import gTTS

# -------------------------
# SETTINGS
# -------------------------
st.set_page_config(page_title="Punjab Farmer Assistant", layout="wide", initial_sidebar_state="expanded")

DB_FILE = "users.db"
AGMARKNET_API_KEY = "YOUR_API_KEY"  # <-- Replace with your Data.gov.in API key

# -------------------------
# CSS: Dark dashboard style
# -------------------------
st.markdown(
    """
    <style>
    :root { --bg:#0b0f12; --card:#0f1720; --muted:#9aa4b2; --accent:#0ea5a4; --panel:#0b1220; --text:#e6eef6; }
    .stApp { background-color: var(--bg); color: var(--text); }
    .sidebar .sidebar-content { background-color: var(--card); }
    .stButton>button { background-color: var(--accent); color: white; border: none; }
    .card { background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)); padding:16px; border-radius:8px; box-shadow: 0 2px 6px rgba(0,0,0,0.6); color:var(--text); }
    .metric-title { color: var(--muted); font-size:12px; }
    .metric-value { font-size:20px; font-weight:700; }
    .right-chat { background-color: #071018; padding:12px; border-radius:8px; height: 85vh; overflow: auto; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# TRANSLATIONS
# -------------------------
translations = {
    "en": {
        "title": "Punjab Farmer Assistant (Dashboard)",
        "desc": "Live crop advisory • weather • mandi prices • voice chatbot",
        "login": "Login", "signup": "Signup", "username": "Username", "password": "Password",
        "signup_success": "Signup successful! Please login.",
        "signup_fail": "Username already exists!",
        "login_fail": "Login failed! Check credentials.",
        "logout": "Logout", "language": "Language / ਭਾਸ਼ਾ",
        "weather": "Weather", "soil": "Soil Nutrients", "crop_rec": "Crop Recommendation",
        "mandi": "Mandi Prices", "chatbot": "Chatbot", "ask": "Ask me...", "voice": "Or ask with your voice:",
        "recommended": "Recommended Crop", "price": "Price of", "trend": "5-Day Weather Trend"
    },
    "pa": {
        "title": "ਪੰਜਾਬ ਕਿਸਾਨ ਸਹਾਇਕ (ਡੈਸ਼ਬੋਰਡ)",
        "desc": "ਲਾਈਵ ਫਸਲ ਸਲਾਹ • ਮੌਸਮ • ਮੰਡੀ ਭਾਅ • ਆਵਾਜ਼ ਚੈਟਬੋਟ",
        "login": "ਲਾਗਿਨ", "signup": "ਸਾਇਨਅੱਪ", "username": "ਉਪਭੋਗਤਾ ਨਾਮ", "password": "ਪਾਸਵਰਡ",
        "signup_success": "ਸਾਇਨਅੱਪ ਸਫਲ! ਕਿਰਪਾ ਕਰਕੇ ਲਾਗਿਨ ਕਰੋ।",
        "signup_fail": "ਯੂਜ਼ਰਨੇਮ ਪਹਿਲਾਂ ਹੀ ਮੌਜੂਦ ਹੈ!",
        "login_fail": "ਲਾਗਿਨ ਅਸਫਲ! ਵੇਰਵੇ ਚੈੱਕ ਕਰੋ।",
        "logout": "ਲਾੱਗ ਆਊਟ", "language": "Language / ਭਾਸ਼ਾ",
        "weather": "ਮੌਸਮ", "soil": "ਮਿੱਟੀ ਪੋਸ਼ਕ ਤੱਤ", "crop_rec": "ਫਸਲ ਸਿਫ਼ਾਰਸ਼",
        "mandi": "ਮੰਡੀ ਭਾਅ", "chatbot": "ਚੈਟਬੋਟ", "ask": "ਮੈਨੂੰ ਪੁੱਛੋ...", "voice": "ਜਾਂ ਆਪਣੀ ਆਵਾਜ਼ ਨਾਲ ਪੁੱਛੋ:",
        "recommended": "ਸਿਫ਼ਾਰਸ਼ ਕੀਤੀ ਫਸਲ", "price": "ਦਾ ਭਾਅ", "trend": "5-ਦਿਨ ਮੌਸਮ ਰੁਝਾਨ"
    }
}

# -------------------------
# DATABASE
# -------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # base schema
    c.execute("""CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL
                )""")
    # add pref_lang column if missing
    try:
        c.execute("ALTER TABLE users ADD COLUMN pref_lang TEXT DEFAULT 'en'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def signup_user(username, password, pref_lang="en"):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, pref_lang) VALUES (?, ?, ?)",
                  (username, hash_password(password), pref_lang))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def login_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == hash_password(password):
        return True
    return False

def get_user_lang(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("SELECT pref_lang FROM users WHERE username=?", (username,))
        r = c.fetchone()
    except:
        r = None
    conn.close()
    return r[0] if r else "en"

def set_user_lang(username, lang_code):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET pref_lang=? WHERE username=?", (lang_code, username))
    conn.commit()
    conn.close()

init_db()

# -------------------------
# FARM UTILS
# -------------------------
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
    end_date = datetime.today()
    start_date = end_date - timedelta(days=5)
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {"parameters": "T2M,RH2M,PRECTOTCORR", "community": "ag",
              "latitude": lat, "longitude": lon,
              "start": start_date.strftime("%Y%m%d"), "end": end_date.strftime("%Y%m%d"),
              "format": "JSON"}
    try:
        r = requests.get(url, params=params, timeout=15)
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
        return forecast[-1], forecast
    except Exception:
        today = datetime.today().strftime("%Y-%m-%d")
        return ({"date": today, "temperature": 25, "humidity": 70, "rainfall": 100}, [])

def get_mandi_price(crop, state="Punjab"):
    try:
        url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
        params = {"api-key": AGMARKNET_API_KEY, "format": "json", "limit": 5,
                  "filters[state]": state, "filters[commodity]": crop.capitalize()}
        r = requests.get(url, params=params, timeout=12)
        records = r.json().get("records", [])
        if records:
            val = records[0].get("modal_price") or records[0].get("min_price") or records[0].get("max_price")
            return int(val) if val else None
    except Exception:
        pass
    fallback = {"Rice": 1900, "Wheat": 2000, "Maize": 1800, "Cotton": 6200, "Pulses": 6000}
    return fallback.get(crop.capitalize(), 1500)

def crop_recommendation(N, P, K, temp, humidity, ph, rainfall):
    if ph < 6.0:
        return "Rice"
    if N > 100 and 6.0 <= ph <= 7.5:
        return "Wheat"
    if rainfall > 120:
        return "Maize"
    if temp > 30 and K > 50:
        return "Cotton"
    return "Pulses"

# -------------------------
# CHATBOT
# -------------------------
IRR_KEYS = ["irrigate", "water", "watering", "irrigation", "ਸਿੰਚਾਈ", "ਪਾਣੀ"]
PRICE_KEYS = ["price", "rate", "mandi", "ਭਾਅ", "ਦਾਮ"]
WEATHER_KEYS = ["weather", "rain", "forecast", "temperature", "humidity", "ਮੌਸਮ", "ਮੀਹ", "ਤਾਪਮਾਨ", "ਨਮੀ"]
SOIL_KEYS = ["soil", "fertilizer", "nutrient", "ph", "ਮਿੱਟੀ", "ਖਾਦ", "ਪੋਸ਼ਕ"]

def detect_intent(q: str):
    qlow = q.lower()
    if any(k in qlow for k in IRR_KEYS):
        return "irrigation"
    if any(k in qlow for k in PRICE_KEYS):
        return "price"
    if any(k in qlow for k in WEATHER_KEYS):
        return "weather"
    if any(k in qlow for k in SOIL_KEYS):
        return "soil"
    return "unknown"

def irrigation_advice(crop, forecast, lang="en"):
    if not forecast:
        return "No forecast data available." if lang=="en" else "ਕੋਈ ਮੌਸਮ ਡਾਟਾ ਉਪਲਬਧ ਨਹੀਂ ਹੈ।"
    rain_next3 = sum(d["rainfall"] for d in forecast[-3:])
    latest = forecast[-1]
    if rain_next3 > 15:
        return (f"Rain expected (~{rain_next3} mm). Delay irrigation for {crop}."
                if lang=="en" else f"ਅਗਲੇ ਦਿਨਾਂ ਵਿੱਚ ਮੀਂਹ ਉਮੀਦ ਹੈ (~{rain_next3} mm)। {crop} ਦੀ ਸਿੰਚਾਈ ਰੋਕੋ।")
    if latest["temperature"] > 32 and latest["humidity"] < 50:
        return (f"High temp & low humidity. Irrigate {crop} in 1–2 days."
                if lang=="en" else f"ਤਾਪਮਾਨ ਜ਼ਿਆਦਾ ਤੇ ਨਮੀ ਘੱਟ। {crop} ਦੀ 1–2 ਦਿਨਾਂ ਵਿੱਚ ਸਿੰਚਾਈ ਕਰੋ।")
    return ("Soil moisture OK. Irrigate every 7–10 days."
            if lang=="en" else "ਮਿੱਟੀ ਦੀ ਨਮੀ ਠੀਕ ਹੈ। 7–10 ਦਿਨਾਂ 'ਚ ਸਿੰਚਾਈ ਕਰੋ।")

def nutrient_advice(N, P, K, pH, lang="en"):
    if lang=="en":
        return f"N={N}, P={P}, K={K}, pH={pH} → adjust fertilizers as needed."
    return f"N={N}, P={P}, K={K}, pH={pH} → ਲੋੜ ਅਨੁਸਾਰ ਖਾਦ ਵਰਤੋਂ।"

def speak_text(text, lang="en"):
    try:
        tts = gTTS(text=text, lang=lang)
        audio_file = "reply.mp3"
        tts.save(audio_file)
        return audio_file
    except Exception as e:
        st.error(f"TTS failed: {e}")
        return None

# -------------------------
# AUTH
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None

sidebar_lang = st.sidebar.radio("Language / ਭਾਸ਼ਾ", ("English", "ਪੰਜਾਬੀ"))
lang_code = "en" if sidebar_lang=="English" else "pa"
T = translations[lang_code]

if not st.session_state.logged_in:
    st.sidebar.markdown("### " + ("Login / Signup" if lang_code=="en" else "ਲਾਗਿਨ / ਸਾਇਨਅੱਪ"))
    auth_mode = st.sidebar.selectbox("", [T["login"], T["signup"]])
    user_in = st.sidebar.text_input(T["username"])
    pwd_in = st.sidebar.text_input(T["password"], type="password")
    pref_lang_choice = st.sidebar.selectbox("Preferred language", ("English","ਪੰਜਾਬੀ")) if auth_mode==T["signup"] else None

    if st.sidebar.button(auth_mode):
        if auth_mode == T["signup"]:
            success = signup_user(user_in, pwd_in, pref_lang="en" if pref_lang_choice=="English" else "pa")
            if success:
                st.sidebar.success(T["signup_success"])
            else:
                st.sidebar.error(T["signup_fail"])
        else:
            if login_user(user_in, pwd_in):
                st.session_state.logged_in = True
                st.session_state.username = user_in
                u_lang = get_user_lang(user_in)
                sidebar_lang = "English" if u_lang=="en" else "ਪੰਜਾਬੀ"
                st.rerun()
            else:
                st.sidebar.error(T["login_fail"])
    st.stop()

st.sidebar.success(f"{st.session_state.username}")
if st.sidebar.button(T["logout"]):
    st.session_state.logged_in = False
    st.rerun()

user_pref = get_user_lang(st.session_state.username)
if user_pref and user_pref != lang_code:
    lang_code = user_pref
    T = translations[lang_code]

# -------------------------
# MAIN LAYOUT
# -------------------------
st.markdown(f"## {T['title']}")
st.markdown(T["desc"])

with st.sidebar:
    st.markdown("### Farm Details")
    district = st.selectbox("Select District / ਜ਼ਿਲ੍ਹਾ", list(DISTRICT_COORDS.keys()))
    st.markdown("### " + T["soil"])
    N = st.number_input("Nitrogen (N)", value=50, min_value=0, max_value=200)
    P = st.number_input("Phosphorus (P)", value=50, min_value=0, max_value=200)
    K = st.number_input("Potassium (K)", value=50, min_value=0, max_value=300)
    pH = st.number_input("Soil pH", value=6.5, min_value=0.0, max_value=14.0, step=0.1)

weather, forecast = fetch_weather(district)
recommended_crop = crop_recommendation(N, P, K, weather["temperature"], weather["humidity"], pH, weather["rainfall"])
price = get_mandi_price(recommended_crop) or "N/A"

left_col, mid_col, right_col = st.columns([1.4, 0.6, 0.8])

with left_col:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"**{T['weather']}** • {district} ({weather['date']})")
    st.markdown(f"- Temp: **{weather['temperature']}°C**  • Humidity: **{weather['humidity']}%**  • Rain: **{weather['rainfall']} mm**")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"**{T['crop_rec']}**")
    st.markdown(f"### {T['recommended']}: **{recommended_crop}**")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"**{T['mandi']}**")
    st.markdown(f"• {T['price']} {recommended_crop}: **₹{price}** / quintal")
    st.markdown("</div>", unsafe_allow_html=True)

with mid_col:
    if forecast:
        df = pd.DataFrame(forecast)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### " + T["trend"])
        fig, ax1 = plt.subplots(figsize=(5,2.5))
        ax1.plot(df["date"], df["temperature"], marker="o")
        ax1.set_ylabel("Temp (°C)")
        ax2 = ax1.twinx()
        ax2.bar(df["date"], df["rainfall"], alpha=0.25)
        ax2.set_ylabel("Rainfall (mm)")
        plt.xticks(rotation=30)
        st.pyplot(fig)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No forecast available")

with right_col:
    st.markdown('<div class="right-chat">', unsafe_allow_html=True)
    st.markdown(f"### {T['chatbot']}")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    user_query = st.text_input(T["ask"], key="chat_input")

    st.markdown(T["voice"])
    voice_text = ""
    if mic_recorder:
        audio = mic_recorder(start_prompt="Record", stop_prompt="Stop", key="recorder")
        if audio and "bytes" in audio:
            with open("voice_input.webm", "wb") as f:
                f.write(audio["bytes"])
            try:
                sound = AudioSegment.from_file("voice_input.webm", format="webm")
                sound.export("voice_input.wav", format="wav")
                recognizer = sr.Recognizer()
                with sr.AudioFile("voice_input.wav") as source:
                    audio_data = recognizer.record(source)
                    voice_text = recognizer.recognize_google(audio_data, language="en-IN" if lang_code=="en" else "pa-IN")
                    st.write(f"🗣️ {voice_text}")
            except Exception as e:
                st.warning("Voice processing failed: " + str(e))
    else:
        uploaded = st.file_uploader("Upload voice file (webm/wav/mp3)", type=["webm","wav","mp3"])
        if uploaded:
            with open("uploaded_audio", "wb") as f:
                f.write(uploaded.getbuffer())
            try:
                sound = AudioSegment.from_file("uploaded_audio")
                sound.export("voice_input.wav", format="wav")
                recognizer = sr.Recognizer()
                with sr.AudioFile("voice_input.wav") as source:
                    audio_data = recognizer.record(source)
                    voice_text = recognizer.recognize_google(audio_data, language="en-IN" if lang_code=="en" else "pa-IN")
                    st.write(f"🗣️ {voice_text}")
            except Exception as e:
                st.warning("Uploaded audio processing failed: " + str(e))

    final_query = user_query if user_query else voice_text

    if final_query:
        st.session_state.chat_history.append({"role":"user","content":final_query})
        intent = detect_intent(final_query)
        if intent == "irrigation":
            bot_reply = irrigation_advice(recommended_crop, forecast, lang=lang_code)
        elif intent == "price":
            bot_reply = (f"{T['price']} {recommended_crop}: ₹{price}/quintal" if lang_code=="en"
                         else f"{recommended_crop} {T['price']}: ₹{price}/ਕੁਇੰਟਲ")
        elif intent == "weather":
            bot_reply = (f"{weather['temperature']}°C, {weather['humidity']}% humidity, {weather['rainfall']}mm rain"
                         if lang_code=="en" else f"{weather['temperature']}°C, {weather['humidity']}% ਨਮੀ, {weather['rainfall']} ਮਿਮੀ ਮੀਂਹ")
        elif intent == "soil":
            bot_reply = nutrient_advice(N,P,K,pH, lang=lang_code)
        else:
            bot_reply = ("I'm still learning. Ask about irrigation, soil, weather, or mandi price."
                         if lang_code=="en" else "ਮੈਂ ਹਾਲੇ ਸਿੱਖ ਰਿਹਾ ਹਾਂ। ਸਿੰਚਾਈ, ਮਿੱਟੀ, ਮੌਸਮ ਜਾਂ ਮੰਡੀ ਭਾਅ ਬਾਰੇ ਪੁੱਛੋ।")

        st.session_state.chat_history.append({"role":"assistant","content":bot_reply})
        audio_f = speak_text(bot_reply, lang=lang_code)
        if audio_f:
            st.audio(audio_f, format="audio/mp3")

    for msg in st.session_state.chat_history[::-1]:
        if msg["role"] == "assistant":
            st.markdown(f"**Bot:** {msg['content']}")
        else:
            st.markdown(f"**You:** {msg['content']}")
    st.markdown('</div>', unsafe_allow_html=True)
