import openrouteservice as ors
from shapely.geometry import Point, shape
import os
from dotenv import load_dotenv

load_dotenv()

# Get API key from environment variable
ORS_API_KEY = os.getenv('ORS_API_KEY')
client = ors.Client(key=ORS_API_KEY)

def get_isochrone(coords, drive_time_minutes=30):
    """Get isochrone polygon for given coordinates and drive time"""
    try:
        # Convert drive time to seconds
        drive_time_seconds = drive_time_minutes * 60
        
        # Request isochrone from OpenRouteService
        isochrones = client.isochrones(
            locations=[coords[::-1]],  # ORS expects [lon, lat]
            profile='driving-hgv',     # Use HGV profile for trucks
            range=[drive_time_seconds],
            attributes=['area', 'reachfactor']
        )
        
        # Convert to Shapely polygon for easy point-in-polygon testing
        return shape(isochrones['features'][0]['geometry'])
    except Exception as e:
        print(f"Error getting isochrone: {e}")
        return None

def find_scales_in_isochrone(polygon, cat_scales_df):
    """Find all CAT scales within the isochrone polygon"""
    if polygon is None:
        return []
    
    scales_in_range = []
    for _, scale in cat_scales_df.iterrows():
        point = Point(scale['Longitude'], scale['Latitude'])
        if polygon.contains(point):
            scales_in_range.append(scale)
    
    return scales_in_range
