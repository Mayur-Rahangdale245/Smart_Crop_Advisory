# punjab_crop_dashboard.py
import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import hashlib
import sqlite3
from pydub import AudioSegment
import speech_recognition as sr
from gtts import gTTS

# Optional voice recorder
try:
    from streamlit_mic_recorder import mic_recorder
except Exception:
    mic_recorder = None

# -------------------------
# SETTINGS
# -------------------------
st.set_page_config(page_title="Punjab Farmer Assistant", layout="wide", initial_sidebar_state="expanded")

DB_FILE = "users.db"
AGMARKNET_API_KEY = "YOUR_API_KEY"  # replace with real key

# -------------------------
# CSS
# -------------------------
st.markdown(
    """
    <style>
    :root { --bg:#0b0f12; --card:#0f1720; --muted:#9aa4b2; --accent:#0ea5a4; --text:#e6eef6; }
    .stApp { background-color: var(--bg); color: var(--text); }
    .sidebar .sidebar-content { background-color: var(--card); }
    .stButton>button { background-color: var(--accent); color: white; border: none; }
    .card { background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
            padding:16px; border-radius:8px; box-shadow: 0 2px 6px rgba(0,0,0,0.6); color:var(--text); }
    .right-chat { background-color: #071018; padding:12px; border-radius:8px; height: 75vh; overflow-y: auto; }
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
# DB
# -------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL,
                    pref_lang TEXT DEFAULT 'en'
                )""")
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
    return row and row[0] == hash_password(password)

def get_user_lang(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT pref_lang FROM users WHERE username=?", (username,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else "en"

init_db()

# -------------------------
# FARM UTILS (weather, crop etc.)
# -------------------------
DISTRICT_COORDS = {"Amritsar": (31.634, 74.872), "Ludhiana": (30.901, 75.857)}

def fetch_weather(district):
    lat, lon = DISTRICT_COORDS.get(district, (30.901, 75.857))
    today = datetime.today()
    try:
        url = "https://power.larc.nasa.gov/api/temporal/daily/point"
        params = {"parameters": "T2M,RH2M,PRECTOTCORR", "community": "ag",
                  "latitude": lat, "longitude": lon,
                  "start": (today - timedelta(days=5)).strftime("%Y%m%d"),
                  "end": today.strftime("%Y%m%d"), "format": "JSON"}
        r = requests.get(url, params=params, timeout=15)
        data = r.json()["properties"]["parameter"]
        dates = sorted(data["T2M"].keys())
        forecast = [{"date": d,
                     "temperature": round(data["T2M"][d], 1),
                     "humidity": round(data["RH2M"][d], 1),
                     "rainfall": round(data.get("PRECTOTCORR", {}).get(d, 0), 1)} for d in dates]
        return forecast[-1], forecast
    except Exception:
        return ({"date": today.strftime("%Y-%m-%d"), "temperature": 25, "humidity": 70, "rainfall": 5}, [])

def get_mandi_price(crop):
    return {"Rice": 1900, "Wheat": 2000}.get(crop, 1500)

def crop_recommendation(N, P, K, temp, humidity, ph, rainfall):
    return "Rice" if ph < 6 else "Wheat"

# -------------------------
# CHATBOT helpers
# -------------------------
def detect_intent(q: str):
    qlow = q.lower()
    if "price" in qlow or "ਭਾਅ" in qlow: return "price"
    if "weather" in qlow or "ਮੌਸਮ" in qlow: return "weather"
    if "soil" in qlow or "ਮਿੱਟੀ" in qlow: return "soil"
    return "unknown"

def irrigation_advice(crop, forecast, lang="en"):
    return "Irrigate in 1–2 days." if lang == "en" else "1–2 ਦਿਨਾਂ ਵਿੱਚ ਸਿੰਚਾਈ ਕਰੋ।"

def nutrient_advice(N, P, K, pH, lang="en"):
    return f"N={N}, P={P}, K={K}, pH={pH}"

def speak_text(text, lang="en"):
    try:
        tts = gTTS(text=text, lang=lang)
        fn = "reply.mp3"
        tts.save(fn)
        return fn
    except Exception:
        return None

# -------------------------
# AUTH + LANGUAGE
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None

sidebar_lang = st.sidebar.radio("Language / ਭਾਸ਼ਾ", ("English", "ਪੰਜਾਬੀ"))
lang_code = "en" if sidebar_lang == "English" else "pa"
T = translations[lang_code]

if not st.session_state.logged_in:
    auth_mode = st.sidebar.selectbox("", [T["login"], T["signup"]])
    user_in = st.sidebar.text_input(T["username"])
    pwd_in = st.sidebar.text_input(T["password"], type="password")

    if st.sidebar.button(auth_mode):
        if auth_mode == T["signup"]:
            if signup_user(user_in, pwd_in, pref_lang=lang_code):
                st.sidebar.success(T["signup_success"])
            else:
                st.sidebar.error(T["signup_fail"])
        else:
            if login_user(user_in, pwd_in):
                st.session_state.logged_in = True
                st.session_state.username = user_in
                lang_code = get_user_lang(user_in)
                T = translations[lang_code]
                st.rerun()
            else:
                st.sidebar.error(T["login_fail"])
    st.stop()

st.sidebar.success(st.session_state.username)
if st.sidebar.button(T["logout"]):
    st.session_state.logged_in = False
    st.rerun()

# Inputs
district = st.sidebar.selectbox("District / ਜ਼ਿਲ੍ਹਾ", list(DISTRICT_COORDS.keys()))
N = st.sidebar.number_input("Nitrogen (N)", value=50)
P = st.sidebar.number_input("Phosphorus (P)", value=50)
K = st.sidebar.number_input("Potassium (K)", value=50)
pH = st.sidebar.number_input("Soil pH", value=6.5, step=0.1)

# -------------------------
# FETCH DATA
# -------------------------
weather, forecast = fetch_weather(district)
recommended_crop = crop_recommendation(N, P, K, weather["temperature"], weather["humidity"], pH, weather["rainfall"])
price = get_mandi_price(recommended_crop)

# -------------------------
# MAIN LAYOUT
# -------------------------
st.markdown(f"## {T['title']}")
st.markdown(T["desc"])

mid_col, right_col = st.columns([2, 1], gap="large")

# MIDDLE: dashboard cards
with mid_col:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**{T['weather']}** • {district} ({weather['date']})")
        st.markdown(f"- 🌡️ {weather['temperature']}°C\n- 💧 {weather['humidity']}%\n- ☔ {weather['rainfall']} mm")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**{T['mandi']}**")
        st.markdown(f"{T['price']} {recommended_crop}: ₹{price}/quintal")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**{T['crop_rec']}**")
        st.markdown(f"🌾 {T['recommended']}: **{recommended_crop}**")
        st.markdown('</div>', unsafe_allow_html=True)

    if forecast:
        df = pd.DataFrame(forecast)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### " + T["trend"])
        fig, ax1 = plt.subplots(figsize=(6,3))
        ax1.plot(df["date"], df["temperature"], marker="o")
        ax2 = ax1.twinx()
        ax2.bar(df["date"], df["rainfall"], alpha=0.3)
        plt.xticks(rotation=30)
        st.pyplot(fig)
        st.markdown('</div>', unsafe_allow_html=True)

# RIGHT: chatbot
with right_col:
    st.markdown('<div style="position:sticky; top:8px;">', unsafe_allow_html=True)
    st.markdown("### 🤖 " + T["chatbot"])
    st.markdown('<div class="right-chat">', unsafe_allow_html=True)

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_query = st.text_input(T["ask"], key="chat_input")

    # mic only
    st.markdown(T["voice"])
    voice_text = ""
    if mic_recorder:
        audio = mic_recorder(start_prompt="🎙️ Start", stop_prompt="⏹️ Stop", key="rec")
        if audio and "bytes" in audio:
            with open("voice_input.webm", "wb") as f:
                f.write(audio["bytes"])
            try:
                sound = AudioSegment.from_file("voice_input.webm", format="webm")
                sound.export("voice_input.wav", format="wav")
                recog = sr.Recognizer()
                with sr.AudioFile("voice_input.wav") as src:
                    voice_text = recog.recognize_google(recog.record(src), language="en-IN" if lang_code=="en" else "pa-IN")
                st.write("🗣️ " + voice_text)
            except Exception as e:
                st.warning("Voice failed: " + str(e))

    final_query = user_query if user_query else voice_text

    if final_query:
        st.session_state.chat_history.append({"role":"user","content":final_query})
        intent = detect_intent(final_query)
        if intent == "price":
            reply = f"{T['price']} {recommended_crop}: ₹{price}/quintal"
        elif intent == "weather":
            reply = f"{weather['temperature']}°C, {weather['humidity']}% humidity"
        elif intent == "soil":
            reply = nutrient_advice(N,P,K,pH,lang=lang_code)
        else:
            reply = "Ask about price, weather or soil."
        st.session_state.chat_history.append({"role":"assistant","content":reply})
        audio_f = speak_text(reply, lang=lang_code)
        if audio_f:
            st.audio(audio_f, format="audio/mp3")

    # bubbles
    for msg in st.session_state.chat_history[::-1]:
        if msg["role"]=="assistant":
            st.markdown(f'<div style="background:#0ea5a4;padding:10px;border-radius:10px;margin:6px 0;color:white;">🤖 {msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#1f2937;padding:10px;border-radius:10px;margin:6px 0;text-align:right;">👩‍🌾 {msg["content"]}</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
