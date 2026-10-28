"""
Biomedical Product Profiles & Arrhenius Kinetic Parameters
Documented WHO, FDA, and peer-reviewed pharmaceutical stability benchmarks.
"""

VACCINE_DATABASE = {
    "Hepatitis B Vaccine (Recombinant)": {
        "category": "Adsorbed Liquid Protein Vaccine (Alum Adjuvant)",
        "safe_min_c": 2.0,
        "safe_max_c": 8.0,
        "freeze_sensitive": True,  # Irreversible aluminum adjuvant agglomeration below 0°C
        "activation_energy_j": 85000.0,  # Ea = 85.0 kJ/mol (WHO PQS reference)
        "reference_temp_k": 277.15,      # 4.0 °C
        "baseline_shelf_life_months": 36.0,
        "max_allowable_equiv_hours": 72.0, # Equivalent hours budget under accelerated thermal stress
        "description": "Widely used liquid vaccine. Highly vulnerable to freezing (<0°C) which destroys potency permanently (fails WHO Shake Test). Stable at 4°C for 3 years, but degrades rapidly at ambient tropical temperatures."
    },
    "mRNA-1273 (COVID-19 Lipid Nanoparticle)": {
        "category": "mRNA-Lipid Nanoparticle Suspension",
        "safe_min_c": 2.0,
        "safe_max_c": 8.0,
        "freeze_sensitive": False, # Tolerates freeze, but fragile when thawed
        "activation_energy_j": 115000.0, # Ea = 115.0 kJ/mol (High thermal fragility)
        "reference_temp_k": 277.15,      # 4.0 °C
        "baseline_shelf_life_months": 1.0, # Thawed shelf-life: 30 days at 2-8°C
        "max_allowable_equiv_hours": 12.0, # Very tight excursion budget
        "description": "Extremely heat-sensitive nucleic acid vaccine. Above 8°C, rapid mRNA phosphodiester backbone hydrolysis occurs. Requires strict real-time kinetic tracking."
    },
    "Human Regular Insulin": {
        "category": "Therapeutic Peptide Hormone",
        "safe_min_c": 2.0,
        "safe_max_c": 8.0,
        "freeze_sensitive": True,  # Freezing causes crystal formation & fibrillar aggregation
        "activation_energy_j": 78500.0,  # Ea = 78.5 kJ/mol
        "reference_temp_k": 277.15,      # 4.0 °C
        "baseline_shelf_life_months": 24.0,
        "max_allowable_equiv_hours": 96.0,
        "description": "Essential peptide hormone. Highly sensitive to both heat (>30°C causes covalent dimerization) and freezing (<0°C causes loss of biological activity)."
    },
    "Measles / OPV (Live Attenuated Vaccine)": {
        "category": "Live Attenuated Viral Vaccine (WHO VVM Category 30)",
        "safe_min_c": 2.0,
        "safe_max_c": 8.0,
        "freeze_sensitive": False, # Can be stored frozen, highly heat-sensitive
        "activation_energy_j": 125000.0, # Ea = 125.0 kJ/mol (Extreme heat lability)
        "reference_temp_k": 277.15,      # 4.0 °C
        "baseline_shelf_life_months": 24.0,
        "max_allowable_equiv_hours": 24.0,
        "description": "Live attenuated viral vaccine with high temperature sensitivity. Thermal degradation causes irreversible viral envelope breakdown."
    }
}

# Aliases for frontend dropdown UI compatibility
VACCINE_DATABASE["Freeze-vulnerable liquid protein (Hepatitis B)"] = VACCINE_DATABASE["Hepatitis B Vaccine (Recombinant)"]
VACCINE_DATABASE["Ultra-fragile nucleic acid (mRNA)"] = VACCINE_DATABASE["mRNA-1273 (COVID-19 Lipid Nanoparticle)"]
VACCINE_DATABASE["Daily life-saving peptide hormone (Insulin)"] = VACCINE_DATABASE["Human Regular Insulin"]
VACCINE_DATABASE["Heat-labile live virus (Measles / Polio)"] = VACCINE_DATABASE["Measles / OPV (Live Attenuated Vaccine)"]


def get_vaccine_profile(vaccine_name):
    """Robust lookup supporting canonical names, UI labels, and keywords."""
    if not vaccine_name:
        return VACCINE_DATABASE["Hepatitis B Vaccine (Recombinant)"]
    if vaccine_name in VACCINE_DATABASE:
        return VACCINE_DATABASE[vaccine_name]
    
    val_lower = str(vaccine_name).lower()
    if "mrna" in val_lower or "nucleic" in val_lower:
        return VACCINE_DATABASE["mRNA-1273 (COVID-19 Lipid Nanoparticle)"]
    elif "insulin" in val_lower or "peptide" in val_lower:
        return VACCINE_DATABASE["Human Regular Insulin"]
    elif "measles" in val_lower or "polio" in val_lower or "opv" in val_lower or "virus" in val_lower:
        return VACCINE_DATABASE["Measles / OPV (Live Attenuated Vaccine)"]
    elif "hepatitis" in val_lower or "protein" in val_lower or "alum" in val_lower:
        return VACCINE_DATABASE["Hepatitis B Vaccine (Recombinant)"]
        
    return VACCINE_DATABASE["Hepatitis B Vaccine (Recombinant)"]


def calculate_arrhenius_factor(temp_c, vaccine_name):
    """Calculates relative acceleration factor Q(T) for a specific vaccine."""
    import math
    profile = get_vaccine_profile(vaccine_name)
    
    if temp_c <= -20.0:
        return 0.01
    
    temp_k = temp_c + 273.15
    r_gas = 8.314  # J/(mol*K)
    ea = profile["activation_energy_j"]
    t_ref_k = profile["reference_temp_k"]
    
    exponent = (ea / r_gas) * ((1.0 / t_ref_k) - (1.0 / temp_k))
    return math.exp(exponent)
