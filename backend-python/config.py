"""
Configuration Management for Deforestation Monitoring System
Loads environment variables and provides centralized configuration access
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory (Project Root)
BASE_DIR = Path(__file__).resolve().parents[1]
backend_python_dir = BASE_DIR / 'backend-python'

# Load environment variables from .env file in root
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path)


class Config:
    """Central configuration class"""
    
    # Database Configuration
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 5432))
    DB_NAME = os.getenv('DB_NAME', 'deforestation_db')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
    
    @property
    def DATABASE_URL(self):
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # Google Earth Engine
    GEE_SERVICE_ACCOUNT_EMAIL = os.getenv('GEE_SERVICE_ACCOUNT_EMAIL')
    _GEE_KEY_PATH = os.getenv('GEE_PRIVATE_KEY_PATH', 'deforestation-detector-485714-f80fa12e8ce2.json')
    
    @property
    def GEE_PRIVATE_KEY_PATH(self):
        # Resolve relative path against backend-python directory
        path = Path(self._GEE_KEY_PATH)
        if not path.is_absolute():
            # Assume it's in backend-python if relative
            return str(BASE_DIR / 'backend-python' / path)
        return str(path)
        
    GEE_PROJECT_ID = os.getenv('GEE_PROJECT_ID')
    
    # Area of Interest - Brazil (Nova Santa Helena)
    AOI_COUNTRY = os.getenv('AOI_COUNTRY', 'Brazil')
    AOI_STATE = os.getenv('AOI_STATE', 'Mato Grosso')
    AOI_DISTRICT = os.getenv('AOI_DISTRICT', 'Nova Santa Helena')
    @property
    def AOI_NAME(self):
        return self.AOI_DISTRICT or self.AOI_STATE

    
    # Detection Algorithm Parameters
    ALT_THRESHOLD_VH = float(os.getenv('ALT_THRESHOLD_VH', -2.3))  # dB drop
    ALT_THRESHOLD_VV = float(os.getenv('ALT_THRESHOLD_VV', -2.0))  # dB drop
    MLP_CONFIDENCE_THRESHOLD = float(os.getenv('MLP_CONFIDENCE_THRESHOLD', 0.85))
    MINIMUM_MAPPING_UNIT_HA = float(os.getenv('MINIMUM_MAPPING_UNIT_HA', 0.4))
    
    # Grid Configuration
    GRID_CELL_SIZE_METERS = 100  # 100m x 100m = 1 hectare (approx.)
    GRID_PIXELS_PER_SIDE = 10  # 10x10 pixels at 10m = 1 ha
    TARGET_CLUSTER_HECTARES = 2.0  # 2-hectare clusters for feature extraction
    
    # Temporal Configuration
    TEMPORAL_WINDOW_DAYS = 730  # 2 years for harmonic stabilization
    MIN_OBSERVATIONS = 30  # Minimum temporal observations for stable baseline
    REPEAT_CYCLE_DAYS = 6  # Sentinel-1 nominal repeat (can be 12 with single satellite)
    
    # Sentinel-1 GEE Collection
    S1_COLLECTION = 'COPERNICUS/S1_GRD'
    S1_POLARIZATION = ['VV', 'VH']
    S1_INSTRUMENT_MODE = 'IW'  # Interferometric Wide swath
    S1_ORBIT_PASS = None  # None = both, or 'ASCENDING'/'DESCENDING'
    
    # DEM for Terrain Correction
    DEM_COLLECTION = 'USGS/SRTMGL1_003'  # SRTM 30m
    
    # Notification Configuration
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
    ALERT_SMS_RECIPIENT = os.getenv('ALERT_SMS_RECIPIENT')
    
    SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
    ALERT_EMAIL_FROM = os.getenv('ALERT_EMAIL_FROM', 'alerts@deforestation-monitor.org')
    ALERT_EMAIL_RECIPIENT = os.getenv('ALERT_EMAIL_RECIPIENT')
    
    # Scheduler Configuration
    PIPELINE_SCHEDULE_HOUR = int(os.getenv('PIPELINE_SCHEDULE_HOUR', 2))
    PIPELINE_SCHEDULE_MINUTE = int(os.getenv('PIPELINE_SCHEDULE_MINUTE', 0))
    PIPELINE_TIMEZONE = os.getenv('PIPELINE_TIMEZONE', 'America/Sao_Paulo')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', './logs/pipeline.log')
    
    # Paths
    BASE_DIR = Path(__file__).parent
    MODELS_DIR = BASE_DIR / 'models' / 'weights'
    SCRIPTS_DIR = BASE_DIR / 'scripts'
    LOGS_DIR = BASE_DIR.parent / 'logs'
    
    # MLP Model Configuration
    MLP_INPUT_SIZE = 180  # Mean + SD + MMD for VV and VH over 30 observations
    MLP_HIDDEN_LAYERS = [40, 10]
    MLP_MODEL_PATH = MODELS_DIR / 'mlp_case4.h5'
    
    def __init__(self):
        # Create necessary directories
        self.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    def validate(self):
        """Validate critical configuration parameters"""
        errors = []
        
        # Check GEE credentials if using real GEE (not mock)
        if not os.getenv('MOCK_GEE'):
            if not self.GEE_SERVICE_ACCOUNT_EMAIL:
                errors.append("GEE_SERVICE_ACCOUNT_EMAIL not set")
            if not Path(self.GEE_PRIVATE_KEY_PATH).exists():
                errors.append(f"GEE credentials file not found: {self.GEE_PRIVATE_KEY_PATH}")
        
        # Check notification credentials (warnings only)
        if not self.TWILIO_ACCOUNT_SID:
            print("WARNING: TWILIO_ACCOUNT_SID not set. SMS notifications disabled.")
        if not self.SENDGRID_API_KEY:
            print("WARNING: SENDGRID_API_KEY not set. Email notifications disabled.")
        
        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(errors))
        
        return True


# Global configuration instance
config = Config()

# Validate on import (with exception handling for initial setup)
try:
    config.validate()
except ValueError as e:
    print(f"Configuration warning: {e}")
    print("Some features may be disabled. Please update .env file.")
