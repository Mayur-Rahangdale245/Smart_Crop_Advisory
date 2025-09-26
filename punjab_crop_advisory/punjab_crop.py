# -------------------------
# MAIN LAYOUT (Updated)
# -------------------------
st.markdown(f"## {T['title']}")
st.markdown(T["desc"])

# Create 3-column layout: left sidebar is already Streamlit sidebar
mid_col, right_col = st.columns([2, 1])

# --- MIDDLE PANEL: CARDS + DASHBOARD ---
with mid_col:
    st.markdown("### 🌿 Dashboard")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**{T['weather']}** • {district} ({weather['date']})")
        st.markdown(f"- 🌡️ Temp: **{weather['temperature']}°C**  \n"
                    f"- 💧 Humidity: **{weather['humidity']}%**  \n"
                    f"- ☔ Rain: **{weather['rainfall']} mm**")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**{T['mandi']}**")
        st.markdown(f"• {T['price']} {recommended_crop}: **₹{price}** / quintal")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**{T['crop_rec']}**")
        st.markdown(f"### 🌾 {T['recommended']}: **{recommended_crop}**")
        st.markdown("</div>", unsafe_allow_html=True)

    # Forecast chart below cards
    if forecast:
        df = pd.DataFrame(forecast)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 📊 " + T["trend"])
        fig, ax1 = plt.subplots(figsize=(6,3))
        ax1.plot(df["date"], df["temperature"], marker="o")
        ax1.set_ylabel("Temp (°C)")
        ax2 = ax1.twinx()
        ax2.bar(df["date"], df["rainfall"], alpha=0.25)
        ax2.set_ylabel("Rainfall (mm)")
        plt.xticks(rotation=30)
        st.pyplot(fig)
        st.markdown("</div>", unsafe_allow_html=True)

# --- RIGHT PANEL: CHATBOT (TOP) ---
with right_col:
    st.markdown("### 🤖 " + T["chatbot"])
    st.markdown('<div class="right-chat">', unsafe_allow_html=True)

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # User query text input
    user_query = st.text_input(T["ask"], key="chat_input")

    # Realtime mic input (no uploader)
    st.markdown(T["voice"])
    voice_text = ""
    if mic_recorder:
        audio = mic_recorder(start_prompt="🎙️ Start", stop_prompt="⏹️ Stop", key="recorder")
        if audio and "bytes" in audio:
            with open("voice_input.webm", "wb") as f:
                f.write(audio["bytes"])
            try:
                sound = AudioSegment.from_file("voice_input.webm", format="webm")
                sound.export("voice_input.wav", format="wav")
                recognizer = sr.Recognizer()
                with sr.AudioFile("voice_input.wav") as source:
                    audio_data = recognizer.record(source)
                    voice_text = recognizer.recognize_google(
                        audio_data, language="en-IN" if lang_code=="en" else "pa-IN"
                    )
                    st.write(f"🗣️ {voice_text}")
            except Exception as e:
                st.warning("Voice processing failed: " + str(e))

    final_query = user_query if user_query else voice_text

    # Bot logic
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

    # Chat history display with bubble styling
    for msg in st.session_state.chat_history[::-1]:
        if msg["role"] == "assistant":
            st.markdown(f"""
            <div style="background:#0ea5a4; padding:10px; border-radius:10px; margin:5px 0; color:white;">
            🤖 {msg['content']}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:#1f2937; padding:10px; border-radius:10px; margin:5px 0; text-align:right;">
            👩‍🌾 {msg['content']}
            </div>
            """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
