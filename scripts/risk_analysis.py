import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime
import os

def calculate_risk_ratings(input_file):
    # Read the Excel file
    df = pd.read_excel(input_file)
   
    # Clean and prepare data
    df['Total Expense'] = df['Total Expense'].fillna(0)
    df['Total Incurred'] = df['Total Incurred'].fillna(0)
    df['total_penalties'] = df['Total Expense'].fillna(0)
   
    # Filter relevant records
    mask = (
        (df['Primary Incident Cause Desc'] == 'overweight') |
        (df['Total Expense'] > 0) |
        (df['Total Incurred'] > 0)
    )
    filtered_df = df[mask]
   
    def process_group(group_by, group_cols):
        # Group and aggregate data
        agg_dict = {
            'incident_count': ('Primary Incident Cause Desc', 'size'),
            'total_penalties': ('total_penalties', 'sum'),
            'avg_gross_weight': ('Gross Weight', 'mean')
        }
       
        grouped = filtered_df.groupby(group_cols).agg(**agg_dict).reset_index()
       
        if len(grouped) == 0:
            return pd.DataFrame()
       
        # Normalize metrics
        scaler = MinMaxScaler()
        metrics = grouped[['incident_count', 'total_penalties']]
        if not metrics.empty:
            grouped[['count_norm', 'penalties_norm']] = scaler.fit_transform(metrics)
        else:
            grouped[['count_norm', 'penalties_norm']] = 0
       
        # Calculate combined risk score (equal weights for incidents and penalties)
        grouped['risk_score'] = (grouped['count_norm'] + grouped['penalties_norm']) / 2
       
        # Assign risk ratings
        grouped['risk_rating'] = grouped['risk_score'].apply(get_rating)
        return grouped.sort_values('risk_score', ascending=False)
   
    # Process routes and liable parties
    route_cols = ['Ship From City', 'Ship From State', 'Ship To City', 'Ship To State']
    route_risk = process_group('Routes', route_cols)
   
    liable_cols = ['Liable Party Name']
    liable_risk = process_group('Liable Parties', liable_cols)
   
    # Save results to Excel
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'data/risk_ratings_{timestamp}.xlsx'
    
    with pd.ExcelWriter(output_file) as writer:
        if not route_risk.empty:
            route_risk.to_excel(writer, sheet_name='Route Risk Ratings', index=False)
        if not liable_risk.empty:
            liable_risk.to_excel(writer, sheet_name='Liable Party Risk Ratings', index=False)
   
    print(f"Risk ratings generated successfully in '{output_file}'")
    
    # Create/update pointer file to latest ratings
    with open('data/latest_risk_ratings.txt', 'w') as f:
        f.write(output_file)

def get_rating(score):
    if score >= 0.7:
        return 'High'
    elif score >= 0.4:
        return 'Medium'
    else:
        return 'Low'

calculate_risk_ratings('data/Cargo_claims_data.xlsx')