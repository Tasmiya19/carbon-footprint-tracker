"""
app.py

Main Streamlit application. Lets a user either:
  1. Type in electricity units consumed manually, OR
  2. Upload a photo of their electricity bill (OCR extracts the units)

Then calculates carbon emissions, an eco-score, and a recommendation,
saves the result, and shows a history chart.

Run with:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import tempfile

from carbon_calculator import build_result
from database import init_db, save_record, get_all_records

# Set OCR import as optional -- app still works without Tesseract installed,
# it just disables the "upload a bill" option.
try:
    from ocr_parser import extract_units_consumed
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


st.set_page_config(page_title="Carbon Footprint Tracker", page_icon="🌱")
init_db()

st.title("🌱 AI-Powered Carbon Footprint Tracker")
st.caption("Electricity Bill Module -- Input to Output Demo")

user_name = st.text_input("Your name", value="Guest")

st.subheader("Step 1: Provide your electricity usage")

input_mode = st.radio(
    "How would you like to provide your data?",
    [
        "Enter units manually",
        "Upload electricity bill image (OCR)",
        "Scan live using camera (OCR)",
    ],
)

units_consumed = None


def run_ocr_on_bytes(image_bytes: bytes, caption: str):
    """
    Save uploaded/captured image bytes to a temp file, run OCR, show the
    image, and return the extracted units (or None if extraction failed).
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    st.image(image_bytes, caption=caption, width=300)

    extracted = extract_units_consumed(tmp_path)
    if extracted is not None:
        st.success(f"OCR detected {extracted} units consumed.")
        return extracted

    st.warning("Couldn't automatically read units from this image. Please enter manually.")
    return None


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

st.subheader("Step 2: Output")

if units_consumed is not None and units_consumed > 0:
    if st.button("Calculate carbon footprint"):
        result = build_result(units_consumed)

        col1, col2 = st.columns(2)
        col1.metric("Carbon Emission", result["carbonEmission"])
        col2.metric("Eco-Score", result["ecoScore"])
        st.info(f"💡 Recommendation: {result['recommendation']}")

        # Save to database
        emission_value = float(result["carbonEmission"].split(" ")[0])
        save_record(
            user_name=user_name,
            electricity_units=units_consumed,
            carbon_emission_kg=emission_value,
            eco_score=result["ecoScore"],
            recommendation=result["recommendation"],
        )
        st.toast("Saved to your history!")

st.subheader("Your History")
records = get_all_records()
if records:
    df = pd.DataFrame(
        records,
        columns=["ID", "User", "Units (kWh)", "Emission (kg CO2)", "Eco-Score", "Recommendation", "Date"],
    )
    st.dataframe(df, use_container_width=True)
    st.line_chart(df.set_index("Date")["Emission (kg CO2)"][::-1])
else:
    st.write("No records yet -- calculate your first footprint above.")
