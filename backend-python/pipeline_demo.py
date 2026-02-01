"""
Demo/Historical Pipeline Execution Script
Runs the deforestation detection on a specific historical date (e.g. 26 Aug 2023)
Stores results with is_demo=True
"""

from datetime import datetime, timedelta
from loguru import logger
import sys
import json
import argparse
from typing import List, Dict, Any

# Configure logging
logger.remove()
logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>", level="INFO")
logger.add("pipeline_demo.log", rotation="10 MB", retention="5 days", level="DEBUG")

from config import config
from db_utils import db
from services.gee_service import gee_service
from models.alt_detector import ALTDetector
from models.mlp_model import MLPModel

def run_demo_pipeline(target_date_str: str, min_obs: int = 30):
    """
    Execute the deforestation detection pipeline for a historical date
    
    Args:
        target_date_str: Target date in YYYY-MM-DD format
    """
    is_demo = True
    
    logger.info("="*80)
    logger.info("DEFORESTATION MONITORING - DEMO PIPELINE")
    logger.info(f"Timestamp: {datetime.now()}")
    logger.info(f"Target Date: {target_date_str}")
    logger.info("="*80)
    
    try:
        # ========================================================================
        # Step 1: Initialize Components
        # ========================================================================
        logger.info("\n[1/7] Initializing components...")
        
        if not gee_service or not gee_service.initialized:
            logger.error("GEE service not initialized. Aborting.")
            return False
        
        alt_detector = ALTDetector(min_observations=min_obs)
        mlp_model = MLPModel()
        
        logger.success("✓ Components initialized")
        
        # ========================================================================
        # Step 2: Load AOI Geometry
        # ========================================================================
        logger.info("\n[2/7] Loading Area of Interest...")
        
        aoi = gee_service.get_aoi_geometry()
        logger.success(f"✓ AOI loaded: {config.AOI_NAME}")
        
        # ========================================================================
        # Step 3: Query Historical Images
        # ========================================================================
        logger.info("\n[3/7] Querying Sentinel-1 catalog for target date...")
        
        # DEMO MODE: specific date
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        
        # Look for images starting from the target date + 12 days forward
        end_search = target_date + timedelta(days=12)
        
        candidates = gee_service.query_latest_images(
            aoi, 
            days_back=12, # Cover the gap
            limit=20, 
            end_date=end_search
        )
        
        # Filter for candidates >= target_date
        # We want the image that *happened* on or immediately after the target date
        valid_candidates = [
            img for img in candidates 
            if img['acquisition_date'] >= target_date
        ]
        valid_candidates.sort(key=lambda x: x['acquisition_date'])
        
        if not valid_candidates:
            logger.warning(f"DEMO: No images found on or after {target_date_str}")
            return False
            
        # Pick the first one
        selected = valid_candidates[0]
        images_to_process = [selected]
        
        logger.info(f"Found image for demo: {selected['image_id']}")
        logger.info(f"Acquisition: {selected['acquisition_date']}")
        
        # ========================================================================
        # Step 4: Process Image
        # ========================================================================
        logger.info("\n[4/7] Processing SAR images...")
        
        all_detections = []
        
        for idx, img_metadata in enumerate(images_to_process, 1):
            image_id = img_metadata['image_id']
            logger.info(f"\n  Processing image {idx}/{len(images_to_process)}: {image_id}")
            
            try:
                # Mark as processing (Register image first to avoid FK violation)
                img_metadata['status'] = 'PROCESSING'
                db.insert_processed_image(img_metadata)

                # Preprocess image
                logger.info("    - Preprocessing (calibration, terrain correction)...")
                preprocessed, stabilized = gee_service.preprocess_image(image_id, aoi)
                
                # Extract backscatter statistics
                logger.info("    - Extracting backscatter statistics...")
                stats_collection = gee_service.extract_backscatter_statistics(stabilized, aoi)
                
                logger.info("    - Exporting statistics from GEE...")
                try:
                    stats_list = stats_collection.getInfo()['features']
                except Exception as e:
                    logger.error(f"    ✗ Failed to fetch statistics: {e}")
                    raise
                
                if not stats_list:
                    logger.warning("    ! No grid cells returned")
                    continue

                grid_observations = [f['properties'] for f in stats_list]
                
                # Store in database
                logger.info(f"    - Storing {len(grid_observations)} grid cell observations...")
                db.insert_backscatter_timeseries(grid_observations)
                
                # Backfill history for these patches (Establishing 6-month baseline)
                logger.info("    - Backfilling 6 months of historical baseline...")
                historical_data, historical_images = gee_service.extract_historical_statistics(
                    patches=stats_collection,
                    target_date=img_metadata['acquisition_date']
                )
                
                if historical_images:
                    logger.info(f"    - Registering {len(historical_images)} historical images to satisfy FK...")
                    # Insert images one by one (or could batch if db_utils supported it)
                    for hist_img in historical_images:
                        # Ensure we don't overwrite status of existing images if they are 'PROCESSING' or 'FAILED'
                        # but insert_processed_image uses ON CONFLICT UPDATE for status.
                        # For history, we just want to ensure they exist.
                        # We'll rely on the existing method.
                        db.insert_processed_image(hist_img)
                        
                if historical_data:
                    logger.info(f"    - Storing {len(historical_data)} historical observations...")
                    db.insert_backscatter_timeseries(historical_data)
                
                logger.success(f"    ✓ Image processed and historical baseline established")
                
            except Exception as e:
                logger.error(f"    ✗ Processing failed: {e}")
                logger.error("Skipping image, but continuing pipeline for debug/check")
                # continue
        
        # ========================================================================
        # Step 5: Run ALT Detection
        # ========================================================================
        logger.info("\n[5/7] Running Adaptive Linear Thresholding detection...")
        
        # Use the image date as reference for detection
        ref_date = f"'{images_to_process[0]['acquisition_date'].strftime('%Y-%m-%d')}'"
        
        recent_obs_query = f"""
            SELECT DISTINCT ON (grid_cell_id)
                grid_cell_id,
                observation_date,
                vv_mean, vv_std, vh_mean, vh_std,
                ST_X(geom) as lon, ST_Y(geom) as lat,
                source_image_id
            FROM backscatter_timeseries
            WHERE observation_date <= {ref_date} 
              AND observation_date >= {ref_date}::DATE - INTERVAL '7 days'
            ORDER BY grid_cell_id, observation_date DESC;
        """
        
        recent_observations = db.execute_query(recent_obs_query)
        logger.info(f"Analyzing {len(recent_observations)} recent grid cell observations around {ref_date}")
        
        # Get historical baseline
        baseline_data = {}
        for obs in recent_observations:
            grid_id = obs['grid_cell_id']
            historical = db.get_historical_backscatter(grid_id, days=180)
            if len(historical) >= alt_detector.min_observations:
                baseline_data[grid_id] = historical
        
        detections = alt_detector.batch_detect(recent_observations, baseline_data)
        logger.info(f"ALT detected {len(detections)} potential deforestation events")
        
        # ========================================================================
        # Step 6: MLP Validation
        # ========================================================================
        logger.info("\n[6/7] Validating detections with MLP model...")
        
        validated_alerts = []
        
        for detection in detections:
            grid_id = detection['grid_cell_id']
            timeseries = db.get_historical_backscatter(grid_id, days=365)
            
            if len(timeseries) < min_obs: continue
            
            validation = mlp_model.validate_detection(grid_id, timeseries)
            
            if validation['is_valid_alert']:
                alert = {
                    **detection,
                    'confidence_score': validation['confidence_score']
                }
                validated_alerts.append(alert)
        
        logger.info(f"MLP validated {len(validated_alerts)} alerts")
        
        # ========================================================================
        # Step 6.5: Optical Validation
        # ========================================================================
        logger.info("\n[6.5/7] Performing Optical Validation (Sentinel-2)...")

        final_alerts = []

        for alert in validated_alerts:
            import ee
            lon, lat = alert['longitude'], alert['latitude']
            geom = ee.Geometry.Point([lon, lat]).buffer(50).bounds() 
            
            optical_data = gee_service.extract_optical_data(
                patch_geometry=geom,
                target_date=alert['detection_date']
            )
            
            if optical_data:
                ndvi_drop = optical_data['ndvi_drop']
                ndvi_after = optical_data['ndvi_after']
                
                optical_score = 0.5 
                if ndvi_drop > 0.15: optical_score = 1.0
                elif ndvi_drop > 0.05: optical_score = 0.8
                elif ndvi_after > 0.6: optical_score = 0.1 
                
                combined_score = (alert['confidence_score'] * 0.6) + (optical_score * 0.4)
                
                alert.update({
                    'optical_score': optical_score,
                    'combined_score': combined_score,
                    'ndvi_drop': ndvi_drop
                })
            else:
                alert.update({
                    'optical_score': None,
                    'combined_score': alert['confidence_score'],
                    'ndvi_drop': None
                })
            
            final_alerts.append(alert)

        # ========================================================================
        # Step 7: Alert Storage (Demo Mode)
        # ========================================================================
        logger.info("\n[7/7] Storing alerts (DEMO MODE)...")
        
        stored_cnt = 0
        for alert in final_alerts:
            geojson = {
                "type": "Polygon",
                "coordinates": [[
                    [alert['longitude'], alert['latitude']],
                    [alert['longitude'] + 0.001, alert['latitude']],
                    [alert['longitude'] + 0.001, alert['latitude'] + 0.001],
                    [alert['longitude'], alert['latitude'] + 0.001],
                    [alert['longitude'], alert['latitude']]
                ]]
            }
            
            alert_data = {
                'detection_date': alert['detection_date'],
                'confidence_score': alert['confidence_score'],
                'area_hectares': config.TARGET_CLUSTER_HECTARES,
                'risk_tier': 'TIER_1', 
                'boundary_id': None,
                'alt_vv_drop_db': alert['vv_drop_db'],
                'alt_vh_drop_db': alert['vh_drop_db'],
                'source_image_id': alert['source_image_id'],
                'optical_score': alert.get('optical_score'),
                'combined_score': alert.get('combined_score'),
                'ndvi_drop': alert.get('ndvi_drop'),
                'geom': json.dumps(geojson),
                'is_demo': True,
                'demo_date': target_date_str
            }
            
            db.insert_alert(alert_data)
            stored_cnt += 1
            
        logger.success(f"✓ Stored {stored_cnt} DEMO alerts")
        return True
        
    except Exception as e:
        logger.exception(f"Demo pipeline failed: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', type=str, required=True, help='YYYY-MM-DD')
    parser.add_argument('--min-obs', type=int, default=30, help='Minimum historical observations (default: 30)')
    args = parser.parse_args()
    
    success = run_demo_pipeline(args.date, min_obs=args.min_obs)
    sys.exit(0 if success else 1)
