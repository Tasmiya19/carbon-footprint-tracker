"""
export_for_powerbi.py

Exports the current ActivityData history (from carbon_tracker.db) into
a CSV file that Power BI can read directly. Run this any time you want
to refresh the data Power BI is working with -- just re-run the script,
then click "Refresh" in Power BI.

Usage:
    python export_for_powerbi.py
"""

import pandas as pd
from database import get_all_records

records = get_all_records()

if not records:
    print("No records found in the database yet. Log a few entries in the app first.")
else:
    df = pd.DataFrame(
        records,
        columns=["ID", "User", "Units_kWh", "Emission_kgCO2", "EcoScore", "Recommendation", "Date"],
    )
    df.to_csv("carbon_data.csv", index=False)
    print(f"Exported {len(df)} records to carbon_data.csv")
