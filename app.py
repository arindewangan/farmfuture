from flask import Flask, render_template, request, jsonify
import requests
import pandas as pd
from datetime import datetime
from cropData import crop_recommendations

app = Flask(__name__)

# Constants
NASA_API_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
CLIMATE_PARAMS = [
    'WS10M', 'V10M', 'PS', 'T2M', 'QV2M', 'WD10M', 'T2MWET', 'RH2M', 'T2MDEW', 
    'PRECTOTCORR', 'ALLSKY_SFC_SW_DNI'
]
START_DATE = "20030101"
END_DATE = "20231231"

def fetch_climate_data(latitude, longitude):
    params = {
        "parameters": ",".join(CLIMATE_PARAMS),
        "community": "AG",
        "longitude": longitude,
        "latitude": latitude,
        "start": START_DATE,
        "end": END_DATE,
        "format": "JSON"
    }
    try:
        response = requests.get(NASA_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        if 'properties' in data and 'parameter' in data['properties']:
            return data['properties']['parameter']
        else:
            raise ValueError(f"Invalid data format received: {data.get('message', 'Unknown error')}")
    except requests.RequestException as e:
        print(f"Error fetching climate data: {e}")
        raise

def fetch_altitude_data(latitude, longitude):
    API_URL = "https://api.open-elevation.com/api/v1/lookup"
    try:
        response = requests.get(API_URL, params={"locations": f"{latitude},{longitude}"})
        response.raise_for_status()
        data = response.json()
        if 'results' in data and len(data['results']) > 0:
            return data['results'][0]['elevation']
        else:
            raise ValueError("No altitude data found")
    except requests.RequestException as e:
        print(f"Error fetching altitude data: {e}")
        raise

def fetch_soil_data(lon, lat):
    base_url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    params = {
        "lon": lon,
        "lat": lat,
        "property": ["clay", "sand", "silt", "phh2o", "nitrogen"],
        "depth": ["0-5cm", "5-15cm", "15-30cm"],
        "value": ["mean"]
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        return process_soil_data(data)
    except requests.RequestException as e:
        print(f"Error fetching soil data: {e}")
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

def safe_get_value(properties, name, depth):
    try:
        return next(depth_layer['values']['mean'] 
                    for layer in properties 
                    if layer['name'] == name 
                    for depth_layer in layer['depths'] 
                    if depth_layer['label'] == depth)
    except (StopIteration, KeyError, IndexError):
        print(f"Warning: Could not find data for {name} at depth {depth}")
        return None

def average_depth_values(properties, name, depths):
    values = [safe_get_value(properties, name, depth) for depth in depths]
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)

def process_soil_data(data):
    if data is None:
        return None
        
    try:
        properties = data['properties']['layers']
    except KeyError:
        print("Error: Unexpected API response structure")
        return None
    
    # Define the depths for averaging
    depth_intervals = ["0-5cm", "5-15cm", "15-30cm"]
    
    # Extract and average relevant data
    clay = average_depth_values(properties, 'clay', depth_intervals)
    sand = average_depth_values(properties, 'sand', depth_intervals)
    silt = average_depth_values(properties, 'silt', depth_intervals)
    ph = average_depth_values(properties, 'phh2o', depth_intervals)
    nitrogen = average_depth_values(properties, 'nitrogen', depth_intervals)

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

def prepare_climate_data(climate_data):
    print("Inside prepare_climate_data function.")
    
    try:
        # Convert climate data to DataFrame
        df = pd.DataFrame(climate_data)
        print("Initial DataFrame:")
        print(df.head())

        # Filter out columns that are not in the DataFrame
        available_params = [param for param in CLIMATE_PARAMS if param in df.columns]
        print(f"Available parameters: {available_params}")
        
        if not available_params:
            raise ValueError("No valid columns available in the climate data.")
        
        # Convert index to datetime and sort
        df.index = pd.to_datetime(df.index, format='%Y%m%d')
        df.sort_index(inplace=True)
        print("DataFrame after index conversion and sorting:")
        print(df.head())

        # Remove invalid data (-999) and outliers
        df = df.replace(-999, pd.NA).dropna()
        print("DataFrame after removing invalid data:")
        print(df.head())

        df_annual = df.resample('Y').agg({
            'T2M': 'mean',
            'PRECTOTCORR': 'sum',
            'RH2M': 'mean',
            'ALLSKY_SFC_SW_DNI': 'mean',
            'WS10M': 'mean',
            'V10M': 'mean',
            'PS': 'mean',
            'QV2M': 'mean',
            'WD10M': 'mean',
            'T2MWET': 'mean',
            'T2MDEW': 'mean'
        })
        print("Annual DataFrame:")
        print(df_annual.head())

        df_annual = remove_outliers(df_annual, available_params)
        print("Annual DataFrame after removing outliers:")
        print(df_annual.head())

        if df_annual.empty:
            raise ValueError("No valid data available after processing")
        
        return df_annual.mean()
    
    except Exception as e:
        print(f"Error in processing data: {e}")
        raise

def remove_outliers(df, columns):
    Q1 = df[columns].quantile(0.25)
    Q3 = df[columns].quantile(0.75)
    IQR = Q3 - Q1
    return df[~((df[columns] < (Q1 - 1.5 * IQR)) | (df[columns] > (Q3 + 1.5 * IQR))).any(axis=1)]

def convert_wind_speed_kmh(wind_speed_m_s):
    return wind_speed_m_s * 3.6

def parse_range(value):
    if isinstance(value, str):
        parts = value.split(',')
        return (float(parts[0].strip()), float(parts[1].strip()))
    return value

def is_within_range(value, range_spec):
    if isinstance(range_spec, dict):
        return range_spec['min'] <= value <= range_spec['max']
    min_val, max_val = parse_range(range_spec)
    return min_val <= value <= max_val

def calculate_suitability(overall_averages, crop_conditions, altitude=None, soil_data=None):
    suitability = {}
    
    for crop, conditions in crop_conditions.items():
        score = 0
        weight = 1 / 8  # Adjust weights to account for the additional parameter

        # Temperature suitability
        if is_within_range(overall_averages.get('T2M', float('inf')), conditions['temperature_range']):
            score += weight
        
        # Rainfall suitability
        if is_within_range(overall_averages.get('PRECTOTCORR', 0), conditions.get('annual_rainfall_mm', '0')):
            score += weight
        
        # Humidity suitability
        if is_within_range(overall_averages.get('RH2M', float('inf')), conditions['humidity_range_percent']):
            score += weight
        
        # Wind Speed Suitability
        wind_speed_kmh = convert_wind_speed_kmh(overall_averages.get('WS10M', 0))
        if wind_speed_kmh <= conditions.get('wind_conditions_kmh', {}).get('speed', float('inf')):
            score += weight
        
        # Wet Bulb Temperature Suitability
        if 'T2MWET' in overall_averages and is_within_range(overall_averages.get('T2MWET', float('inf')), conditions['temperature_range']):
            score += weight
        
        # Dew Point Suitability
        if 'T2MDEW' in overall_averages and is_within_range(overall_averages.get('T2MDEW', float('inf')), conditions['temperature_range']):
            score += weight
        
        # DNI Suitability (Assuming it's desirable)
        if 'ALLSKY_SFC_SW_DNI' in overall_averages:
            score += weight
        
        # Altitude Suitability (if altitude data is available)
        if altitude and is_within_range(altitude, conditions.get('altitude_m', "0, 3000")):
            score += weight
        
        # Soil Data Suitability
        if soil_data:
            soil_type = soil_data.get("Soil Type", "Unknown")
            if soil_type in conditions.get('soil_types', []):
                score += weight
        
        suitability[crop] = score * 100  # Convert to percentage
    
    return suitability

def predict_suitability(latitude, longitude, crop=None):
    try:
        print("Fetching climate data...")
        climate_data = fetch_climate_data(latitude, longitude)
        print("Climate data fetched successfully.")
        
        print("Preparing climate data...")
        overall_averages = prepare_climate_data(climate_data)
        print("Climate data prepared successfully.")
        print(overall_averages)
        
        print("Fetching altitude data...")
        altitude = fetch_altitude_data(latitude, longitude)
        print(f"Altitude: {altitude} meters")
        
        print("Fetching soil data...")
        soil_data = fetch_soil_data(longitude, latitude)
        print(f"Soil data: {soil_data}")

        print("Calculating suitability...")
        suitability = calculate_suitability(overall_averages, crop_recommendations, altitude, soil_data)
        print("Suitability calculated successfully.")
        
        if crop:
            return {crop: suitability.get(crop, 0)}
        return suitability
    
    except Exception as e:
        print(f"Error in predicting suitability: {e}")
        return {'error': str(e)}

# Store status in a global variable
status = 'Not started'
 
@app.route('/status')
def status_route():
    return jsonify(status)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict_route():
    latitude = float(request.form['latitude'])
    longitude = float(request.form['longitude'])
    crop = request.form.get('crop')

    try:
        global status
        # Update status and call prediction function
        status = 'Fetching climate data...'
        climate_data = fetch_climate_data(latitude, longitude)
        status = 'Climate data fetched successfully.'
        
        status = 'Preparing climate data...'
        overall_averages = prepare_climate_data(climate_data)
        status = 'Climate data prepared successfully.'

        status = 'Fetching altitude data...'
        altitude = fetch_altitude_data(latitude, longitude)
        status = f'Altitude: {altitude} meters'

        status = 'Fetching soil data...'
        soil_data = fetch_soil_data(longitude, latitude)
        status = f'Soil data Fetched Successfully.'

        status = 'Calculating suitability...'
        suitability = calculate_suitability(overall_averages, crop_recommendations, altitude, soil_data)
        status = 'Suitability calculated successfully.'

        if crop:
            return jsonify({'suitability': {crop: suitability.get(crop, 0)}})
        return jsonify({'suitability': suitability})

    except Exception as e:
        status['calculate_suitability'] = 'Error in predicting suitability.'
        return jsonify({'error': str(e)})

# if __name__ == "__main__":
#     app.run(debug=True)
