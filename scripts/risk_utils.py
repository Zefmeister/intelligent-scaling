import pandas as pd
from sklearn.preprocessing import MinMaxScaler

def calculate_route_risk(ship_from_city, ship_from_state, ship_to_city, ship_to_state, risk_ratings_df):
    """Get risk score for a specific route"""
    route_mask = (
        (risk_ratings_df['Ship From City'].str.upper() == ship_from_city.upper()) &
        (risk_ratings_df['Ship From State'].str.upper() == ship_from_state.upper()) &
        (risk_ratings_df['Ship To City'].str.upper() == ship_to_city.upper()) &
        (risk_ratings_df['Ship To State'].str.upper() == ship_to_state.upper())
    )
    route_data = risk_ratings_df[route_mask]
    
    print("\n=== Route Risk Analysis ===")
    print(f"Searching for route: {ship_from_city}, {ship_from_state} to {ship_to_city}, {ship_to_state}")
    print(f"Route data found: {len(route_data)} records")
    if not route_data.empty:
        risk_details = route_data.iloc[0].to_dict()
        print("\nRisk Score Components:")
        print(f"Incident Count: {risk_details.get('incident_count', 0)}")
        print(f"Total Penalties: ${risk_details.get('total_penalties', 0):,.2f}")
        print(f"Normalized Count: {risk_details.get('count_norm', 0):.3f}")
        print(f"Normalized Penalties: {risk_details.get('penalties_norm', 0):.3f}")
        print(f"Final Risk Score: {risk_details.get('risk_score', 0):.3f}")
        return risk_details.get('risk_score', 0), risk_details.get('risk_rating', 'Low')
    return 0.0, 'Low'

def calculate_liable_party_risk(liable_party, risk_ratings_df):
    """Get risk score for a liable party"""
    party_mask = risk_ratings_df['Liable Party Name'] == liable_party
    party_data = risk_ratings_df[party_mask]
    print(f"Liable party data found: {len(party_data)} records")
    print(f"Liable party risk calculation details: {party_data[['incident_count', 'total_penalties', 'risk_score']].to_dict('records')}")
    if not party_data.empty:
        return party_data.iloc[0]['risk_score'], party_data.iloc[0]['risk_rating']
    return 0.0, 'Low'

def get_risk_recommendation(route_risk_score, liable_party_risk_score, detour_cost):
    """
    Provide recommendation based on combined risk factors
    Returns: (should_scale, confidence, reasoning)
    """
    combined_risk = (route_risk_score + liable_party_risk_score) / 2
    
    if combined_risk >= 0.7:
        return True, "High", "High risk route and/or liable party history"
    elif combined_risk >= 0.4:
        if detour_cost < 100:  # Adjustable threshold
            return True, "Medium", "Medium risk with reasonable detour cost"
        else:
            return False, "Medium", "Medium risk but high detour cost"
    else:
        return False, "Low", "Low risk route and liable party history"
