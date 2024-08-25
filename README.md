# Climate Suitability Predictor

This Flask application predicts the suitability of various crops based on climate, altitude, and soil data. It fetches data from NASA for climate parameters, Open Elevation for altitude, and SoilGrids for soil properties. The suitability score for each crop is calculated based on predefined conditions and displayed via a web interface.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Dependencies](#dependencies)
- [Configuration](#configuration)

## Features

- Fetches daily climate data from NASA's POWER API.
- Retrieves altitude data from Open Elevation API.
- Queries soil properties from SoilGrids API.
- Processes data to calculate suitability scores for various crops.
- Provides a web interface for user input and results display.

## Installation

1. **Clone the repository:**

   ```git clone https://github.com/arindewangan/farmfuture``` 

2.  **Navigate to the project directory:**
    `cd climate-suitability-predictor` 
    
3.  **Create a virtual environment:**
    `python -m venv venv` 
    
4.  **Activate the virtual environment:**
    
    -   On Windows:
        `venv\Scripts\activate` 
        
    -   On macOS/Linux:
        `source venv/bin/activate` 
        
5.  **Install the required dependencies:**
    
    `pip install -r requirements.txt` 
    

## Usage

1.  **Run the Flask application:**
    
    bash
    
    Copy code
    
    `python app.py` 
    
2.  **Open your web browser and navigate to:**
    
    
    `http://127.0.0.1:5000/` 
    
    You will see the main interface where you can input latitude, longitude, and optionally select a crop.
    
3.  **Submit the form to get the suitability prediction for the specified location and crop.**
    

## API Endpoints

### `GET /`

-   **Description:** Serves the main interface (HTML page) for user input.

### `POST /predict`

-   **Description:** Provides the suitability prediction based on the provided latitude, longitude, and optional crop.
-   **Request Parameters:**
    -   `latitude` (float): Latitude of the location.
    -   `longitude` (float): Longitude of the location.
    -   `crop` (optional, string): The crop for which to predict suitability.
-   **Response:**
    -   JSON object with suitability scores for all crops or the specified crop.

## Dependencies

-   **Flask:** For serving the web application.
-   **requests:** For making HTTP requests to external APIs.
-   **pandas:** For data manipulation and analysis.

Install the dependencies using the `requirements.txt` file provided in the project.

## Configuration

-   **NASA API URL:** `https://power.larc.nasa.gov/api/temporal/daily/point`
-   **Open Elevation API URL:** `https://api.open-elevation.com/api/v1/lookup`
-   **SoilGrids API URL:** `https://rest.isric.org/soilgrids/v2.0/properties/query`


----------