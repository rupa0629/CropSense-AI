"""Advanced CropSense dashboard app with full workflow and polished UX."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

from models.disease_model import predict_disease
from utils.auth_db import (
    authenticate_user,
    create_user,
    get_analysis_timeline,
    get_dashboard_counts,
    get_disease_distribution,
    get_recent_analysis,
    get_user_settings,
    init_db,
    save_analysis_log,
    save_chat_log,
    save_user_settings,
    save_weather_log,
)
from utils.chatbot import get_response
from utils.fertilizer import get_recommendation
from utils.severity import classify_severity
from utils.weather import get_weather_advisory

st.set_page_config(page_title="CropSense AI", page_icon="leaf", layout="wide")
init_db()


def bootstrap() -> None:
    defaults = {
        "auth_user": None,
        "guest_mode": False,
        "active_page": "Dashboard",
        "chat_history": [{"role": "bot", "text": "Hello. I am your AI farming assistant. Ask about disease, treatment, fertilizer, or weather."}],
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
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


bootstrap()

st.markdown(
    """
    <style>
    :root {
      --bg: #eef7f1;
      --card: #ffffff;
      --line: #deebe4;
      --text: #0f172a;
      --muted: #64748b;
      --green1: #0f7a52;
      --green2: #2eb775;
    }

    .stApp {
      background: radial-gradient(circle at 10% 0%, #e4f7ea 0%, transparent 40%),
                  radial-gradient(circle at 100% 100%, #e7f9ef 0%, transparent 38%),
                  var(--bg) !important;
      color: var(--text);
      font-family: "Segoe UI", "Inter", sans-serif;
    }

    [data-testid="stSidebar"] {
      background: #ffffff !important;
      border-right: 1px solid var(--line);
    }

    [data-testid="stSidebar"] * {
      color: #0f172a !important;
    }

    .sidebar-brand {
      background: #f8fcf9;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      margin-bottom: 10px;
    }

    .page-title {
      margin-bottom: 6px;
    }

    .hero {
      background: linear-gradient(120deg, #0d7b53, #189963, #3ec182);
      border-radius: 22px;
      padding: 22px;
      box-shadow: 0 20px 40px rgba(14, 120, 82, 0.22);
      margin-bottom: 14px;
    }

    .hero * {
      color: #ffffff !important;
    }

    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 8px 24px rgba(16, 24, 40, 0.06);
      margin-bottom: 12px;
    }

    .feature-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 12px;
    }

    .feature {
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      box-shadow: 0 6px 16px rgba(15, 23, 42, 0.05);
    }

    .upload-box {
      border: 2px dashed #9bd4b4;
      border-radius: 18px;
      background: #fafffc;
      padding: 16px;
    }

    .muted {
      color: var(--muted) !important;
      font-size: .9rem;
    }

    .conf-track {
      height: 12px;
      background: #d8eadf;
      border-radius: 999px;
      overflow: hidden;
      margin-bottom: 6px;
    }

    .conf-fill {
      height: 12px;
      background: linear-gradient(90deg, var(--green1), var(--green2));
      border-radius: 999px;
    }

    .chip {
      display: inline-block;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: .85rem;
      font-weight: 700;
    }

    .chat-user {
      margin: 6px 0 6px auto;
      width: fit-content;
      max-width: 80%;
      padding: 10px;
      border-radius: 14px 14px 4px 14px;
      background: #def9e7;
      border: 1px solid #bce9ce;
    }

    .chat-bot {
      margin: 6px auto 6px 0;
      width: fit-content;
      max-width: 86%;
      padding: 10px;
      border-radius: 14px 14px 14px 4px;
      background: #ffffff;
      border: 1px solid #d9e8df;
    }

    .login-wrap {
      max-width: 620px;
      margin: 16px auto;
      border: 1px solid var(--line);
      border-radius: 24px;
      overflow: hidden;
      background: #ffffff;
      box-shadow: 0 22px 50px rgba(14, 38, 28, 0.13);
    }

    .login-head {
      background: linear-gradient(140deg, #f8fffb, #f1f9f4);
      text-align: center;
      padding: 24px 16px 8px;
    }

    .stButton button {
      background: linear-gradient(120deg, #128455, #28a868) !important;
      color: #ffffff !important;
      border: 0 !important;
      border-radius: 12px !important;
      font-weight: 700 !important;
      min-height: 42px;
      box-shadow: 0 10px 22px rgba(20, 132, 84, 0.2);
    }

    .stTextInput input, .stTextArea textarea {
      border-radius: 12px !important;
      border: 1px solid #cfe1d7 !important;
      background: #ffffff !important;
      color: #0f172a !important;
    }

    @media (max-width: 900px) {
      .feature-grid { grid-template-columns: 1fr; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def is_logged_in() -> bool:
    return bool(st.session_state.auth_user or st.session_state.guest_mode)


def severity_style(level: str) -> tuple[str, str, str]:
    if level == "Mild":
        return "Mild", "#fef3c7", "#92400e"
    if level == "Moderate":
        return "Moderate", "#ffedd5", "#9a3412"
    if level == "Severe":
        return "Severe", "#fee2e2", "#991b1b"
    return "N/A", "#dcfce7", "#166534"


def confidence_html(confidence: float) -> str:
    pct = max(0, min(100, int(confidence * 100)))
    return (
        f'<div class="conf-track"><div class="conf-fill" style="width:{pct}%"></div></div>'
        f'<small class="muted">{pct}% confidence</small>'
    )


def image_quality_check(image: Image.Image) -> list[str]:
    arr = np.array(image.convert("RGB"))
    gray = arr.mean(axis=2)
    issues: list[str] = []
    if float(gray.mean()) < 45:
        issues.append("Image looks dark. Capture in better daylight.")
    if float(gray.std()) < 22:
        issues.append("Low contrast detected. Move closer and focus one leaf.")
    blur = float(np.abs(np.diff(gray, axis=0)).mean() + np.abs(np.diff(gray, axis=1)).mean())
    if blur < 8:
        issues.append("Image blur detected. Keep camera steady and refocus.")
    return issues


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
    s = get_user_settings(int(user["id"]))
    st.session_state.default_location = s["default_location"]
    st.session_state.saved_api_key = s["weather_api_key"]


def chat_context() -> dict:
    pred = None
    weather = None
    if st.session_state.analysis_done and st.session_state.disease_result:
        pred = {
            "disease": st.session_state.disease_result.get("disease"),
            "confidence": st.session_state.disease_result.get("confidence"),
            "severity": (st.session_state.severity_result or {}).get("level"),
            "immediate_action": (st.session_state.fert_result or {}).get("immediate_action"),
        }
    if st.session_state.weather_data:
        w = st.session_state.weather_data
        weather = {
            "location": w.get("location"),
            "temperature": w.get("temperature"),
            "humidity": w.get("humidity"),
            "description": w.get("description"),
        }
    recent = st.session_state.chat_history[-6:]
    return {"latest_prediction": pred, "latest_weather": weather, "recent_chat": recent}


def auth_page() -> None:
    st.markdown(
        """
        <div class="login-wrap">
          <div class="login-head">
            <h1 style="margin:0">Smart Rice</h1>
            <h3 style="margin:0">Crop Monitoring System</h3>
            <p class="muted">Login or Register to continue. Data is stored in local database.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 1.7, 1])
    with c2:
        login_tab, reg_tab = st.tabs(["Login", "Register"])

        with login_tab:
            with st.form("login_form"):
                email = st.text_input("Email Address", placeholder="Enter your email")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                submit = st.form_submit_button("Login", use_container_width=True)
            if submit:
                user = authenticate_user(email, password)
                if user:
                    st.session_state.auth_user = user
                    st.session_state.guest_mode = False
                    apply_user_settings()
                    st.rerun()
                st.error("Invalid email or password.")

        with reg_tab:
            with st.form("register_form"):
                name = st.text_input("Full Name")
                r_email = st.text_input("Email")
                p1 = st.text_input("Password", type="password")
                p2 = st.text_input("Confirm Password", type="password")
                reg = st.form_submit_button("Create Account", use_container_width=True)
            if reg:
                if p1 != p2:
                    st.warning("Passwords do not match.")
                else:
                    ok, msg = create_user(name, r_email, p1)
                    if ok:
                        st.success(msg + " Please login now.")
                    else:
                        st.error(msg)

        if st.button("Continue as Guest", use_container_width=True):
            st.session_state.auth_user = {"id": 0, "full_name": "Guest Farmer", "email": "guest@local"}
            st.session_state.guest_mode = True
            st.rerun()


def page_dashboard() -> None:
    user = st.session_state.auth_user
    st.markdown(
        f"""
        <div class="hero">
          <h4 style="margin:0">Welcome back</h4>
          <h1 style="margin:0">{user['full_name']}</h1>
          <p style="margin-top:8px">Professional crop monitoring dashboard with disease AI, weather advisory, and assistant support.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="feature-grid">
          <div class="feature"><h4>Upload Crop Image</h4><p class="muted">Upload leaf image and run disease detection.</p></div>
          <div class="feature"><h4>Weather Advisory</h4><p class="muted">Fetch live weather and risk advisory.</p></div>
          <div class="feature"><h4>AI Chatbot</h4><p class="muted">Ask treatment and farming questions.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if int(user["id"]) > 0:
        s = get_dashboard_counts(int(user["id"]))
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Analyses", s["analysis_count"])
        m2.metric("Weather Checks", s["weather_count"])
        m3.metric("Chat Messages", s["chat_count"])

        st.markdown("### Recent Analyses")
        rows = get_recent_analysis(int(user["id"]), limit=8)
        if rows:
            df = pd.DataFrame(rows)
            df["confidence"] = (df["confidence"] * 100).round(1).astype(str) + "%"
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No analysis history yet.")


def page_upload() -> None:
    st.markdown("## Upload Crop Image")
    left, right = st.columns([2, 1])

    with left:
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        up = st.file_uploader("Choose image", type=["jpg", "jpeg", "png", "webp"])
        st.markdown("</div>", unsafe_allow_html=True)

        if up is not None:
            h = hashlib.sha256(up.getvalue()).hexdigest()
            if h != st.session_state.uploaded_image_hash:
                st.session_state.uploaded_image_hash = h
                st.session_state.uploaded_image = Image.open(up)
                st.session_state.uploaded_image_name = up.name
                st.session_state.analysis_done = False

        if st.session_state.uploaded_image is not None:
            st.image(st.session_state.uploaded_image, caption="Preview", use_container_width=True)
            issues = image_quality_check(st.session_state.uploaded_image)
            if issues:
                for i in issues:
                    st.warning(i)
            else:
                st.success("Image quality looks good for analysis.")

            if st.button("Analyze Crop", use_container_width=True):
                st.session_state.loading_analysis = True

    with right:
        st.markdown(
            '<div class="card"><h4>Photo Guidelines</h4><p class="muted">Use daylight, focus one leaf, keep affected region visible, avoid blur.</p></div>',
            unsafe_allow_html=True,
        )

    if st.session_state.loading_analysis and st.session_state.uploaded_image is not None:
        with st.spinner("Analyzing crop health..."):
            time.sleep(0.8)
            dr = predict_disease(st.session_state.uploaded_image)
            if dr.get("needs_retake"):
                sr = {"level": "Mild", "advice": "Prediction uncertain. Retake a clearer close-up image and try again."}
                fr = {
                    "immediate_action": "Retake image before treatment decision.",
                    "fertiliser": [
                        "Capture single leaf in focus.",
                        "Avoid shadows and glare.",
                        "Keep camera distance 15 to 25 cm.",
                    ],
                }
            else:
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
                    int(user["id"]),
                    st.session_state.uploaded_image_name or "uploaded_image",
                    dr["disease"],
                    float(dr["confidence"]),
                    sr["level"],
                    fr.get("immediate_action", ""),
                )

        st.success("Analysis completed. Open Results page.")


def page_results() -> None:
    st.markdown("## Results")
    if not st.session_state.analysis_done:
        st.info("Run analysis from Upload page first.")
        return

    dr = st.session_state.disease_result
    sr = st.session_state.severity_result
    fr = st.session_state.fert_result
    sev, bg, fg = severity_style(sr["level"])

    c1, c2 = st.columns([2.2, 1])
    with c1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"### Disease: {dr['disease']}")
        st.markdown(confidence_html(float(dr.get("confidence", 0.0))), unsafe_allow_html=True)
        st.caption(f"Model: {dr.get('method', 'unknown')} | Margin: {dr.get('margin', 0.0):.3f}")
        if dr.get("needs_retake"):
            st.error(dr.get("uncertainty_reason", "Prediction is uncertain."))
        probs = dr.get("all_probs", {})
        if probs:
            rank = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:3]
            st.markdown("Top predictions")
            for k, v in rank:
                st.markdown(f"- {k}: {int(v*100)}%")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card"><h4>Treatment and Recommendations</h4>', unsafe_allow_html=True)
        for i in fr.get("fertiliser", []):
            st.markdown(f"- {i}")
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="card"><h4>Severity</h4>', unsafe_allow_html=True)
        st.markdown(f'<span class="chip" style="background:{bg};color:{fg}">{sev}</span>', unsafe_allow_html=True)
        st.write(sr.get("advice", ""))
        st.markdown("</div>", unsafe_allow_html=True)


def page_weather() -> None:
    st.markdown("## Weather Dashboard")
    a, b = st.columns([2, 1])
    with a:
        loc = st.text_input("Location", value=st.session_state.default_location)
    with b:
        key = st.text_input("OpenWeather API Key", type="password", value=st.session_state.saved_api_key)

    user = st.session_state.auth_user
    p1, p2 = st.columns(2)
    with p1:
        if st.button("Save Location and API Key", use_container_width=True) and user and int(user["id"]) > 0:
            save_user_settings(int(user["id"]), loc, key)
            st.session_state.default_location = loc
            st.session_state.saved_api_key = key
            st.success("Saved.")
    with p2:
        if st.button("Fetch Weather", use_container_width=True):
            st.session_state.weather_data = get_weather_advisory(loc.strip(), key.strip() or None)
            w = st.session_state.weather_data
            if user and int(user["id"]) > 0 and w:
                save_weather_log(
                    int(user["id"]),
                    w["location"],
                    float(w["temperature"]),
                    float(w["humidity"]),
                    float(w["wind_speed"]),
                    w["description"],
                    w["source"],
                )

    w = st.session_state.weather_data
    if not w:
        st.info("Fetch weather to see metrics.")
        return

    st.markdown('<div class="hero">', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Temperature", f"{w['temperature']} C")
    m2.metric("Humidity", f"{w['humidity']}%")
    m3.metric("Wind", f"{w['wind_speed']} m/s")
    m4.metric("Condition", w["description"])
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### Advisory")
    for a in w["advisories"]:
        st.markdown(f"- {a}")


def page_chatbot() -> None:
    st.markdown("## AI Farming Assistant")
    left, right = st.columns([2.2, 1])

    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        for m in st.session_state.chat_history:
            cls = "chat-user" if m["role"] == "user" else "chat-bot"
            st.markdown(f'<div class="{cls}">{m["text"]}</div>', unsafe_allow_html=True)
        in1, in2 = st.columns([5, 1])
        with in1:
            q = st.text_input("", placeholder="Type your question...", key="chat_input")
        with in2:
            send = st.button("Send", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="card"><h4>Suggested Questions</h4><p class="muted">How to treat Leaf Blast?<br>Best fertilizer for Brown Spot?<br>How to prevent Bacterial Blight?</p></div>', unsafe_allow_html=True)
        st.markdown('<div class="card"><h4>Tips</h4><p class="muted">Mention disease name, crop stage, and weather for better response.</p></div>', unsafe_allow_html=True)

    if send and q.strip():
        user_msg = q.strip()
        reply = get_response(user_msg, context=chat_context())
        st.session_state.chat_history.append({"role": "user", "text": user_msg})
        st.session_state.chat_history.append({"role": "bot", "text": reply})

        user = st.session_state.auth_user
        if user and int(user["id"]) > 0:
            save_chat_log(int(user["id"]), "user", user_msg)
            save_chat_log(int(user["id"]), "bot", reply)

        st.rerun()


def page_summary() -> None:
    st.markdown("## Summary Overview")
    user = st.session_state.auth_user
    if not user or int(user["id"]) <= 0:
        st.info("Login with registered account to view analytics.")
        return

    uid = int(user["id"])
    counts = get_dashboard_counts(uid)
    dist = get_disease_distribution(uid, limit=100)
    timeline = get_analysis_timeline(uid, limit=45)

    a, b, c = st.columns(3)
    a.metric("Total Analyses", counts["analysis_count"])
    b.metric("Weather Checks", counts["weather_count"])
    c.metric("Chat Messages", counts["chat_count"])

    l, r = st.columns(2)
    with l:
        st.markdown('<div class="card"><h4>Disease Distribution</h4>', unsafe_allow_html=True)
        if dist:
            st.bar_chart(pd.DataFrame(dist).set_index("disease"))
        else:
            st.info("No disease records yet.")
        st.markdown("</div>", unsafe_allow_html=True)
    with r:
        st.markdown('<div class="card"><h4>Confidence Trend</h4>', unsafe_allow_html=True)
        if timeline:
            df = pd.DataFrame(timeline)
            df["confidence_pct"] = (df["confidence"] * 100).round(2)
            st.line_chart(df[["confidence_pct"]])
        else:
            st.info("No confidence history yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    rec = get_recent_analysis(uid, limit=10)
    st.markdown("### Recent Analysis Table")
    if rec:
        dfr = pd.DataFrame(rec)
        dfr["confidence"] = (dfr["confidence"] * 100).round(1).astype(str) + "%"
        st.dataframe(dfr, use_container_width=True)
    else:
        st.info("No recent analyses.")


if not is_logged_in():
    auth_page()
    st.stop()

with st.sidebar:
    st.markdown(
        f"""
        <div class="sidebar-brand">
          <h3 style="margin:0">CropGuard AI</h3>
          <p class="muted" style="margin:4px 0 0">Smart Farming, Better Future</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pages = ["Dashboard", "Upload", "Results", "Weather", "Chatbot", "Summary"]
    idx = pages.index(st.session_state.active_page) if st.session_state.active_page in pages else 0
    page = st.radio("Navigation", pages, index=idx)
    st.session_state.active_page = page

    st.divider()
    if st.button("Reset Analysis", use_container_width=True):
        reset_analysis()
        st.success("Analysis reset done.")

    if st.button("Logout", use_container_width=True):
        st.session_state.auth_user = None
        st.session_state.guest_mode = False
        reset_analysis()
        st.rerun()

    st.markdown("---")
    user_name = st.session_state.auth_user["full_name"] if st.session_state.auth_user else "Guest"
    st.caption(f"User: {user_name}")
    st.caption(datetime.now().strftime("%d %b %Y, %I:%M %p"))

if page == "Dashboard":
    page_dashboard()
elif page == "Upload":
    page_upload()
elif page == "Results":
    page_results()
elif page == "Weather":
    page_weather()
elif page == "Chatbot":
    page_chatbot()
else:
    page_summary()

st.markdown("---")
st.caption("Smart Rice Crop Monitoring System | Advanced UI | SQLite persistence")
