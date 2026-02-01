
import ee
from services.gee_service import GEEService
from datetime import datetime
from config import Config

def test_historical_extraction():
    try:
        # Initialize GEE
        ee.Initialize(project=Config.GEE_PROJECT_ID)
        
        service = GEEService()
        
        # Define a small AOI (Nova Santa Helena)
        aoi = ee.Geometry.Polygon([
            [-55.5786, -10.8711],
            [-55.5786, -10.8351],
            [-55.5426, -10.8351],
            [-55.5426, -10.8711]
        ])
        
        # Create dummy patches
        patches = service._generate_candidate_patches(ee.Image.constant(1).clip(aoi), aoi).limit(5)
        print(f"Created {patches.size().getInfo()} test patches")
        
        # Target date
        target_date = datetime(2023, 3, 2)
        
        # Run extraction
        print("Starting historical extraction...")
        stats = service.extract_historical_statistics(patches, target_date, days_back=30)
        
        print(f"Success! Extracted {len(stats)} records.")
        
    except Exception as e:
        print(f"Caught exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_historical_extraction()
