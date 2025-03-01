import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from risk_utils import calculate_route_risk, calculate_liable_party_risk, get_risk_recommendation
import os
from datetime import datetime
from isochrone_utils import get_isochrone, find_scales_in_isochrone

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
    """Calculate detour costs, returning both total cost and driver time cost separately"""
    # Debug coordinate inputs
    print("\nCoordinate Validation:")
    print(f"Ship from: {ship_from_coords}")
    print(f"Ship to: {ship_to_coords}")
    print(f"Scale: {cat_scale_coords}")
    
    # Calculate distances with explicit coordinate order (lat, lon)
    direct_route = geodesic(ship_from_coords, ship_to_coords).miles
    to_scale = geodesic(ship_from_coords, cat_scale_coords).miles
    from_scale = geodesic(cat_scale_coords, ship_to_coords).miles
    
    # Calculate total route with scale
    route_with_scale = to_scale + from_scale
    detour_distance = route_with_scale - direct_route
    detour_time = detour_distance / AVERAGE_SPEED_MPH
    driver_time_cost = detour_time * DRIVER_COST_PER_HOUR
    total_detour_cost = driver_time_cost + CAT_SCALE_COST
    
    # Detailed debug output
    print(f"\nCost Breakdown:")
    print(f"Driver time cost (${DRIVER_COST_PER_HOUR}/hr * {detour_time:.2f}hr): ${driver_time_cost:.2f}")
    print(f"Scale fee: ${CAT_SCALE_COST:.2f}")
    print(f"Total cost: ${total_detour_cost:.2f}")
    
    return total_detour_cost, detour_distance, driver_time_cost

def calculate_path_deviation(point_coords, from_coords, to_coords):
    """Calculate how far a point deviates from the direct route path"""
    route_distance = geodesic(from_coords, to_coords).miles
    via_point_distance = geodesic(from_coords, point_coords).miles + geodesic(point_coords, to_coords).miles
    return (via_point_distance - route_distance) / route_distance  # Returns percentage deviation

def find_best_cat_scale(ship_from_coords, ship_to_coords, route_risk=0.0):
    """Find the optimal cat scale location considering route corridor"""
    total_distance = geodesic(ship_from_coords, ship_to_coords).miles
    max_deviation = 0.15  # Allow 15% path deviation
    
    # For longer routes, be more lenient with deviation
    if total_distance > 500:
        max_deviation = 0.20
    elif total_distance > 1000:
        max_deviation = 0.25
    
    # Find all scales within reasonable deviation from route
    viable_scales = []
    for _, scale in cat_scales.iterrows():
        scale_coords = (scale['Latitude'], scale['Longitude'])
        deviation = calculate_path_deviation(scale_coords, ship_from_coords, ship_to_coords)
        
        if deviation <= max_deviation:
            detour_cost, extra_distance, driver_time_cost = calculate_detour_cost(
                ship_from_coords, ship_to_coords, scale_coords
            )
            viable_scales.append({
                'scale': scale,
                'deviation': deviation,
                'detour_cost': detour_cost,
                'distance': extra_distance,
                'from_origin': geodesic(ship_from_coords, scale_coords).miles
            })
    
    if not viable_scales:
        return "No suitable scale found", float('inf'), None, None
    
    # Sort scales by a combination of factors
    for scale in viable_scales:
        # Calculate score (lower is better)
        scale['score'] = (
            scale['deviation'] * 100 +  # Path deviation
            scale['detour_cost'] / 50 +  # Cost factor
            (0 if route_risk >= 0.7 and scale['from_origin'] <= 100 else scale['from_origin'] / 100)  # Origin proximity for high risk
        )
    
    # Get best scale based on combined score
    best_scale = min(viable_scales, key=lambda x: x['score'])
    scale_data = best_scale['scale']
    
    # Calculate final costs for best scale
    final_detour_cost, _, final_driver_time_cost = calculate_detour_cost(
        ship_from_coords, ship_to_coords,
        (scale_data['Latitude'], scale_data['Longitude'])
    )
    
    return (
        f"{scale_data['TruckstopName']} - {scale_data['InterstateCity']}, {scale_data['State']} (#{scale_data['CATScaleNumber']})",
        final_detour_cost,
        (scale_data['Latitude'], scale_data['Longitude']),
        final_driver_time_cost
    )

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
            best_scale, detour_cost, scale_coords, driver_time_cost = find_best_cat_scale(
                ship_from_coords, ship_to_coords, route_risk
            )
            
            # Get recommendation
            should_scale, confidence, reasoning = get_risk_recommendation(
                route_risk, liable_risk, detour_cost
            )
            
            # Display results with more detail
            st.write(f"**Route Risk Rating:** {route_rating} ({route_risk:.2f})")
            st.write(f"**Liable Party Risk Rating:** {liable_rating} ({liable_risk:.2f})")
            st.write(f"**Scale Details:**")
            
            # After finding best scale, add historical comparison
            if should_scale:
                # Find historical loss location for this route
                historical_data = incident_data[
                    (incident_data['Ship From City'].str.upper() == ship_from_city.upper()) &
                    (incident_data['Ship From State'].str.upper() == ship_from_state.upper()) &
                    (incident_data['Ship To City'].str.upper() == ship_to_city.upper()) &
                    (incident_data['Ship To State'].str.upper() == ship_to_state.upper())
                ]
                
                if not historical_data.empty:
                    # Get Loss City coordinates
                    loss_city = historical_data.iloc[0]['Loss City']
                    loss_state = historical_data.iloc[0]['Loss State']
                    loss_loc = f"{loss_city}, {loss_state}"
                    loss_coords = get_coordinates(loss_loc)
                    
                    if loss_coords:
                        # Calculate historical detour cost
                        historical_detour_cost, historical_distance, historical_driver_cost = calculate_detour_cost(
                            ship_from_coords, ship_to_coords, loss_coords
                        )
                        
                        # Compare locations
                        scale_data = cat_scales[
                            (cat_scales['State'] == loss_state) &
                            (cat_scales['InterstateCity'] == loss_city)
                        ]
                        
                        st.write("\n**Historical Comparison:**")
                        st.write(f"- Historical scale location: {loss_city}, {loss_state}")
                        st.write(f"- Historical detour cost breakdown:")
                        st.write(f"  - Driver time: ${historical_driver_cost:.2f}")
                        st.write(f"  - Scale fee: ${CAT_SCALE_COST:.2f}")
                        st.write(f"  - Total cost: ${historical_detour_cost:.2f}")
                        
                        if scale_data.empty:
                            st.write("Note: Historical location is not a registered CAT scale")
                        
                        savings = historical_detour_cost - detour_cost
                        if savings > 0:
                            st.success(f"Potential savings using recommended scale: ${savings:.2f}")
                        else:
                            st.warning(f"Historical route was more efficient by: ${-savings:.2f}")
                        
                # Continue with existing display code...
                direct_route = geodesic(ship_from_coords, ship_to_coords).miles
                to_scale = geodesic(ship_from_coords, scale_coords).miles
                st.write(f"- Direct route: {direct_route:.1f} miles")
                st.write(f"- Distance to scale: {to_scale:.1f} miles")
                st.write(f"- Additional cost breakdown:")
                st.write(f"  - Driver time: ${driver_time_cost:.2f}")  # Use actual driver time cost
                st.write(f"  - Scale fee: ${CAT_SCALE_COST:.2f}")
                st.write(f"  - **Total detour cost:** ${detour_cost:.2f}")
                
                st.success(f"Recommendation: **Stop at cat scale '{best_scale}'**\n"
                          f"Confidence: {confidence}\n"
                          f"Reason: {reasoning}")
            else:
                st.info(f"Recommendation: **Skip scaling**\nConfidence: {confidence}\nReason: {reasoning}")
