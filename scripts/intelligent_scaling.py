import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# --- Constants & Configurations ---
CAT_SCALE_COST = 14.0              # Fixed cost for weighing at a cat scale
DRIVER_COST_PER_HOUR = 30.0          # Example driver pay rate per hour
VIOLATION_COST = 500.0               # Base cost of an overweight violation
OUT_OF_RANGE_MILE_COST = 2.0         # Cost per extra mile off the main route
AVERAGE_SPEED_MPH = 50.0             # Assumed average speed in mph

# --- Load Cat Scale Data ---
try:
    # Specify the required columns when reading the file
    cat_scales = pd.read_excel("cat_scales.xlsx", usecols=[
        'CATScaleNumber', 'State', 'InterstateCity', 'TruckstopName',
        'InterstateAddress', 'Latitude', 'Longitude'
    ])
except Exception as e:
    st.error(f"Error loading cat scales file: {e}")
    # Create empty DataFrame with correct columns
    cat_scales = pd.DataFrame(columns=[
        'CATScaleNumber', 'State', 'InterstateCity', 'TruckstopName',
        'InterstateAddress', 'Latitude', 'Longitude'
    ])

# --- Load Historical Incident Data ---
try:
    incident_data = pd.read_excel("incident_data.xlsx")
except Exception as e:
    st.error(f"Error loading incident data file: {e}")
    incident_data = pd.DataFrame(columns=["Loss City/State", "Ship From", "Ship To", "Liable Party Name", "Total Expense", "Weight"])

# --- Geocoding Setup ---
geolocator = Nominatim(user_agent="truck_scaling_app")

def get_coordinates(location_str):
    """Get (latitude, longitude) tuple for a given location string."""
    try:
        location = geolocator.geocode(location_str)
        if location:
            return (location.latitude, location.longitude)
        else:
            return None
    except Exception as e:
        st.error(f"Error geocoding '{location_str}': {e}")
        return None

def calculate_detour_cost(ship_from_coords, ship_to_coords, cat_scale_coords):
    """
    Calculate the additional cost incurred by detouring to a cat scale.
    The extra miles are computed as:
        (distance from ship_from to cat scale) + (distance from cat scale to ship_to)
        MINUS the direct ship_from to ship_to distance.
    """
    base_distance = geodesic(ship_from_coords, ship_to_coords).miles
    distance_to_scale = geodesic(ship_from_coords, cat_scale_coords).miles
    distance_from_scale = geodesic(cat_scale_coords, ship_to_coords).miles
    detour_distance = distance_to_scale + distance_from_scale - base_distance

    # Estimate extra time in hours (using average speed)
    extra_time = detour_distance / AVERAGE_SPEED_MPH

    # Compute cost: driver time cost + extra miles cost + cat scale fee
    detour_cost = (extra_time * DRIVER_COST_PER_HOUR) + (detour_distance * OUT_OF_RANGE_MILE_COST) + CAT_SCALE_COST
    return detour_cost, detour_distance

def find_best_cat_scale(ship_from_coords, ship_to_coords):
    """
    Iterate over all cat scale locations and find the one with the minimum detour cost.
    Returns the best scale's location name and the corresponding detour cost.
    """
    best_scale = None
    best_cost = float('inf')
    for idx, row in cat_scales.iterrows():
        cat_scale_coords = (row['Latitude'], row['Longitude'])
        detour_cost, extra_distance = calculate_detour_cost(ship_from_coords, ship_to_coords, cat_scale_coords)
        if detour_cost < best_cost:
            best_cost = detour_cost
            # Create a location string from the available fields
            best_scale = f"{row['TruckstopName']} - {row['InterstateCity']}, {row['State']} (#{row['CATScaleNumber']})"
    return best_scale, best_cost

def compute_historical_risk_premium(liable_party):
    """
    Calculate an average expense from historical incidents for the given liable party.
    This average expense is used as an additional risk premium.
    """
    party_incidents = incident_data[incident_data["Liable Party Name"].str.lower() == liable_party.lower()]
    if not party_incidents.empty:
        avg_expense = party_incidents["Total Expense"].mean()
        return avg_expense, len(party_incidents)
    return 0.0, 0

# --- Streamlit UI ---
st.title("Truck Scaling Risk Analysis")

st.markdown("""
This tool helps you decide whether to stop at a cat scale for weighing your truck.
Enter your **Ship From**, **Ship To**, and **Liable Party Name** below.
""")

ship_from = st.text_input("Enter Ship From (City, State):")
ship_to = st.text_input("Enter Ship To (City, State):")
liable_party = st.text_input("Enter Liable Party Name:")

if st.button("Analyze Risk"):
    if not ship_from or not ship_to or not liable_party:
        st.error("Please enter all required fields.")
    else:
        ship_from_coords = get_coordinates(ship_from)
        ship_to_coords = get_coordinates(ship_to)
        if ship_from_coords is None or ship_to_coords is None:
            st.error("Could not determine coordinates for one of the provided locations.")
        else:
            # Find the optimal cat scale along the route.
            best_scale, detour_cost = find_best_cat_scale(ship_from_coords, ship_to_coords)
            
            # Compute historical risk premium from incident data for the liable party.
            risk_premium, incident_count = compute_historical_risk_premium(liable_party)
            
            # Compute the overall risk cost: violation cost plus the historical risk premium.
            risk_cost = VIOLATION_COST + risk_premium
            
            st.write(f"**Calculated Detour Cost:** ${detour_cost:.2f}")
            st.write(f"**Risk Cost (Violation Cost + Historical Avg Expense):** ${risk_cost:.2f}")
            if incident_count > 0:
                st.info(f"Found {incident_count} historical incident(s) for '{liable_party}' with an average expense of ${risk_premium:.2f}.")
            else:
                st.info(f"No historical incident data found for '{liable_party}'.")
            
            # Decision logic: Recommend scaling if detour cost is lower than the risk cost.
            if detour_cost < risk_cost:
                st.success(f"Recommendation: **Stop at cat scale '{best_scale}'**. This detour cost is lower than the expected risk cost.")
            else:
                st.info("Recommendation: **Skip scaling.** The detour cost is higher than the potential risk cost.")
