"""
carbon_calculator.py

Core logic for converting electricity consumption (in units/kWh)
into an estimated carbon emission, an eco-score, and a
recommendation. No dataset or ML model required -- this is a
straightforward formula + rule-based lookup, matching the
"Carbon Calculation Engine" described in the project report.
"""

# Average grid emission factor (kg CO2 per kWh).
# India's national grid average is commonly cited around 0.82 kg CO2/kWh.
# Change this if you have a more specific/regional value to cite in your report.
EMISSION_FACTOR_KG_PER_KWH = 0.82


def calculate_emission(units_consumed: float, emission_factor: float = EMISSION_FACTOR_KG_PER_KWH) -> float:
    """
    Convert electricity units consumed (kWh) into kg of CO2 emitted.

    Formula: carbon_emission = units_consumed * emission_factor
    """
    if units_consumed < 0:
        raise ValueError("units_consumed cannot be negative")
    return round(units_consumed * emission_factor, 2)


def calculate_eco_score(units_consumed: float) -> int:
    """
    Very simple rule-based eco-score (0-100, higher = better/greener).
    Thresholds are illustrative -- tune them to match typical household
    usage in your target region.
    """
    if units_consumed <= 100:
        return 90
    elif units_consumed <= 200:
        return 75
    elif units_consumed <= 300:
        return 60
    elif units_consumed <= 400:
        return 45
    else:
        return 30


def generate_recommendation(units_consumed: float) -> str:
    """
    Rule-based recommendation engine (no ML needed for this simple version).
    """
    if units_consumed <= 100:
        return "Great job! Your electricity usage is already low. Keep it up."
    elif units_consumed <= 250:
        return "Reduce electricity consumption during peak hours to save more."
    elif units_consumed <= 400:
        return "Consider switching to energy-efficient (5-star rated) appliances."
    else:
        return "Your usage is high -- audit high-consumption appliances like ACs and geysers."


def build_result(units_consumed: float) -> dict:
    """
    Convenience wrapper that returns the full output payload,
    matching the API example shape from the project report:
    {
        "electricityUnits": 120,
        "carbonEmission": "45 kg CO2",
        "ecoScore": 78,
        "recommendation": "..."
    }
    """
    emission = calculate_emission(units_consumed)
    return {
        "electricityUnits": units_consumed,
        "carbonEmission": f"{emission} kg CO2",
        "ecoScore": calculate_eco_score(units_consumed),
        "recommendation": generate_recommendation(units_consumed),
    }


if __name__ == "__main__":
    # Quick manual test: python carbon_calculator.py
    sample = build_result(120)
    print(sample)
