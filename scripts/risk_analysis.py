import pandas as pd
from sklearn.preprocessing import MinMaxScaler #Going with MixMax here so that we can calculate risk (bound 0-1 for simplicity) and all corresponding features to a specified range (default is [0, 1]).
#X_std (intermediate standardized value)= (X - X.min()) / (X.max() - X.min())
#X_scaled = X_std * (max - min) + min
 
 
#WEIGHING_COST = 14  # $14 per weighing
 
def calculate_risk_ratings(input_file):
    # Read the Excel file
    df = pd.read_excel(input_file)
   
    # Clean and prepare data
    df['Total Expense'] = df['Total Expense'].fillna(0)
    df['Total Incurred'] = df['Total Incurred'].fillna(0)
    #df['total_penalties'] = df['Total Expense'] + f['Total Incurred'] - They are the same. Causing count to double
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
       
        # Include avg_loss_location_risk for routes
        if group_cols == ['Ship From City', 'Ship From State', 'Ship To City', 'Ship To State']:
            agg_dict['avg_loss_location_risk'] = ('risk_score', 'mean')
       
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
       
        # Calculate combined risk score
        if group_cols == ['Ship From City', 'Ship From State', 'Ship To City', 'Ship To State']:
            # Include avg_loss_location_risk which is already 0-1
            # Equal weights to incidents, penalties, and loss location risk (33%) if loss location else equal weighted avg
            grouped['risk_score'] = (grouped['count_norm'] + grouped['penalties_norm'] + grouped['avg_loss_location_risk']) / 3
        else:
            grouped['risk_score'] = (grouped['count_norm'] + grouped['penalties_norm']) / 2
       
        # Assign risk ratings
        #Threshold Logic:
        # High Risk (≥0.7): Mandatory weighing - expected fines    
        # Medium Risk (≥0.4): Recommended weighing - potential fines justify cost
        # Low Risk (<0.4): Optional weighing - savings outweigh risk
        def get_rating(score):
            if score >= 0.7:
                return 'High'
            elif score >= 0.4:
                return 'Medium'
            else:
                return 'Low'
       
        grouped['risk_rating'] = grouped['risk_score'].apply(get_rating)
        return grouped.sort_values('risk_score', ascending=False)
   
   
   
    # Process loss locations first to get their risk scores
    loss_location_cols = ['Loss City', 'Loss State']
    loss_location_risk = process_group('Loss Locations', loss_location_cols)
   
    if not loss_location_risk.empty:
        # Merge loss location risk scores back into filtered_df
        filtered_df = filtered_df.merge(
            loss_location_risk[loss_location_cols + ['risk_score']],
            on=loss_location_cols,
            how='left'
        )
        filtered_df['risk_score'] = filtered_df['risk_score'].fillna(0)
    else:
        filtered_df['risk_score'] = 0
   
    # Process routes
    route_cols = ['Ship From City', 'Ship From State', 'Ship To City', 'Ship To State']
    route_risk = process_group('Routes', route_cols)
   
    # Process liable parties
    liable_cols = ['Liable Party Name']
    liable_risk = process_group('Liable Parties', liable_cols)
   
    # Save results to Excel
    with pd.ExcelWriter('risk_ratings_2.xlsx') as writer:
        if not route_risk.empty:
            route_risk.to_excel(writer, sheet_name='Route Risk Ratings', index=False)
        if not liable_risk.empty:
            liable_risk.to_excel(writer, sheet_name='Liable Party Risk Ratings', index=False)
        if not loss_location_risk.empty:
            loss_location_risk.to_excel(writer, sheet_name='Loss Location Risk Ratings', index=False)
   
    print("Risk ratings generated successfully in 'risk_ratings.xlsx'")
 
calculate_risk_ratings('Cargo_claims_data.xlsx')