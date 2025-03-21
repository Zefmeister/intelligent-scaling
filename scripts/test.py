from opencage.geocoder import OpenCageGeocode

# Replace with your OpenCage API key
key = 'd47f8c2e5d2b457f9128b8b583f80dd4'
geocoder = OpenCageGeocode(key)

# Define the query
query = "Heartland Express - Poplar Bluff, MO #1018"
query2= "4155 S Westwood Blvd, Poplar Bluff, MO"

# Geocode the query
result = geocoder.geocode(query)
print(result)
print("############################################")
result2 = geocoder.geocode(query2)
#print(result2)
if result:
    # Print the full address for result
    print(f"Address: {result[0]['formatted']}")
    print(f"Latitude: {result[0]['geometry']['lat']}")
    print(f"Longitude: {result[0]['geometry']['lng']}")
    # Print the full address for result2
    print("############################################")
    print(f"Address: {result2[0]['formatted']}")
    print(f"Latitude: {result2[0]['geometry']['lat']}")
    print(f"Longitude: {result2[0]['geometry']['lng']}")
else:
    print("Location not found.")
