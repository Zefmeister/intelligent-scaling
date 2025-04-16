import folium
from folium import plugins
import streamlit as st
from streamlit_folium import folium_static

def create_route_map(ship_from_coords, ship_to_coords, scale_coords=None, isochrone_polygon=None, scales_in_range=None, historical_scale=None):
    """Create an interactive map showing route, scale, and isochrone"""
    # Create map centered between origin and destination
    center_lat = (ship_from_coords[0] + ship_to_coords[0]) / 2
    center_lon = (ship_from_coords[1] + ship_to_coords[1]) / 2
    m = folium.Map(location=[center_lat, center_lon], zoom_start=7)
    
    # Add historical scale location if provided
    if historical_scale:
        historical_coords, loss_city, loss_state = historical_scale
        folium.Marker(
            historical_coords,
            popup=f'Historical Loss Location: {loss_city}, {loss_state}',
            icon=folium.Icon(color='red', icon='warning', prefix='fa')
        ).add_to(m)
    
    # Add origin marker
    folium.Marker(
        ship_from_coords,
        popup='Origin',
        icon=folium.Icon(color='green', icon='play', prefix='fa')
    ).add_to(m)
    
    # Add destination marker
    folium.Marker(
        ship_to_coords,
        popup='Destination',
        icon=folium.Icon(color='red', icon='stop', prefix='fa')
    ).add_to(m)
    
    # Draw direct route line
    folium.PolyLine(
        locations=[ship_from_coords, ship_to_coords],
        color='blue',
        weight=2,
        opacity=0.8
    ).add_to(m)
    
    # Add recommended scale if provided
    if scale_coords:
        folium.Marker(
            scale_coords,
            popup='Recommended Scale',
            icon=folium.Icon(color='orange', icon='scale', prefix='fa')
        ).add_to(m)
        
        # Draw route with scale
        route_with_scale = [
            ship_from_coords,
            scale_coords,
            ship_to_coords
        ]
        folium.PolyLine(
            locations=route_with_scale,
            color='orange',
            weight=2,
            opacity=0.5,
            dashArray='5,10'
        ).add_to(m)
    
    # Add isochrone if provided
    if isochrone_polygon:
        folium.GeoJson(
            isochrone_polygon.__geo_interface__,
            style_function=lambda x: {
                'fillColor': '#00FF00',
                'color': '#00FF00',
                'weight': 1,
                'fillOpacity': 0.2
            }
        ).add_to(m)
    
    # Add other scales in range if provided
    if scales_in_range:
        for scale in scales_in_range:
            folium.CircleMarker(
                location=(scale['Latitude'], scale['Longitude']),
                radius=3,
                popup=f"{scale['TruckstopName']} - {scale['InterstateCity']}",
                color='gray',
                fill=True
            ).add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    return m
