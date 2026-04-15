"""Advanced CropSense app with professional UI + full persistence."""

from __future__ import annotations

import time
import hashlib
import streamlit as st
from PIL import Image

from models.disease_model import predict_disease
from utils.severity import classify_severity
from utils.weather import get_weather_advisory
from utils.fertilizer import get_recommendation
from utils.chatbot import get_response
from utils.auth_db import (
    authenticate_user,
    create_user,
    get_recent_analysis,
    get_user_settings,
    init_db,
    save_analysis_log,
    save_chat_log,
    save_user_settings,
    save_weather_log,
)

st.set_page_config(page_title="Smart Rice Crop Monitoring System", page_icon="🌾", layout="wide")
init_db()


def bootstrap() -> None:
    defaults = {
        "auth_user": None,
        "guest_mode": False,
        "active_page": "🏠 Home",
        "chat_history": [
            {"role": "bot", "text": "Welcome. Ask about diseases, fertilizer, weather, or treatment."}
        ],
        "weather_data": None,
        "analysis_done": False,
        "loading_analysis": False,
        "disease_result": None,
        "severity_result": None,
        "fert_result": None,
        "uploaded_image": None,
        "uploaded_image_name": "",
        "uploaded_image_hash": "",
        "default_location": "Delhi,IN",
        "saved_api_key": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


bootstrap()

st.markdown(
    """
    <style>
    .stApp {
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      color: #0f172a;
      background:
        radial-gradient(circle at 0% 0%, #e7f7ed 0%, transparent 32%),
        radial-gradient(circle at 100% 100%, #def5e8 0%, transparent 26%),
        #f4fbf6;
    }

    [data-testid="stSidebar"] {
      background: linear-gradient(180deg, #eaf8ef, #f4fcf7) !important;
      border-right: 1px solid #d6e9dc;
    }

    h1,h2,h3,h4,h5,p,label,small,span,div {
      color: #0f172a !important;
    }

    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] span {
      color: #0f172a !important;
    }

    .stTextInput label,
    .stTextArea label,
    .stSelectbox label,
    .stFileUploader label,
    .stRadio label,
    .stMultiSelect label,
    .stNumberInput label {
      color: #0f172a !important;
      font-weight: 600 !important;
    }

    .stTextInput input,
    .stTextArea textarea {
      background: #ffffff !important;
      color: #0f172a !important;
      border: 1.4px solid #b9d8c4 !important;
      border-radius: 10px !important;
      font-weight: 500 !important;
    }

    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {
      color: #64748b !important;
      opacity: 1 !important;
    }

    .stButton button {
      background: linear-gradient(120deg, #0b6a48, #13835a) !important;
      color: #ffffff !important;
      border: 0 !important;
      border-radius: 10px !important;
      font-weight: 700 !important;
      box-shadow: 0 4px 16px rgba(16, 130, 86, 0.25);
    }

    .stButton button:hover {
      filter: brightness(1.05);
      transform: translateY(-1px);
    }

    .hero {
      background: linear-gradient(120deg, #0b5f42, #127e56, #25a36a);
      color: #ffffff !important;
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 10px 28px rgba(11, 95, 66, 0.25);
      margin-bottom: 14px;
    }

    .hero * { color: #ffffff !important; }

    .card {
      background: #ffffff;
      border: 1px solid #d1e5d8;
      border-left: 5px solid #198754;
      border-radius: 14px;
      padding: 14px;
      box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06);
      margin-bottom: 12px;
    }

    .feature-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }

    .feature {
      background: #ffffff;
      border: 1px solid #d1e5d8;
      border-radius: 12px;
      padding: 12px;
      box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
    }

    .upload-box {
      border: 2.5px dashed #1f9d64;
      border-radius: 16px;
      background: #f8fffb;
      padding: 12px;
    }

    .result-name {
      font-size: 1.9rem;
      font-weight: 800;
      color: #0c5b40 !important;
    }

    .conf-track {
      height: 12px;
      border-radius: 999px;
      background: #d4e6da;
      overflow: hidden;
      margin-bottom: 6px;
    }

    .conf-fill {
      height: 12px;
      border-radius: 999px;
      background: linear-gradient(90deg, #0f7b53, #2cc17e);
    }

    .sev-pill {
      display: inline-block;
      border-radius: 999px;
      padding: 4px 10px;
      color: #fff !important;
      font-weight: 700;
      font-size: 0.9rem;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .summary-box {
      border: 1px solid #d1e5d8;
      background: #ffffff;
      border-radius: 12px;
      padding: 10px;
    }

    .chat-user {
      background: #ddfbe8;
      border: 1px solid #b7e8c9;
      color: #14532d !important;
      border-radius: 14px 14px 4px 14px;
      padding: 9px;
      margin: 6px 0 6px auto;
      width: fit-content;
      max-width: 80%;
    }

    .chat-bot {
      background: #ffffff;
      border: 1px solid #d6e5dc;
      border-radius: 14px 14px 14px 4px;
      padding: 9px;
      margin: 6px auto 6px 0;
      width: fit-content;
      max-width: 85%;
    }

    .login-wrap {
      max-width: 920px;
      margin: 10px auto;
      border: 1px solid #cde7d7;
      border-radius: 18px;
      overflow: hidden;
      box-shadow: 0 12px 36px rgba(8, 31, 20, 0.14);
    }

    .login-top {
      background: linear-gradient(130deg, #0c5f43, #1d8a5f, #29ab70);
      padding: 16px;
      color: #fff !important;
    }

    .login-top * { color: #fff !important; }

    @media (max-width: 900px) {
      .feature-grid { grid-template-columns: 1fr; }
      .summary-grid { grid-template-columns: 1fr; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def is_logged_in() -> bool:
    return bool(st.session_state.auth_user or st.session_state.guest_mode)


def severity_style(level: str) -> tuple[str, str]:
    if level == "Mild":
        return "🟡 Mild", "#eab308"
    if level == "Moderate":
        return "🟠 Moderate", "#f97316"
    if level == "Severe":
        return "🔴 Severe", "#dc2626"
    return "✅ N/A", "#16a34a"


def confidence_html(confidence: float) -> str:
    pct = int(confidence * 100)
    return (
        f'<div class="conf-track"><div class="conf-fill" style="width:{pct}%"></div></div>'
        f'<small style="color:#334155">{pct}% confidence</small>'
    )


def reset_analysis() -> None:
    st.session_state.analysis_done = False
    st.session_state.loading_analysis = False
    st.session_state.disease_result = None
    st.session_state.severity_result = None
    st.session_state.fert_result = None
    st.session_state.uploaded_image = None
    st.session_state.uploaded_image_name = ""


def apply_user_settings() -> None:
    user = st.session_state.auth_user
    if not user or user.get("email") == "guest@local":
        return
    settings = get_user_settings(int(user["id"]))
    st.session_state.default_location = settings["default_location"]
    st.session_state.saved_api_key = settings["weather_api_key"]


def auth_page() -> None:
    st.markdown(
        """
        <div class="login-wrap">
          <div class="login-top">
            <h2 style="margin:0">🌾 Smart Rice Crop Monitoring System</h2>
            <p style="margin:6px 0 0">Login/Register to continue. All analysis, weather, and chat are stored in database.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 1.8, 1])
    with c2:
        t1, t2 = st.tabs(["Login", "Register"])

        with t1:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="yourmail@gmail.com")
                password = st.text_input("Password", type="password")
                login_btn = st.form_submit_button("Login", use_container_width=True)

            if login_btn:
                user = authenticate_user(email, password)
                if user:
                    st.session_state.auth_user = user
                    st.session_state.guest_mode = False
                    apply_user_settings()
                    st.success("Login successful")
                    st.rerun()
                else:
                    st.error("Invalid email or password")

        with t2:
            with st.form("register_form"):
                name = st.text_input("Full Name", placeholder="Rupas Farmer")
                email = st.text_input("Email", key="reg_email", placeholder="rupas@gmail.com")
                password = st.text_input("Password (min 8 chars)", type="password")
                confirm = st.text_input("Confirm Password", type="password")
                reg_btn = st.form_submit_button("Register", use_container_width=True)

            if reg_btn:
                if not name.strip() or not email.strip() or not password.strip():
                    st.warning("Please fill all fields")
                elif password != confirm:
                    st.warning("Passwords do not match")
                else:
                    ok, msg = create_user(name, email, password)
                    if ok:
                        st.success(msg + " Now login.")
                    else:
                        st.error(msg)

        gc1, gc2, gc3 = st.columns([1, 2, 1])
        with gc2:
            if st.button("Continue as Guest", use_container_width=True):
                st.session_state.auth_user = {"id": 0, "full_name": "Guest Farmer", "email": "guest@local"}
                st.session_state.guest_mode = True
                st.session_state.default_location = "Delhi,IN"
                st.session_state.saved_api_key = ""
                st.rerun()


def page_home() -> None:
    st.markdown(
        f"""
        <div class="hero">
            <h1>👋 Welcome, {st.session_state.auth_user['full_name']}</h1>
            <p>Professional crop monitoring dashboard with login, database, real weather API support, and AI analysis.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="feature-grid">
            <div class="feature"><h3>📸 Upload Crop Image</h3><p>Upload rice leaf image and run disease detection.</p></div>
            <div class="feature"><h3>🌦 Weather Advisory</h3><p>Get live weather metrics and risk advisories.</p></div>
            <div class="feature"><h3>💬 Ask Chatbot</h3><p>Ask treatment, fertilizer, and prevention questions.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    user = st.session_state.auth_user
    if user and int(user["id"]) > 0:
        history = get_recent_analysis(int(user["id"]), limit=5)
        st.markdown("### Recent Analyses")
        if history:
            for item in history:
                st.markdown(
                    f"- **{item['created_at']}** | {item['image_name']} | {item['disease']} | {int(item['confidence']*100)}% | {item['severity']}"
                )
        else:
            st.info("No analysis history yet.")


def page_upload() -> None:
    st.markdown("## 📸 Image Upload Page")
    st.markdown('<div class="upload-box">', unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload rice leaf image", type=["jpg", "jpeg", "png", "webp"])
    st.markdown("</div>", unsafe_allow_html=True)

    if uploaded is not None:
        file_bytes = uploaded.getvalue()
        current_hash = hashlib.sha256(file_bytes).hexdigest()

        # If a new file is uploaded, clear previous analysis so results refresh correctly
        if current_hash != st.session_state.uploaded_image_hash:
            st.session_state.uploaded_image_hash = current_hash
            st.session_state.uploaded_image = Image.open(uploaded)
            st.session_state.uploaded_image_name = uploaded.name
            st.session_state.analysis_done = False
            st.session_state.disease_result = None
            st.session_state.severity_result = None
            st.session_state.fert_result = None
            st.session_state.loading_analysis = False

    if st.session_state.uploaded_image is not None:
        st.image(st.session_state.uploaded_image, caption="Preview image", use_container_width=True)

        if st.button("🔍 Analyse Crop", use_container_width=True):
            st.session_state.loading_analysis = True

    if st.session_state.loading_analysis and st.session_state.uploaded_image is not None:
        st.markdown('<div class="card"><h3>🔬 Analysing crop health...</h3><p>Please wait...</p></div>', unsafe_allow_html=True)
        with st.spinner("Processing..."):
            time.sleep(1.0)
            dr = predict_disease(st.session_state.uploaded_image)
            sr = classify_severity(dr["disease"], dr["confidence"], st.session_state.uploaded_image)
            fr = get_recommendation(dr["disease"], sr["level"])

            st.session_state.disease_result = dr
            st.session_state.severity_result = sr
            st.session_state.fert_result = fr
            st.session_state.analysis_done = True
            st.session_state.loading_analysis = False

            user = st.session_state.auth_user
            if user and int(user["id"]) > 0:
                save_analysis_log(
                    user_id=int(user["id"]),
                    image_name=st.session_state.uploaded_image_name or "uploaded_image",
                    disease=dr["disease"],
                    confidence=float(dr["confidence"]),
                    severity=sr["level"],
                    immediate_action=fr.get("immediate_action", ""),
                )

        st.success("Analysis completed. Open Results page.")


def page_results() -> None:
    st.markdown("## 📊 Results Page")
    if not st.session_state.analysis_done:
        st.info("No analysis yet. Go to Upload page first.")
        return

    dr = st.session_state.disease_result
    sr = st.session_state.severity_result
    fr = st.session_state.fert_result

    sev_text, sev_color = severity_style(sr["level"])

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🌿 Disease")
    st.markdown(f'<div class="result-name">{dr["disease"]}</div>', unsafe_allow_html=True)
    st.markdown(confidence_html(dr["confidence"]), unsafe_allow_html=True)
    st.caption(f"Prediction method: {dr.get('method', 'unknown')}")
    if dr.get("method") != "custom_model":
        st.warning("You are not using a trained custom rice model yet. Current prediction is demo-level and may repeat/swap classes.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### ⚠ Severity")
    st.markdown(f'<span class="sev-pill" style="background:{sev_color}">{sev_text}</span>', unsafe_allow_html=True)
    st.write(sr["advice"])
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🌱 Fertilizer")
    for x in fr.get("fertiliser", []):
        st.markdown(f"- {x}")
    st.markdown("</div>", unsafe_allow_html=True)


def page_weather() -> None:
    st.markdown("## 🌦️ Weather Advisory Page")

    location = st.text_input("Location", value=st.session_state.default_location)
    api_key_input = st.text_input(
        "OpenWeather API Key",
        type="password",
        value=st.session_state.saved_api_key,
        help="Use your real OpenWeather API key here.",
    )

    user = st.session_state.auth_user
    if user and int(user["id"]) > 0:
        if st.button("Save API Key & Location", use_container_width=True):
            save_user_settings(int(user["id"]), location, api_key_input)
            st.session_state.default_location = location
            st.session_state.saved_api_key = api_key_input
            st.success("Saved to database.")

    if st.button("Fetch Real Weather", use_container_width=True):
        key_to_use = api_key_input.strip() or st.session_state.saved_api_key
        st.session_state.weather_data = get_weather_advisory(location=location.strip(), api_key=key_to_use or None)

        w = st.session_state.weather_data
        if user and int(user["id"]) > 0 and w:
            save_weather_log(
                user_id=int(user["id"]),
                location=w["location"],
                temperature=float(w["temperature"]),
                humidity=float(w["humidity"]),
                wind_speed=float(w["wind_speed"]),
                description=w["description"],
                source=w["source"],
            )

    w = st.session_state.weather_data
    if not w:
        st.info("Fetch weather to see data.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🌡 Temperature", f"{w['temperature']}°C")
    c2.metric("💧 Humidity", f"{w['humidity']}%")
    c3.metric("💨 Wind", f"{w['wind_speed']} m/s")
    c4.metric("🌤 Condition", w["description"])

    st.markdown("### Advisory")
    for adv in w["advisories"]:
        st.markdown(f"- {adv}")


def page_chat() -> None:
    st.markdown("## 🤖 Chatbot Page")

    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-user">{msg["text"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bot">{msg["text"]}</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([5, 1])
    with c1:
        q = st.text_input("Message", placeholder="How to treat Leaf Blast?", key="chat_input_box")
    with c2:
        send = st.button("Send", use_container_width=True)

    if send and q.strip():
        user_msg = q.strip()
        bot_msg = get_response(user_msg)
        st.session_state.chat_history.append({"role": "user", "text": user_msg})
        st.session_state.chat_history.append({"role": "bot", "text": bot_msg})

        user = st.session_state.auth_user
        if user and int(user["id"]) > 0:
            save_chat_log(int(user["id"]), "user", user_msg)
            save_chat_log(int(user["id"]), "bot", bot_msg)

        st.rerun()

    st.markdown("### Quick buttons")
    q1, q2 = st.columns(2)
    with q1:
        if st.button("How to treat Leaf Blast?", use_container_width=True):
            msg = "How to treat Leaf Blast?"
            reply = get_response(msg)
            st.session_state.chat_history.append({"role": "user", "text": msg})
            st.session_state.chat_history.append({"role": "bot", "text": reply})
            st.rerun()
    with q2:
        if st.button("What fertilizer to use?", use_container_width=True):
            msg = "What fertilizer to use?"
            reply = get_response(msg)
            st.session_state.chat_history.append({"role": "user", "text": msg})
            st.session_state.chat_history.append({"role": "bot", "text": reply})
            st.rerun()


def page_summary() -> None:
    st.markdown("## 📌 Final Summary Screen")
    if not st.session_state.analysis_done:
        st.warning("Run analysis first from Upload page.")
        return

    dr = st.session_state.disease_result
    sr = st.session_state.severity_result
    fr = st.session_state.fert_result
    w = st.session_state.weather_data

    sev_text, _ = severity_style(sr["level"])
    weather_text = "No weather fetched"
    if w:
        weather_text = f"{w['description']} - humidity {w['humidity']}%"

    st.markdown(
        f"""
        <div class="summary-grid">
            <div class="summary-box"><h4>🌿 Disease</h4><p>{dr['disease']}</p></div>
            <div class="summary-box"><h4>⚠ Severity</h4><p>{sev_text}</p></div>
            <div class="summary-box"><h4>🌱 Action</h4><p>{fr.get('immediate_action', '')}</p></div>
            <div class="summary-box"><h4>🌦 Weather</h4><p>{weather_text}</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if not is_logged_in():
    auth_page()
    st.stop()

with st.sidebar:
    st.markdown("## Navigation")
    st.caption(f"User: {st.session_state.auth_user['full_name']}")
    page = st.radio(
        "Go to",
        [
            "🏠 Home",
            "📸 Upload",
            "📊 Results",
            "🌦 Weather",
            "🤖 Chatbot",
            "📌 Summary",
        ],
        index=["🏠 Home", "📸 Upload", "📊 Results", "🌦 Weather", "🤖 Chatbot", "📌 Summary"].index(st.session_state.active_page),
    )
    st.session_state.active_page = page

    st.divider()
    if st.button("Reset Analysis", use_container_width=True):
        reset_analysis()
        st.success("Analysis reset")

    if st.button("Logout", use_container_width=True):
        st.session_state.auth_user = None
        st.session_state.guest_mode = False
        reset_analysis()
        st.rerun()

if page == "🏠 Home":
    page_home()
elif page == "📸 Upload":
    page_upload()
elif page == "📊 Results":
    page_results()
elif page == "🌦 Weather":
    page_weather()
elif page == "🤖 Chatbot":
    page_chat()
else:
    page_summary()

st.markdown("---")
st.caption("Smart Rice Crop Monitoring System | Professional UI | SQLite persistent storage")







