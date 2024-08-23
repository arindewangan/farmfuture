import requests
import pandas as pd
from datetime import datetime

# Define crop recommendations with general climate requirements
crop_recommendations = {
    'Rice': {
        'temp': (20, 30),         # Temperature in °C
        'precip': (3, 10),        # Precipitation in mm/hour
        'humidity': (70, 90),     # Relative Humidity in %
        'pressure': (90, 110)     # Surface Pressure in kPa
    },
    'Wheat': {
        'temp': (10, 20),         # Temperature in °C
        'precip': (0.5, 5),       # Precipitation in mm/hour
        'humidity': (50, 70),     # Relative Humidity in %
        'pressure': (90, 110)     # Surface Pressure in kPa
    },
    # Add more crops with their temperature, precipitation, humidity, and pressure ranges
}

# Function to fetch climate data
def fetch_climate_data(latitude, longitude, start_date, end_date):
    url = f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=WS10M,PS,T2M,U10M,QV2M,WD10M,T2MWET,RH2M,T2MDEW,PRECTOTCORR&community=AG&longitude={longitude}&latitude={latitude}&start={start_date}&end={end_date}&format=JSON"
    response = requests.get(url)
    data = response.json()

    if 'properties' in data:
        climate_data = data['properties']['parameter']
        return climate_data
    else:
        raise ValueError(f"Failed to fetch data: {data.get('message', 'Unknown error')}")

# Function to prepare data and calculate monthly averages
def prepare_data(climate_data):
    df = pd.DataFrame(climate_data)
    required_columns = ['T2M', 'PRECTOTCORR', 'RH2M', 'PS']
    if not all(col in df.columns for col in required_columns):
        raise ValueError(f"DataFrame missing required columns. Found columns: {df.columns}")
    
    df = df.reset_index()
    df['index'] = pd.to_datetime(df['index'], format='%Y%m%d')
    df.set_index('index', inplace=True)
    df = df.sort_index()
    df = df[(df['T2M'] != -999) & (df['PRECTOTCORR'] != -999) & (df['RH2M'] != -999) & (df['PS'] != -999)]
    Q1 = df.quantile(0.25)
    Q3 = df.quantile(0.75)
    IQR = Q3 - Q1
    df = df[~((df < (Q1 - 1.5 * IQR)) | (df > (Q3 + 1.5 * IQR))).any(axis=1)]
    
    # Calculate monthly averages
    monthly_averages = df.resample('M').mean()
    return monthly_averages

# Function to calculate suitability percentage for each crop
def calculate_suitability_percentage(monthly_averages, crop_conditions):
    total_params = len(crop_conditions)
    suitability = {month: {} for month in range(1, 13)}
    
    for month in range(1, 13):
        month_data = monthly_averages[monthly_averages.index.month == month]
        if month_data.empty:
            continue
        
        temp_mean = month_data['T2M'].mean()
        precip_mean = month_data['PRECTOTCORR'].mean()
        humidity_mean = month_data['RH2M'].mean()
        pressure_mean = month_data['PS'].mean()
        
        for crop, conditions in crop_conditions.items():
            temp_min, temp_max = conditions['temp']
            precip_min, precip_max = conditions['precip']
            humidity_min, humidity_max = conditions['humidity']
            pressure_min, pressure_max = conditions['pressure']
            
            suitability_percentage = 0
            if temp_min <= temp_mean <= temp_max:
                suitability_percentage += 25
            if precip_min <= precip_mean <= precip_max:
                suitability_percentage += 25
            if humidity_min <= humidity_mean <= humidity_max:
                suitability_percentage += 25
            if pressure_min <= pressure_mean <= pressure_max:
                suitability_percentage += 25
            
            suitability[month][crop] = suitability_percentage
            
    return suitability

# Function to get the prediction for all months
def predict_for_date(latitude, longitude):
    start_date = "20030101"
    end_date = datetime.now().strftime("%Y%m%d")
    climate_data = fetch_climate_data(latitude, longitude, start_date, end_date)
    monthly_averages = prepare_data(climate_data)
    suitability = calculate_suitability_percentage(monthly_averages, crop_recommendations)
    return suitability

# Function to get the prediction for a specific crop
def predict_crop_for_date(crop, latitude, longitude):
    suitability = predict_for_date(latitude, longitude)
    crop_suitability = {}
    
    for month in range(1, 13):
        if crop in suitability[month]:
            crop_suitability[month] = suitability[month][crop]
    
    return crop_suitability

# Function to get crops grown in a particular month with chances
def crops_for_month(month, latitude, longitude):
    suitability = predict_for_date(latitude, longitude)
    if month in suitability:
        return suitability[month]
    else:
        raise ValueError("Invalid month. Please enter a value between 1 and 12.")

# Example usage
if __name__ == "__main__":
    latitude = 13.241753
    longitude = 77.718927

    # Get prediction for all months
    try:
        suitability = predict_for_date(latitude, longitude)
        for month in range(1, 13):
            month_name = datetime(2000, month, 1).strftime('%B')
            print(f"Month: {month_name}")
            for crop, percentage in suitability[month].items():
                print(f"  {crop}: {percentage}%")
    except Exception as e:
        print(f"Error: {e}")
    
    # Get prediction for a specific crop
    crop = 'Rice'
    try:
        crop_suitability = predict_crop_for_date(crop, latitude, longitude)
        print(f"\nSuitability for {crop}:")
        for month, percentage in crop_suitability.items():
            month_name = datetime(2000, month, 1).strftime('%B')
            print(f"  {month_name}: {percentage}%")
    except Exception as e:
        print(f"Error: {e}")
    
    # Get crops grown in a particular month with chances
    month = 8
    try:
        crops_in_month = crops_for_month(month, latitude, longitude)
        print(f"\nCrops suitable in {datetime(2000, month, 1).strftime('%B')}:")
        for crop, percentage in crops_in_month.items():
            print(f"  {crop}: {percentage}%")
    except Exception as e:
        print(f"Error: {e}")
