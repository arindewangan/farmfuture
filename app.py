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

def calculate_suitability(overall_averages, crop_conditions):
    suitability = {}
    
    for crop, conditions in crop_conditions.items():
        score = 0
        weight = 1 / 6  # Equal weight for each parameter

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
        
        print("Calculating suitability...")
        suitability = calculate_suitability(overall_averages, crop_recommendations)
        print("Suitability calculated successfully.")
        
        if crop:
            return {crop: suitability.get(crop, 0)}
        return suitability
    
    except Exception as e:
        print(f"Error in predicting suitability: {e}")
        return {'error': str(e)}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict_route():
    latitude = float(request.form['latitude'])
    longitude = float(request.form['longitude'])
    crop = request.form.get('crop')

    try:
        result = predict_suitability(latitude, longitude, crop)
    except Exception as e:
        return jsonify({'error': str(e)})

    return jsonify({'suitability': result})

if __name__ == "__main__":
    app.run(debug=True)
