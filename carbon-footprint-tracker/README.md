# Carbon Footprint Tracker -- Electricity Bill Module

Part of the "AI-Powered Carbon Footprint Tracking & Reduction System" project.
This module covers the electricity bill input -> output pipeline:

```
Electricity Bill (image or manual entry)
        -> OCR Extraction (units consumed)
        -> Carbon Emission Calculation
        -> Output: emission (kg CO2), eco-score, recommendation
        -> Saved to database, shown on dashboard
```

## Project Structure

```
carbon-footprint-tracker/
├── app.py                  # Streamlit app (main entry point)
├── ocr_parser.py            # OCR + regex extraction from bill images
├── carbon_calculator.py     # Emission / eco-score / recommendation logic
├── data/
│   └── sample_bills/        # Sample electricity bill images for testing OCR
├── database.py               # SQLite setup and queries
├── requirements.txt
└── README.md
```

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install the Tesseract OCR engine (separate from the Python package):
   - **Windows:** https://github.com/UB-Mannheim/tesseract/wiki
   - **macOS:** `brew install tesseract`
   - **Linux:** `sudo apt install tesseract-ocr`

   (If you skip this, the app still works using manual entry -- OCR upload
   is automatically disabled.)

## Running the app

```bash
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

## Testing individual pieces

```bash
python carbon_calculator.py                          # test emission formula
python ocr_parser.py data/sample_bills/bill1.jpg      # test OCR on a sample bill
python database.py                                    # test database save/read
```

## Notes

- The default emission factor (0.82 kg CO2/kWh) is a general grid average --
  update `EMISSION_FACTOR_KG_PER_KWH` in `carbon_calculator.py` if your
  report cites a different regional figure.
- OCR regex patterns in `ocr_parser.py` are a starting point. Real bills
  vary by provider, so test against your own sample bills in
  `data/sample_bills/` and extend the patterns as needed.
- The ML-based prediction module mentioned in the project report is a
  separate future enhancement, not included here -- this covers the
  working input -> output pipeline for electricity bill scanning only.
