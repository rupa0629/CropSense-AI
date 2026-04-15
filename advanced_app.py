import streamlit as st
from PIL import Image

from models.disease_model import predict_disease
from utils.severity import classify_severity
from utils.weather import get_weather_advisory
from utils.fertilizer import get_recommendation
from utils.chatbot import get_response
from utils.auth_db import init_db, create_user, authenticate_user

st.set_page_config(page_title="CropSense Advanced", page_icon="🌾", layout="wide")
init_db()

if "auth_user" not in st.session_state:
    st.session_state.auth_user = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "bot", "text": "Welcome to CropSense assistant."}]
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False
if "weather_data" not in st.session_state:
    st.session_state.weather_data = None

st.markdown(
    """
    <style>
    .stApp {
      background: radial-gradient(circle at 20% 0%, #e9f8ee 0, transparent 30%), #f6fbf7;
      color: #0f172a;
    }
    .hero {
      background: linear-gradient(120deg, #0f5132, #198754);
      color: #fff;
      border-radius: 14px;
      padding: 18px;
      margin-bottom: 14px;
      box-shadow: 0 8px 20px rgba(0,0,0,0.15);
    }
    .card {
      background: #fff;
      border: 1px solid #d5e4db;
      border-left: 5px solid #198754;
      border-radius: 12px;
      padding: 12px;
      margin-bottom: 10px;
    }
    .chat-user { background:#dcfce7; border-radius:10px; padding:8px; margin:6px 0 6px auto; width:fit-content; max-width:80%; }
    .chat-bot { background:#fff; border:1px solid #d5e4db; border-radius:10px; padding:8px; margin:6px auto 6px 0; width:fit-content; max-width:85%; }
    .login-box { max-width: 760px; margin: 20px auto; background: #fff; border: 1px solid #d5e4db; border-radius: 16px; padding: 16px; }
    [data-testid="stSidebar"] { background: #edf7f0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


def auth_screen() -> None:
    st.markdown('<div class="login-box"><h2>CropSense Secure Login</h2><p>Login or create an account to continue.</p></div>', unsafe_allow_html=True)
    tab_login, tab_register = st.tabs(["Login", "Create Account"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True, type="primary")
        if submit:
            user = authenticate_user(email, password)
            if user:
                st.session_state.auth_user = user
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid email or password")

    with tab_register:
        with st.form("register_form"):
            full_name = st.text_input("Full name")
            email = st.text_input("Email", key="reg_email")
            pwd = st.text_input("Password (min 8 chars)", type="password")
            confirm = st.text_input("Confirm password", type="password")
            submit_reg = st.form_submit_button("Create Account", use_container_width=True)
        if submit_reg:
            if not full_name.strip() or not email.strip() or not pwd:
                st.warning("Fill all fields")
            elif pwd != confirm:
                st.warning("Passwords do not match")
            else:
                ok, msg = create_user(full_name, email, pwd)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)


if not st.session_state.auth_user:
    auth_screen()
    st.stop()

with st.sidebar:
    st.markdown(f"### User: {st.session_state.auth_user['full_name']}")
    st.caption(st.session_state.auth_user["email"])
    if st.button("Logout", use_container_width=True):
        st.session_state.auth_user = None
        st.rerun()

    st.divider()
    weather_location = st.text_input("Field Location", value="Delhi,IN")
    api_key = st.text_input("OpenWeatherMap API Key", type="password")

st.markdown('<div class="hero"><h1>Smart Rice Crop Monitoring</h1><p>Advanced UI + login + DB support</p></div>', unsafe_allow_html=True)

left_col, right_col = st.columns([1, 1.1], gap="large")

with left_col:
    st.subheader("Upload Crop Image")
    uploaded = st.file_uploader("Upload", type=["jpg", "jpeg", "png", "webp"], label_visibility="collapsed")

    if uploaded:
        image = Image.open(uploaded)
        st.image(image, caption="Uploaded image", use_container_width=True)
        if st.button("Analyse Crop", type="primary", use_container_width=True):
            disease = predict_disease(image)
            severity = classify_severity(disease["disease"], disease["confidence"], image)
            fert = get_recommendation(disease["disease"], severity["level"])
            weather = get_weather_advisory(weather_location.strip(), api_key.strip() or None)
            st.session_state.analysis_done = True
            st.session_state.disease_result = disease
            st.session_state.severity_result = severity
            st.session_state.fert_result = fert
            st.session_state.weather_data = weather
            st.rerun()

    st.markdown("---")
    st.subheader("Weather")
    if st.button("Fetch Weather", use_container_width=True):
        st.session_state.weather_data = get_weather_advisory(weather_location.strip(), api_key.strip() or None)

    if st.session_state.weather_data:
        w = st.session_state.weather_data
        st.markdown(
            f'<div class="card"><b>{w["location"]}</b><br>Temp: {w["temperature"]} C | Humidity: {w["humidity"]}% | Wind: {w["wind_speed"]} m/s<br><small>{w["description"]}</small></div>',
            unsafe_allow_html=True,
        )
        for adv in w["advisories"]:
            st.markdown(f"- {adv}")

with right_col:
    st.subheader("Analysis Results")
    if st.session_state.analysis_done:
        dr = st.session_state.disease_result
        sr = st.session_state.severity_result
        fr = st.session_state.fert_result
        st.markdown(f'<div class="card"><b>Disease:</b> {dr["disease"]}<br><b>Confidence:</b> {int(dr["confidence"]*100)}%</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card" style="border-left-color:#f59e0b"><b>Severity:</b> {sr["level"]}<br>{sr["advice"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card" style="border-left-color:#0369a1"><b>Immediate Action:</b><br>{fr["immediate_action"]}</div>', unsafe_allow_html=True)

        t1, t2, t3, t4 = st.tabs(["Fertiliser", "Pesticide", "Cultural", "Prevention"])
        with t1:
            for i in fr.get("fertiliser", []):
                st.markdown(f"- {i}")
        with t2:
            for i in fr.get("pesticide", []):
                st.markdown(f"- {i}")
        with t3:
            for i in fr.get("cultural", []):
                st.markdown(f"- {i}")
        with t4:
            for i in fr.get("prevention", []):
                st.markdown(f"- {i}")
    else:
        st.info("Upload image and click Analyse Crop")

st.markdown("---")
st.subheader("Farmer Assistant Chatbot")
for m in st.session_state.chat_history:
    if m["role"] == "user":
        st.markdown(f'<div class="chat-user">{m["text"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bot">{m["text"]}</div>', unsafe_allow_html=True)

c1, c2 = st.columns([5, 1])
with c1:
    q = st.text_input("Ask question", label_visibility="collapsed", placeholder="How to treat leaf blast?", key="chat_q")
with c2:
    send = st.button("Send", use_container_width=True)

if send and q.strip():
    st.session_state.chat_history.append({"role": "user", "text": q.strip()})
    st.session_state.chat_history.append({"role": "bot", "text": get_response(q.strip())})
    st.rerun()

st.caption("CropSense Advanced")
