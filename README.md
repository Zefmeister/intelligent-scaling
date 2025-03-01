# Intelligent Scaling Decision Tool

A data-driven application to help trucking companies make informed decisions about when and where to scale their trucks.

## Overview

This tool analyzes historical data and real-time factors to recommend optimal scaling locations, helping to:
- Reduce overweight violations
- Minimize unnecessary scaling costs
- Optimize route efficiency
- Manage risk based on historical data

## Features

- Risk analysis based on historical route data
- Liable party risk assessment
- Intelligent CAT scale location recommendations
- Cost-benefit analysis of scaling decisions
- Early route scaling optimization

## Setup

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Prepare data directory:
```bash
mkdir data
```

4. Required data files in `data/` directory:
- cat_scales.xlsx (CAT scale locations)
- Cargo_claims_data.xlsx (Claims and incidents data)
- risk_ratings_2.xlsx (Generated risk ratings)

## Usage

1. Generate risk ratings:
```bash
python scripts/risk_analysis.py
```

2. Run the application:
```bash
streamlit run scripts/intelligent_scaling.py
```

3. Enter route information:
   - Ship From location (City, State)
   - Ship To location (City, State)
   - Liable Party Name

## Risk Analysis

Risk ratings are calculated based on:
- Historical incidents
- Total penalties
- Route-specific risk factors
- Liable party history

Risk levels:
- High Risk (≥0.7): Mandatory weighing
- Medium Risk (≥0.4): Recommended weighing
- Low Risk (<0.4): Optional weighing

## File Structure

```
intelligent-scaling/
├── data/                    # Data files
├── scripts/
│   ├── intelligent_scaling.py  # Main application
│   ├── risk_analysis.py        # Risk calculation
│   └── risk_utils.py           # Utility functions
├── requirements.txt         # Dependencies
└── README.md               # Documentation
```

## Dependencies

- streamlit: Web interface
- pandas: Data processing
- geopy: Geocoding and distance calculations
- scikit-learn: Risk normalization
- openpyxl: Excel file handling