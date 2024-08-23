from flask import Flask, render_template, request, jsonify
import requests
import pandas as pd
from datetime import datetime
import cropData

app = Flask(__name__)

crop_recommendations = cropData.crop_recommendations

def fetch_climate_data(latitude, longitude, start_date, end_date):
    url = f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=WS10M,PS,T2M,U10M,QV2M,WD10M,T2MWET,RH2M,T2MDEW,PRECTOTCORR&community=AG&longitude={longitude}&latitude={latitude}&start={start_date}&end={end_date}&format=JSON"
    response = requests.get(url)
    data = response.json()

    if 'properties' in data:
        climate_data = data['properties']['parameter']
        return climate_data
    else:
        raise ValueError(f"Failed to fetch data: {data.get('message', 'Unknown error')}")

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
    
    monthly_averages = df.resample('ME').mean()
    return monthly_averages

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

def predict_for_date(latitude, longitude):
    start_date = "20030101"
    end_date = datetime.now().strftime("%Y%m%d")
    climate_data = fetch_climate_data(latitude, longitude, start_date, end_date)
    monthly_averages = prepare_data(climate_data)
    suitability = calculate_suitability_percentage(monthly_averages, crop_recommendations)
    return suitability

def predict_crop_for_date(crop, latitude, longitude):
    suitability = predict_for_date(latitude, longitude)
    crop_suitability = {}
    
    for month in range(1, 13):
        if crop in suitability[month]:
            crop_suitability[month] = suitability[month][crop]
    
    return crop_suitability

def crops_for_month(month, latitude, longitude):
    suitability = predict_for_date(latitude, longitude)
    if month in suitability:
        return suitability[month]
    else:
        raise ValueError("Invalid month. Please enter a value between 1 and 12.")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    latitude = float(request.form['latitude'])
    longitude = float(request.form['longitude'])
    month = request.form.get('month')
    crop = request.form.get('crop')

    result = {}

    try:
        if crop and month:
            # Predict for a specific crop and month
            month = int(month)
            crop_suitability = predict_crop_for_date(crop, latitude, longitude)
            if month in crop_suitability:
                result['crop_suitability_for_month'] = {month: crop_suitability[month]}
            else:
                result['error'] = f"No suitability data available for crop '{crop}' in month '{month}'."
        elif crop:
            # Predict for specific crop
            crop_suitability = predict_crop_for_date(crop, latitude, longitude)
            result['crop_suitability'] = crop_suitability
        elif month:
            # Predict for specific month
            month = int(month)
            crops_in_month = crops_for_month(month, latitude, longitude)
            result['crops_in_month'] = crops_in_month
        else:
            # General prediction
            suitability = predict_for_date(latitude, longitude)
            result['suitability'] = suitability
    except Exception as e:
        result['error'] = str(e)

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
