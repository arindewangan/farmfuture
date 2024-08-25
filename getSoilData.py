import requests
import json

def query_soil_data(lon, lat):
    base_url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    params = {
        "lon": lon,
        "lat": lat,
        "property": ["clay", "sand", "silt", "phh2o", "nitrogen"],
        "depth": "0-30cm",
        "value": ["mean"]
    }
    
    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: API returned status code {response.status_code}")
        return None

def determine_soil_type(clay, sand, silt):
    if any(v is None for v in [clay, sand, silt]):
        return "Unknown"
    if sand >= 70:
        return "Sandy"
    elif clay >= 40:
        return "Clay"
    elif silt >= 80:
        return "Silty"
    elif sand >= 52 and clay < 20:
        return "Sandy Loam"
    elif clay >= 28 and sand <= 52:
        return "Clay Loam"
    else:
        return "Loam"

def safe_get_value(properties, name):
    try:
        return next(layer for layer in properties if layer['name'] == name)['depths'][0]['values']['mean']
    except (StopIteration, KeyError, IndexError):
        print(f"Warning: Could not find data for {name}")
        return None

def process_soil_data(data):
    if data is None:
        return None
    
    try:
        properties = data['properties']['layers']
    except KeyError:
        print("Error: Unexpected API response structure")
        return None
    
    # Extract relevant data
    clay = safe_get_value(properties, 'clay')
    sand = safe_get_value(properties, 'sand')
    silt = safe_get_value(properties, 'silt')
    ph = safe_get_value(properties, 'phh2o')
    nitrogen = safe_get_value(properties, 'nitrogen')

    # Convert to appropriate units if data is available
    clay = clay / 10 if clay is not None else None  # Convert to percentage
    sand = sand / 10 if sand is not None else None  # Convert to percentage
    silt = silt / 10 if silt is not None else None  # Convert to percentage
    ph = ph / 10 if ph is not None else None  # Convert to pH scale
    nitrogen = nitrogen / 100 if nitrogen is not None else None  # Convert to g/kg

    soil_type = determine_soil_type(clay, sand, silt)
    
    nutrients = {
        'N': round(nitrogen, 2) if nitrogen is not None else 'Not available',
        'P': 'Not available',
        'K': 'Not available'
    }
    
    return {
        "Soil Type": soil_type,
        "Soil pH": round(ph, 1) if ph is not None else 'Not available',
        "Soil Nutrients": nutrients
    }

# Example usage
lon, lat = 13.232995, 77.720781  # Example coordinates (center of USA)
raw_data = query_soil_data(lon, lat)
processed_data = process_soil_data(raw_data)

if processed_data:
    print(json.dumps(processed_data, indent=2))
else:
    print("Failed to process soil data")