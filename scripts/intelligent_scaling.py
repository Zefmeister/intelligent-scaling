import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from risk_utils import calculate_route_risk, calculate_liable_party_risk, get_risk_recommendation
import os
from datetime import datetime

# --- Constants & Configurations ---
CAT_SCALE_COST = 14.0              # Fixed cost for weighing at a cat scale
DRIVER_COST_PER_HOUR = 17.0          # Example driver pay rate per hour
VIOLATION_COST = 500.0               # Base cost of an overweight violation
OUT_OF_RANGE_MILE_COST = 2.0         # Cost per extra mile off the main route
AVERAGE_SPEED_MPH = 50.0             # Assumed average speed in mph

# --- Load Cat Scale Data ---
try:
    # Specify the required columns when reading the file
    cat_scales = pd.read_excel("data/cat_scales.xlsx", usecols=[
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
    incident_data = pd.read_excel("data/Cargo_claims_data.xlsx")
except Exception as e:
    st.error(f"Error loading cargo claims file: {e}")
    incident_data = pd.DataFrame(columns=["Loss City/State", "Ship From", "Ship To", "Liable Party Name", "Total Expense", "Weight"])

# --- Load Risk Ratings Data ---
def get_latest_risk_ratings():
    try:
        # Try to read pointer file
        with open('data/latest_risk_ratings.txt', 'r') as f:
            latest_file = f.read().strip()
        
        if os.path.exists(latest_file):
            return pd.read_excel(latest_file, sheet_name=['Route Risk Ratings', 'Liable Party Risk Ratings'])
        else:
            # Fall back to finding most recent file
            risk_files = [f for f in os.listdir('data') if f.startswith('risk_ratings_')]
            if risk_files:
                latest_file = max(risk_files)
                return pd.read_excel(f"data/{latest_file}", sheet_name=['Route Risk Ratings', 'Liable Party Risk Ratings'])
    except Exception as e:
        st.error(f"Error loading risk ratings: {e}")
    
    return {
        'Route Risk Ratings': pd.DataFrame(),
        'Liable Party Risk Ratings': pd.DataFrame()
    }

risk_ratings = get_latest_risk_ratings()

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

def find_best_cat_scale(ship_from_coords, ship_to_coords, route_risk=0.0):
    """
    Find the optimal cat scale location considering:
    1. For high-risk routes, strongly prefer scales closer to origin
    2. For lower risk routes, minimize total detour cost
    """
    best_scale = None
    best_cost = float('inf')
    best_early_scale = None
    best_early_cost = float('inf')
    
    # For high risk routes, only look at scales within 50 miles of origin
    high_risk_radius = 50 if route_risk >= 0.7 else float('inf')
    
    for idx, row in cat_scales.iterrows():
        cat_scale_coords = (row['Latitude'], row['Longitude'])
        distance_from_origin = geodesic(ship_from_coords, cat_scale_coords).miles
        
        # For high risk routes, only consider nearby scales
        if route_risk >= 0.7 and distance_from_origin > high_risk_radius:
            continue
            
        detour_cost, extra_distance = calculate_detour_cost(ship_from_coords, ship_to_coords, cat_scale_coords)
        
        # For nearby scales, prioritize based on distance from origin
        if distance_from_origin <= high_risk_radius:
            # Adjust cost to favor closer scales
            adjusted_cost = detour_cost * (1 + distance_from_origin/high_risk_radius)
            if adjusted_cost < best_early_cost:
                best_early_cost = adjusted_cost
                best_early_scale = {
                    'name': f"{row['TruckstopName']} - {row['InterstateCity']}, {row['State']} (#{row['CATScaleNumber']})",
                    'distance': distance_from_origin,
                    'cost': detour_cost
                }
        
        if detour_cost < best_cost:
            best_cost = detour_cost
            best_scale = {
                'name': f"{row['TruckstopName']} - {row['InterstateCity']}, {row['State']} (#{row['CATScaleNumber']})",
                'distance': distance_from_origin,
                'cost': detour_cost
            }

    # For high-risk routes, always prefer early scales unless significantly more expensive
    if route_risk >= 0.7 and best_early_scale:
        return best_early_scale['name'], best_early_scale['cost']
    
    return best_scale['name'], best_cost

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
        ship_from_city, ship_from_state = ship_from.split(", ")
        ship_to_city, ship_to_state = ship_to.split(", ")
        
        ship_from_coords = get_coordinates(ship_from)
        ship_to_coords = get_coordinates(ship_to)
        
        if ship_from_coords is None or ship_to_coords is None:
            st.error("Could not determine coordinates for one of the provided locations.")
        else:
            # Calculate risk scores
            route_risk, route_rating = calculate_route_risk(
                ship_from_city, ship_from_state, 
                ship_to_city, ship_to_state,
                risk_ratings['Route Risk Ratings']
            )
            
            liable_risk, liable_rating = calculate_liable_party_risk(
                liable_party, 
                risk_ratings['Liable Party Risk Ratings']
            )
            
            # Find the optimal cat scale along the route
            best_scale, detour_cost = find_best_cat_scale(ship_from_coords, ship_to_coords, route_risk)
            
            # Get recommendation
            should_scale, confidence, reasoning = get_risk_recommendation(
                route_risk, liable_risk, detour_cost
            )
            
            # Display results
            st.write(f"**Route Risk Rating:** {route_rating} ({route_risk:.2f})")
            st.write(f"**Liable Party Risk Rating:** {liable_rating} ({liable_risk:.2f})")
            st.write(f"**Detour Cost:** ${detour_cost:.2f}")
            
            if should_scale:
                st.success(f"Recommendation: **Stop at cat scale '{best_scale}'**\n"
                          f"Confidence: {confidence}\n"
                          f"Reason: {reasoning}\n"
                          f"Estimated detour cost: ${detour_cost:.2f}")
            else:
                st.info(f"Recommendation: **Skip scaling**\nConfidence: {confidence}\nReason: {reasoning}")
