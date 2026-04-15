# 🌾 Smart Rice Crop Monitoring & Advisory System

> AI-powered rice disease detection, severity analysis, weather advisory,
> fertiliser recommendations, and farmer chatbot — all in one Streamlit app.

---

## 📁 Project Structure

```
rice_crop_monitor/
│
├── app.py                      ← Main Streamlit application
│
├── models/
│   ├── __init__.py
│   └── disease_model.py        ← MobileNetV2-based disease classifier
│
├── utils/
│   ├── __init__.py
│   ├── severity.py             ← Severity classification (Mild/Moderate/Severe)
│   ├── weather.py              ← OpenWeatherMap API integration
│   ├── fertilizer.py           ← Rule-based fertiliser recommendation engine
│   └── chatbot.py              ← Rule-based keyword-matching chatbot
│
├── requirements.txt            ← Python dependencies
└── README.md                   ← This file
```

---

## ⚙️ Setup Instructions (Step-by-Step)

### Step 1 — Prerequisites

Make sure you have **Python 3.10 or higher** installed.

```bash
python --version   # should show 3.10+
```

---

### Step 2 — Create a virtual environment (recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

---

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

> ⏱️ First install takes 3–5 minutes (TensorFlow download ~200 MB).
> After that, everything runs instantly.

---

### Step 4 — (Optional) Get a free weather API key

1. Go to [https://openweathermap.org/api](https://openweathermap.org/api)
2. Sign up for a free account
3. Copy your API key
4. Paste it into the **API Key** field in the app sidebar

Without a key, the app uses **demo weather data** — all other features work fully.

---

### Step 5 — Run the application

```bash
streamlit run app.py
```

The app opens automatically at **http://localhost:8501** in your browser.

---

## 🚀 How to Use

| Step | Action |
|------|--------|
| 1 | Upload a rice leaf / field photo (JPG, PNG, WEBP) |
| 2 | Click **🔍 Analyse Crop** |
| 3 | View **disease detected**, **severity level**, and **treatment plan** |
| 4 | Click **🔄 Fetch Weather** for field advisory |
| 5 | Type a question in the **chatbot** or click a quick question |

---

## 📊 Sample Outputs

### Disease Detection
```
Detected:   Leaf Blast  🍃
Confidence: 74%
Method:     heuristic (MobileNetV2 feature-map based)
```

### Severity
```
Level:   Moderate 🟠
Advice:  Begin treatment within 48 hours
Anomalous pixel area: 38.2%
```

### Fertiliser Plan
```
Immediate:  Remove infected leaves
Fertiliser: Reduce N, add Silicon
Pesticide:  Tricyclazole 75 WP @ 0.6 g/L
Cultural:   Maintain 5 cm flood water
```

### Weather
```
Location:    Delhi
Temperature: 31°C  Humidity: 72%
Advisory:    Temperature optimal; humidity acceptable;
             Clear sky — good conditions for spraying.
```

### Chatbot
```
You: How to treat leaf blast?
Bot: 🍃 Leaf Blast causes diamond-shaped grey lesions...
     Reduce nitrogen and spray Tricyclazole to control it.
```

---

## 🧠 Module Explanations (Viva-ready)

### 1. Disease Detection (`models/disease_model.py`)
- Uses **MobileNetV2** pretrained on ImageNet as the backbone
- MobileNetV2 uses **depthwise separable convolutions** → very fast on CPU
- Extracts features → maps ImageNet concepts to rice disease classes
- In production: replace the final dense layer with a fine-tuned head trained
  on a rice disease dataset (e.g., Kaggle Rice Leaf Disease Dataset)
- Fallback heuristic uses RGB channel statistics as a simple classifier

### 2. Severity Detection (`utils/severity.py`)
- **Hybrid approach**: 60% model confidence + 40% pixel analysis
- Pixel analysis: counts "non-green" pixels (anomalous areas)
- Three levels: Mild (<50% combined), Moderate (<75%), Severe (≥75%)
- Output includes treatment urgency colour coding

### 3. Weather Advisory (`utils/weather.py`)
- Calls **OpenWeatherMap REST API** (`/data/2.5/weather`)
- Parses temperature, humidity, wind, description
- Rule-based advisory engine: maps metric ranges to farming actions
- Graceful fallback to demo data when offline / no API key

### 4. Fertiliser Recommendation (`utils/fertilizer.py`)
- Pure **rule-based expert system** (no ML needed here)
- Knowledge base: 4 diseases × 4 action categories
- Returns actionable, stage-specific field instructions
- Urgency level is cross-linked with severity output

### 5. Farmer Chatbot (`utils/chatbot.py`)
- **Keyword matching NLP** (no external NLP library required)
- Knowledge base: ~20 topic clusters covering diseases, nutrients, irrigation, etc.
- Multi-keyword scoring: selects answer with most keyword matches
- Beginner-friendly language; Markdown formatting for readability

### 6. Frontend (`app.py`)
- **Streamlit** single-page app with custom CSS theming
- Session state used for: chat history, analysis results, weather cache
- Responsive 2-column layout; tabbed recommendation panels
- Custom CSS: gradient header, card borders, confidence bars, chat bubbles

---

## 🔧 Customisation

| What to change | Where |
|----------------|-------|
| Add more diseases | `DISEASE_CLASSES` in `disease_model.py` |
| Fine-tune weights | Replace `_get_backbone()` in `disease_model.py` |
| Add new chatbot topics | Append `(keywords, answer)` to `_KB` in `chatbot.py` |
| Change default city | `weather_location` default in sidebar (`app.py`) |
| Adjust severity thresholds | `_MILD_MAX` / `_MODERATE_MAX` in `severity.py` |

---

## 📌 Requirements Summary

| Library | Purpose |
|---------|---------|
| `streamlit` | Web UI framework |
| `tensorflow-cpu` | MobileNetV2 backbone |
| `Pillow` | Image loading & processing |
| `numpy` | Array operations |
| `requests` | Weather API calls |

---

*Built for educational purposes. Always consult a certified agronomist for critical crop decisions.*
