"""
app.py

Main Streamlit application for the AI-Powered Carbon Footprint Tracker.

Currently implements the Electricity Bill module end-to-end:
    Input (manual / upload / live camera) -> OCR -> Carbon Calculation
    -> Eco-Score & Recommendation -> Storage -> History Dashboard

The sidebar lists all modules from the project roadmap so new ones
(Transportation, Fuel Usage, ML Prediction) can be dropped in later
without restructuring the app -- each just needs its own
`render_xxx_module()` function following the same pattern as
`render_electricity_module()` below.

Run with:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import tempfile

from carbon_calculator import build_result, EMISSION_FACTOR_KG_PER_KWH
from database import init_db, save_record, get_all_records

# OCR is optional -- app still works without Tesseract installed,
# it just disables the "upload"/"live scan" input options.
try:
    from ocr_parser import extract_units_consumed
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


# ---------------------------------------------------------------------------
# Page setup & styling
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Carbon Footprint Tracker",
    page_icon="🌱",
    layout="wide",
)
init_db()

CUSTOM_CSS = """
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1B5E20;
        margin-bottom: 0;
    }
    .sub-header {
        color: #558B2F;
        font-size: 1rem;
        margin-top: 0;
    }
    .metric-card {
        background-color: #F1F8E9;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        text-align: center;
        border: 1px solid #C5E1A5;
    }
    .metric-card h2 {
        margin: 0;
        color: #2E7D32;
        font-size: 1.8rem;
    }
    .metric-card p {
        margin: 0;
        color: #616161;
        font-size: 0.9rem;
    }
    .recommendation-banner {
        background-color: #FFF8E1;
        border-left: 5px solid #FBC02D;
        padding: 1rem 1.2rem;
        border-radius: 6px;
        font-size: 1rem;
        margin-top: 1rem;
    }
    .coming-soon-box {
        background-color: #FAFAFA;
        border: 1px dashed #BDBDBD;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        color: #757575;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def eco_score_color(score: int) -> str:
    if score >= 75:
        return "#2E7D32"   # green
    elif score >= 50:
        return "#F9A825"   # amber
    else:
        return "#C62828"   # red


def render_eco_gauge(score: int):
    """Render a circular gauge for the eco-score using Plotly (looks much better on screen than a plain progress bar)."""
    color = eco_score_color(score)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": " / 100", "font": {"size": 34}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 50], "color": "#FFEBEE"},
                    {"range": [50, 75], "color": "#FFF8E1"},
                    {"range": [75, 100], "color": "#E8F5E9"},
                ],
            },
            title={"text": "Eco-Score", "font": {"size": 18}},
        )
    )
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)


def run_ocr_on_bytes(image_bytes: bytes, caption: str):
    """
    Save uploaded/captured image bytes to a temp file, run OCR, show the
    image, and return the extracted units (or None if extraction failed).
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    st.image(image_bytes, caption=caption, width=280)

    extracted = extract_units_consumed(tmp_path)
    if extracted is not None:
        st.success(f"✅ OCR detected **{extracted} units** consumed.")
        return extracted

    st.warning("⚠️ Couldn't automatically read units from this image. Please enter manually.")
    return None


def render_output(units_consumed: float, user_name: str):
    """Render the styled Step 2 output: metric cards, eco-score, recommendation, save to DB."""
    st.subheader("Step 2: Output")

    if st.button("🧮 Calculate carbon footprint", type="primary"):
        result = build_result(units_consumed)
        score = result["ecoScore"]

        left_col, right_col = st.columns([1, 1])

        with left_col:
            st.markdown(
                f"""<div class="metric-card"><p>⚡ Units Consumed</p>
                <h2>{units_consumed}</h2></div>""",
                unsafe_allow_html=True,
            )
            st.write("")
            st.markdown(
                f"""<div class="metric-card"><p>🌍 Carbon Emission</p>
                <h2>{result['carbonEmission']}</h2></div>""",
                unsafe_allow_html=True,
            )

        with right_col:
            render_eco_gauge(score)

        st.markdown(
            f"""<div class="recommendation-banner">💡 <b>Recommendation:</b> {result['recommendation']}</div>""",
            unsafe_allow_html=True,
        )

        emission_value = float(result["carbonEmission"].split(" ")[0])
        save_record(
            user_name=user_name,
            electricity_units=units_consumed,
            carbon_emission_kg=emission_value,
            eco_score=score,
            recommendation=result["recommendation"],
        )
        st.toast("Saved to your history!")


def render_history():
    st.subheader("📊 Your History")
    records = get_all_records()
    if records:
        df = pd.DataFrame(
            records,
            columns=["ID", "User", "Units (kWh)", "Emission (kg CO2)", "Eco-Score", "Recommendation", "Date"],
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.line_chart(df.set_index("Date")["Emission (kg CO2)"][::-1])
    else:
        st.info("No records yet -- calculate your first footprint above.")


# ---------------------------------------------------------------------------
# Electricity Bill module (fully implemented)
# ---------------------------------------------------------------------------

def render_electricity_module():
    st.markdown('<p class="main-header">🌱 AI-Powered Carbon Footprint Tracker</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Electricity Bill Module -- Input to Output Pipeline</p>', unsafe_allow_html=True)
    st.divider()

    tab_overview, tab_demo, tab_history = st.tabs(["📋 Overview", "🧪 Try It Live", "📊 History"])

    with tab_overview:
        render_overview()

    with tab_demo:
        render_demo()

    with tab_history:
        render_history()


def render_overview():
    st.subheader("How this module works")
    c1, c2, c3, c4 = st.columns(4)
    steps = [
        ("📄", "1. Input", "Bill photo, live camera scan, or manual entry"),
        ("🔍", "2. OCR Extraction", "Units consumed (kWh) is read automatically"),
        ("🧮", "3. Calculation", "Units × emission factor → kg CO2 emitted"),
        ("📊", "4. Output", "Emission, eco-score & a personalized tip"),
    ]
    for col, (icon, title, desc) in zip([c1, c2, c3, c4], steps):
        with col:
            st.markdown(
                f"""<div class="metric-card" style="min-height:150px;">
                <div style="font-size:2rem;">{icon}</div>
                <p style="font-weight:600; color:#2E7D32;">{title}</p>
                <p style="font-size:0.85rem;">{desc}</p></div>""",
                unsafe_allow_html=True,
            )

    st.write("")
    st.info(
        f"**Formula used:** Carbon Emission (kg CO2) = Units Consumed (kWh) × "
        f"{EMISSION_FACTOR_KG_PER_KWH} kg CO2/kWh"
    )
    st.caption(
        "This module works fully offline from any dataset -- OCR uses a pretrained engine, "
        "and the calculation is formula/rule-based. A dataset is only needed later, for the "
        "upcoming ML Prediction module."
    )


def render_demo():
    user_name = st.text_input("Your name", value="Guest")

    st.subheader("Step 1: Provide your electricity usage")

    input_mode = st.radio(
        "How would you like to provide your data?",
        [
            "Enter units manually",
            "Upload electricity bill image (OCR)",
            "Scan live using camera (OCR)",
        ],
        horizontal=True,
    )

    units_consumed = None

    if input_mode == "Enter units manually":
        units_consumed = st.number_input("Electricity units consumed (kWh)", min_value=0.0, step=1.0)

    elif input_mode == "Upload electricity bill image (OCR)":
        if not OCR_AVAILABLE:
            st.warning(
                "OCR dependencies (pytesseract / opencv-python) or the Tesseract "
                "engine aren't installed. Falling back to manual entry below."
            )
            units_consumed = st.number_input("Electricity units consumed (kWh)", min_value=0.0, step=1.0)
        else:
            uploaded_file = st.file_uploader("Upload a photo/scan of your bill", type=["jpg", "jpeg", "png"])
            if uploaded_file is not None:
                extracted = run_ocr_on_bytes(uploaded_file.read(), "Uploaded bill")
                units_consumed = extracted if extracted is not None else st.number_input(
                    "Electricity units consumed (kWh)", min_value=0.0, step=1.0
                )

    else:  # Scan live using camera (OCR)
        if not OCR_AVAILABLE:
            st.warning(
                "OCR dependencies (pytesseract / opencv-python) or the Tesseract "
                "engine aren't installed. Falling back to manual entry below."
            )
            units_consumed = st.number_input("Electricity units consumed (kWh)", min_value=0.0, step=1.0)
        else:
            st.caption("Point your camera at the full bill, keep it flat and well-lit, then click Take Photo.")
            camera_image = st.camera_input("Scan your electricity bill")
            if camera_image is not None:
                extracted = run_ocr_on_bytes(camera_image.getvalue(), "Live-scanned bill")
                units_consumed = extracted if extracted is not None else st.number_input(
                    "Electricity units consumed (kWh)", min_value=0.0, step=1.0
                )

    st.caption(f"Emission factor used: {EMISSION_FACTOR_KG_PER_KWH} kg CO2 per kWh")

    if units_consumed is not None and units_consumed > 0:
        render_output(units_consumed, user_name)


# ---------------------------------------------------------------------------
# Placeholder modules -- from the project roadmap, not built yet.
# Replace each render_xxx_placeholder() call with a real render_xxx_module()
# function (same pattern as electricity above) as each module is built.
# ---------------------------------------------------------------------------

def render_placeholder(title: str, description: str):
    st.markdown(f'<p class="main-header">{title}</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Coming Soon</p>', unsafe_allow_html=True)
    st.divider()
    st.markdown(
        f"""<div class="coming-soon-box">🚧<br><br>{description}<br><br>
        <i>Planned for a future release of this project.</i></div>""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Sidebar navigation across all planned modules
# ---------------------------------------------------------------------------

st.sidebar.title("🌍 Carbon Tracker")
st.sidebar.caption("AI-Powered Carbon Footprint Tracking & Reduction System")

module = st.sidebar.radio(
    "Modules",
    [
        "⚡ Electricity Bill",
        "🚗 Transportation (GPS)",
        "⛽ Fuel Usage",
        "🔮 ML Emission Prediction",
    ],
)

st.sidebar.divider()
st.sidebar.caption("Project Status")
st.sidebar.markdown(
    "- ✅ Electricity Bill Module\n"
    "- 🚧 Transportation Module\n"
    "- 🚧 Fuel Usage Module\n"
    "- 🚧 ML Prediction Module"
)

if module == "⚡ Electricity Bill":
    render_electricity_module()
elif module == "🚗 Transportation (GPS)":
    render_placeholder("🚗 Transportation Module", "GPS-based travel tracking to calculate transportation emissions.")
elif module == "⛽ Fuel Usage":
    render_placeholder("⛽ Fuel Usage Module", "Track fuel consumption and its associated carbon emissions.")
else:
    render_placeholder("🔮 ML Emission Prediction", "Machine learning models to forecast future carbon emissions based on usage history.")
