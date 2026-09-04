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
import base64
import time

from carbon_calculator import build_result, EMISSION_FACTOR_KG_PER_KWH
from database import init_db, save_record, get_all_records, get_records_for_user, get_leaderboard

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
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Hide default Streamlit chrome for a cleaner "website" feel */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .block-container {
        padding-top: 1.5rem;
        max-width: 1100px;
    }

    /* Hero banner */
    .hero-banner {
        background: linear-gradient(135deg, #1B5E20 0%, #2E7D32 45%, #66BB6A 100%);
        border-radius: 18px;
        padding: 2.2rem 2.5rem;
        color: white;
        margin-bottom: 1.8rem;
        box-shadow: 0 8px 24px rgba(27, 94, 32, 0.25);
    }
    .hero-banner h1 {
        font-family: 'Poppins', sans-serif;
        font-size: 2.2rem;
        font-weight: 700;
        margin: 0 0 0.3rem 0;
        color: white;
    }
    .hero-banner p {
        font-size: 1.05rem;
        margin: 0;
        opacity: 0.92;
    }

    .section-title {
        font-family: 'Poppins', sans-serif;
        font-weight: 600;
        color: #1B5E20;
        font-size: 1.3rem;
        margin-top: 0.5rem;
        margin-bottom: 0.8rem;
        border-left: 4px solid #66BB6A;
        padding-left: 0.6rem;
    }

    /* Cards */
    .metric-card {
        background-color: #ffffff;
        border-radius: 14px;
        padding: 1.3rem 1.5rem;
        text-align: center;
        border: 1px solid #E0E0E0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 18px rgba(46,125,50,0.15);
    }
    .metric-card h2 {
        margin: 0.2rem 0 0 0;
        color: #2E7D32;
        font-family: 'Poppins', sans-serif;
        font-size: 1.8rem;
    }
    .metric-card p {
        margin: 0;
        color: #757575;
        font-size: 0.88rem;
        font-weight: 500;
    }

    .recommendation-banner {
        background: linear-gradient(135deg, #FFFDE7, #FFF8E1);
        border-left: 5px solid #FBC02D;
        padding: 1.1rem 1.4rem;
        border-radius: 10px;
        font-size: 1rem;
        margin-top: 1.2rem;
        box-shadow: 0 2px 8px rgba(251,192,45,0.15);
    }

    .badge-banner {
        background: linear-gradient(135deg, #E8F5E9, #F1F8E9);
        border: 1.5px solid #A5D6A7;
        border-radius: 30px;
        padding: 0.6rem 1.4rem;
        font-size: 1.05rem;
        margin: 0.8rem 0 1.2rem 0;
        display: inline-block;
        color: #1B5E20;
    }

    .leaderboard-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 0.5rem;
        background: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 2px 10px rgba(0,0,0,0.04);
    }
    .leaderboard-table th {
        background: linear-gradient(135deg, #2E7D32, #43A047);
        color: white;
        padding: 0.7rem 1rem;
        font-family: 'Poppins', sans-serif;
        font-weight: 600;
        text-align: left;
        font-size: 0.9rem;
    }
    .leaderboard-table td {
        padding: 0.65rem 1rem;
        border-bottom: 1px solid #F0F0F0;
        font-size: 0.92rem;
    }
    .leaderboard-table tr:last-child td {
        border-bottom: none;
    }
    .leaderboard-table tr:hover td {
        background-color: #F9FBE7;
    }

    .coming-soon-box {
        background-color: #FAFAFA;
        border: 1.5px dashed #BDBDBD;
        border-radius: 14px;
        padding: 2.5rem;
        text-align: center;
        color: #757575;
    }

    /* Buttons */
    div.stButton > button {
        background: linear-gradient(135deg, #2E7D32, #43A047);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.55rem 1.4rem;
        font-weight: 600;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    div.stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 14px rgba(46,125,50,0.35);
        color: white;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        font-weight: 600;
        padding: 0.6rem 1.2rem;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #F1F8E9;
    }

    .footer-note {
        text-align: center;
        color: #9E9E9E;
        font-size: 0.8rem;
        margin-top: 2.5rem;
        padding-top: 1rem;
        border-top: 1px solid #E0E0E0;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_hero(title: str, subtitle: str):
    st.markdown(
        f"""<div class="hero-banner"><h1>{title}</h1><p>{subtitle}</p></div>""",
        unsafe_allow_html=True,
    )


def render_footer():
    st.markdown(
        '<div class="footer-note">AI-Powered Carbon Footprint Tracking & Reduction System · Major Project</div>',
        unsafe_allow_html=True,
    )


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


def show_scanning_animation(image_bytes: bytes, seconds: float = 2.0):
    """
    Display the captured/uploaded image with an animated horizontal
    scan-line sweeping over it, like a real document scanner, for a
    short moment before showing the OCR result. Purely visual --
    doesn't affect the actual OCR logic.
    """
    encoded = base64.b64encode(image_bytes).decode()
    scanner_html = f"""
    <div style="position:relative; width:280px; margin:auto; overflow:hidden;
                border-radius:8px; border:2px solid #2E7D32;">
        <img src="data:image/jpeg;base64,{encoded}" style="width:100%; display:block;">
        <div style="position:absolute; left:0; width:100%; height:4px;
                    background:linear-gradient(90deg, rgba(46,125,50,0) 0%, #66BB6A 50%, rgba(46,125,50,0) 100%);
                    box-shadow:0 0 8px 2px #66BB6A;
                    animation: scanSweep {seconds}s ease-in-out infinite;"></div>
    </div>
    <style>
        @keyframes scanSweep {{
            0%   {{ top: 0%; }}
            50%  {{ top: 96%; }}
            100% {{ top: 0%; }}
        }}
    </style>
    """
    placeholder = st.empty()
    placeholder.markdown(scanner_html, unsafe_allow_html=True)
    with st.spinner("🔍 Scanning bill..."):
        time.sleep(seconds)
    placeholder.empty()


def run_ocr_on_bytes(image_bytes: bytes, caption: str, key_prefix: str):
    """
    Save uploaded/captured image bytes to a temp file, run OCR (with a
    scanning animation shown first), and return the extracted units.

    If no known bill pattern matched, but OCR still found plausible
    numbers on the bill, the user is shown those numbers to pick from
    -- instead of the system just giving up -- so it works reasonably
    well across bill layouts we haven't specifically coded for.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    show_scanning_animation(image_bytes)

    units, candidates = extract_units_consumed(tmp_path)

    st.image(image_bytes, caption=caption, width=280)

    if units is not None:
        st.success(f"✅ OCR detected **{units} units** consumed.")
        return units

    if candidates:
        st.info(
            "Couldn't automatically identify the exact field, but found these numbers "
            "on the bill. Select the correct **units consumed** value:"
        )
        choice = st.selectbox(
            "Detected numbers",
            options=["-- select --"] + candidates,
            key=f"{key_prefix}_candidates",
        )
        if choice != "-- select --":
            return float(choice)
        return None

    st.warning("⚠️ Couldn't automatically read this bill. Please enter manually.")
    return None


def render_output(units_consumed: float, user_name: str):
    """Render the styled Step 2 output: metric cards, eco-score, recommendation, save to DB."""
    st.subheader("Step 2: Output")

    if st.button("🧮 Calculate Carbon Footprint", type="primary"):
        result = build_result(units_consumed)
        score = result["ecoScore"]
        emission_value = float(result["carbonEmission"].split(" ")[0])

        # Grab the user's previous entry (if any) BEFORE saving the new one,
        # so we can show a "vs last time" comparison -- a simple trend
        # indicator inspired by similar carbon-tracking apps' progress views.
        previous_entries = get_records_for_user(user_name)
        previous_emission = previous_entries[0][3] if previous_entries else None

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

        # Month-over-month / entry-over-entry comparison
        if previous_emission is not None and previous_emission > 0:
            change_pct = ((emission_value - previous_emission) / previous_emission) * 100
            if change_pct < -1:
                st.success(f"📉 Down {abs(change_pct):.0f}% from your last entry ({previous_emission} kg CO2) — nice work!")
            elif change_pct > 1:
                st.warning(f"📈 Up {change_pct:.0f}% from your last entry ({previous_emission} kg CO2).")
            else:
                st.info(f"➖ About the same as your last entry ({previous_emission} kg CO2).")

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

        # Summary cards: best score so far, average this month, current streak
        best_score = int(df["Eco-Score"].max())
        avg_score = round(df["Eco-Score"].mean(), 1)
        streak = _calculate_good_score_streak(df)
        badge_emoji, badge_name = _get_badge(streak, avg_score)

        s1, s2, s3 = st.columns(3)
        with s1:
            st.markdown(f"""<div class="metric-card"><p>🏆 Best Eco-Score</p><h2>{best_score}</h2></div>""", unsafe_allow_html=True)
        with s2:
            st.markdown(f"""<div class="metric-card"><p>📈 Average Eco-Score</p><h2>{avg_score}</h2></div>""", unsafe_allow_html=True)
        with s3:
            st.markdown(f"""<div class="metric-card"><p>🔥 Current Streak</p><h2>{streak}</h2></div>""", unsafe_allow_html=True)

        st.markdown(
            f"""<div class="badge-banner">{badge_emoji} <b>{badge_name}</b></div>""",
            unsafe_allow_html=True,
        )

        st.write("")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.line_chart(df.set_index("Date")["Emission (kg CO2)"][::-1])

        st.write("")
        render_leaderboard()
    else:
        st.info("No records yet -- calculate your first footprint above.")


def _calculate_good_score_streak(df: pd.DataFrame) -> int:
    """
    Count how many of the most recent entries (across all users, in
    save order) have an eco-score of 75+ in a row. A simple, transparent
    gamification signal -- inspired by streak features in similar
    carbon-tracking apps -- computed purely from data already stored,
    no extra input needed.
    """
    streak = 0
    for score in df["Eco-Score"]:  # df is already most-recent-first
        if score >= 75:
            streak += 1
        else:
            break
    return streak


def _get_badge(streak: int, avg_score: float):
    """
    A simple, transparent badge tier based on overall average score and
    current streak -- purely for engagement/motivation, computed from
    data already stored (no new input needed).
    """
    if avg_score >= 85 and streak >= 3:
        return "🏆", "Eco Warrior"
    elif avg_score >= 70:
        return "🌳", "Eco Champion"
    elif avg_score >= 50:
        return "🌿", "Eco Aware"
    else:
        return "🌱", "Getting Started"


def render_leaderboard():
    """
    Leaderboard ranking users by total points (sum of their eco-scores
    across all entries) -- inspired by gamification features in similar
    public carbon-tracking projects (e.g. EcoTrackr, NAVIN). Top 3 get
    medal icons; more entries with better scores earns more points.
    """
    st.markdown('<p class="section-title">🏅 Leaderboard</p>', unsafe_allow_html=True)
    leaderboard = get_leaderboard()
    if not leaderboard:
        return

    medals = ["🥇", "🥈", "🥉"]
    rows_html = ""
    for i, (user, avg_score, points, entries) in enumerate(leaderboard):
        rank_display = medals[i] if i < 3 else f"#{i + 1}"
        rows_html += f"""
        <tr>
            <td style="text-align:center; font-size:1.2rem;">{rank_display}</td>
            <td><b>{user}</b></td>
            <td style="text-align:center;">{avg_score}</td>
            <td style="text-align:center;">{points}</td>
            <td style="text-align:center;">{entries}</td>
        </tr>"""

    table_html = f"""
    <table class="leaderboard-table">
        <thead>
            <tr><th>Rank</th><th>User</th><th>Avg Eco-Score</th><th>Points</th><th>Entries</th></tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    """
    st.markdown(table_html, unsafe_allow_html=True)
    st.caption("Points = sum of eco-scores across all your entries. Log more good-usage entries to climb the board.")


# ---------------------------------------------------------------------------
# Electricity Bill module (fully implemented)
# ---------------------------------------------------------------------------

def render_electricity_module():
    render_hero(
        "🌱 AI-Powered Carbon Footprint Tracker",
        "Electricity Bill Module — Input to Output Pipeline",
    )

    tab_overview, tab_demo, tab_history = st.tabs(["📋 Overview", "🧪 Try It Live", "📊 History"])

    with tab_overview:
        render_overview()

    with tab_demo:
        render_demo()

    with tab_history:
        render_history()

    render_footer()


def render_overview():
    st.markdown('<p class="section-title">How this module works</p>', unsafe_allow_html=True)
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

    st.markdown('<p class="section-title">Step 1: Provide your electricity usage</p>', unsafe_allow_html=True)

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
                extracted = run_ocr_on_bytes(uploaded_file.read(), "Uploaded bill", key_prefix="upload")
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
                extracted = run_ocr_on_bytes(camera_image.getvalue(), "Live-scanned bill", key_prefix="camera")
                units_consumed = extracted if extracted is not None else st.number_input(
                    "Electricity units consumed (kWh)", min_value=0.0, step=1.0
                )

    st.caption(f"Emission factor used: {EMISSION_FACTOR_KG_PER_KWH} kg CO2 per kWh")

    if units_consumed is not None and units_consumed >= 0:
        render_output(units_consumed, user_name)


# ---------------------------------------------------------------------------
# Placeholder modules -- from the project roadmap, not built yet.
# Replace each render_xxx_placeholder() call with a real render_xxx_module()
# function (same pattern as electricity above) as each module is built.
# ---------------------------------------------------------------------------

def render_placeholder(title: str, description: str):
    render_hero(title, "Coming Soon")
    st.markdown(
        f"""<div class="coming-soon-box">🚧<br><br>{description}<br><br>
        <i>Planned for a future release of this project.</i></div>""",
        unsafe_allow_html=True,
    )
    render_footer()


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
