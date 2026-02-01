"""
Main Pipeline Execution Script
Orchestrates the daily deforestation detection workflow
"""

from datetime import datetime
from loguru import logger
import sys
import json
from typing import List, Dict, Any

# Configure logging
logger.remove()
logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>", level="INFO")
logger.add(config.LOG_FILE, rotation="10 MB", retention="30 days", level="DEBUG")

from config import config
from db_utils import db
from services.gee_service import gee_service
from models.alt_detector import ALTDetector
from models.mlp_model import MLPModel

def run_pipeline():
    """Execute the complete deforestation detection pipeline"""
    
    logger.info("="*80)
    logger.info("DEFORESTATION MONITORING PIPELINE - START")
    logger.info(f"Timestamp: {datetime.now()}")
    logger.info(f"AOI: {config.AOI_NAME}, {config.AOI_STATE} (Code: {config.AOI_MUNICIPALITY_CODE})")
    logger.info("="*80)
    
    try:
        # ========================================================================
        # Step 1: Initialize Components
        # ========================================================================
        logger.info("\n[1/7] Initializing components...")
        
        if not gee_service or not gee_service.initialized:
            logger.error("GEE service not initialized. Aborting.")
            return False
        
        alt_detector = ALTDetector()
        mlp_model = MLPModel()
        
        logger.success("✓ Components initialized")
        
        # ========================================================================
        # Step 2: Load AOI Geometry
        # ========================================================================
        logger.info("\n[2/7] Loading Area of Interest...")
        
        aoi = gee_service.get_aoi_geometry()
        logger.success(f"✓ AOI loaded: {config.AOI_NAME}")
        
        # ========================================================================
        # Step 3: Query Unprocessed Images
        # ========================================================================
        logger.info("\n[3/7] Querying Sentinel-1 catalog...")
        
        unprocessed_images = gee_service.get_unprocessed_images(aoi, days_back=14)
        
        if not unprocessed_images:
            logger.info("No new images to process. Pipeline complete.")
            return True
        
        logger.info(f"Found {len(unprocessed_images)} new images to process")
        
        # ========================================================================
        # Step 4: Process Each Image
        # ========================================================================
        logger.info("\n[4/7] Processing SAR images...")
        
        all_detections = []
        
        for idx, img_metadata in enumerate(unprocessed_images, 1):
            image_id = img_metadata['image_id']
            logger.info(f"\n  Processing image {idx}/{len(unprocessed_images)}: {image_id}")
            logger.info(f"  Acquisition: {img_metadata['acquisition_date']}")
            
            try:
                # Mark as processing (Ensure record exists first)
                img_metadata['status'] = 'PROCESSING'
                db.insert_processed_image(img_metadata)

                # Preprocess image
                logger.info("    - Preprocessing (calibration, terrain correction)...")
                preprocessed, stabilized = gee_service.preprocess_image(image_id, aoi)
                
                # Extract backscatter statistics
                logger.info("    - Extracting backscatter statistics...")
                stats_collection = gee_service.extract_backscatter_statistics(stabilized, aoi)
                
                # Convert to Python-friendly format
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
                historical_data = gee_service.extract_historical_statistics(
                    patches=stats_collection,
                    target_date=img_metadata['acquisition_date']
                )
                if historical_data:
                    logger.info(f"    - Storing {len(historical_data)} historical observations...")
                    db.insert_backscatter_timeseries(historical_data)
                
                # Mark image as completed
                db.execute_update(
                    """UPDATE processed_images 
                       SET status = 'COMPLETED', 
                           processing_date = CURRENT_TIMESTAMP,
                           num_alerts_generated = 0
                       WHERE image_id = %s""",
                    (image_id,)
                )
                
                logger.success(f"    ✓ Image processed successfully")
                
            except Exception as e:
                logger.error(f"    ✗ Processing failed: {e}")
                db.execute_update(
                    "UPDATE processed_images SET status = 'FAILED', error_message = %s WHERE image_id = %s",
                    (str(e), image_id)
                )
                continue
        
        # ========================================================================
        # Step 5: Run ALT Detection
        # ========================================================================
        logger.info("\n[5/7] Running Adaptive Linear Thresholding detection...")
        
        # Get recent observations for detection
        recent_obs_query = """
            SELECT DISTINCT ON (grid_cell_id)
                grid_cell_id,
                observation_date,
                vv_mean, vv_std, vh_mean, vh_std,
                ST_X(geom) as lon, ST_Y(geom) as lat,
                source_image_id
            FROM backscatter_timeseries
            WHERE observation_date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY grid_cell_id, observation_date DESC;
        """
        
        recent_observations = db.execute_query(recent_obs_query)
        logger.info(f"Analyzing {len(recent_observations)} recent grid cell observations")
        
        # Get historical baseline for each grid cell
        baseline_data = {}
        for obs in recent_observations:
            grid_id = obs['grid_cell_id']
            historical = db.get_historical_backscatter(grid_id, days=180)
            if len(historical) >= alt_detector.min_observations:
                baseline_data[grid_id] = historical
        
        logger.info(f"Baseline data available for {len(baseline_data)} grid cells")
        
        # Run batch detection
        detections = alt_detector.batch_detect(recent_observations, baseline_data)
        
        logger.info(f"ALT detected {len(detections)} potential deforestation events")
        
        # ========================================================================
        # Step 6: MLP Validation
        # ========================================================================
        logger.info("\n[6/7] Validating detections with MLP model...")
        
        validated_alerts = []
        
        for detection in detections:
            grid_id = detection['grid_cell_id']
            
            # Get full time series for feature extraction
            timeseries = db.get_historical_backscatter(grid_id, days=365)
            
            if len(timeseries) < 30:
                logger.warning(f"Skipping {grid_id}: insufficient time series data")
                continue
            
            # Validate with MLP
            validation = mlp_model.validate_detection(grid_id, timeseries)
            
            if validation['is_valid_alert']:
                # Combine detection and validation metadata
                alert = {
                    **detection,
                    'confidence_score': validation['confidence_score']
                }
                validated_alerts.append(alert)
        
        logger.info(f"MLP validated {len(validated_alerts)} alerts (threshold: {mlp_model.threshold})")
        
        # ========================================================================
        # Step 6.5: Optical Validation (Sentinel-2)
        # ========================================================================
        logger.info("\n[6.5/7] Performing Optical Validation (Sentinel-2)...")

        final_alerts = []

        for alert in validated_alerts:
            logger.info(f"  Verifying alert {alert['grid_cell_id']}...")
            
            import ee
            # Construct geometry for GEE (10x10 pixels ~ 100m box)
            lon, lat = alert['longitude'], alert['latitude']
            geom = ee.Geometry.Point([lon, lat]).buffer(50).bounds() 
            
            # Query Optical Data
            optical_data = gee_service.extract_optical_data(
                patch_geometry=geom,
                target_date=alert['detection_date']
            )
            
            if optical_data:
                ndvi_drop = optical_data['ndvi_drop']
                ndvi_after = optical_data['ndvi_after']
                
                # Scoring logic: High drop -> High Confidence
                optical_score = 0.5 
                if ndvi_drop > 0.15: optical_score = 1.0
                elif ndvi_drop > 0.05: optical_score = 0.8
                elif ndvi_after > 0.6: optical_score = 0.1 # Still green
                
                # Combine scores (Radar 60%, Optical 40%)
                combined_score = (alert['confidence_score'] * 0.6) + (optical_score * 0.4)
                
                alert.update({
                    'optical_score': optical_score,
                    'combined_score': combined_score,
                    'ndvi_drop': ndvi_drop
                })
                logger.success(f"    ✓ Optical confirmed: Drop={ndvi_drop:.3f}, Score={optical_score}")
            else:
                alert.update({
                    'optical_score': None,
                    'combined_score': alert['confidence_score'],
                    'ndvi_drop': None
                })
                logger.warning(f"    - No clear optical data. Using Radar score only.")
            
            final_alerts.append(alert)

        # ========================================================================
        # Step 7: Spatial Classification & Alert Storage
        # ========================================================================
        logger.info("\n[7/7] Classifying alerts and storing...")
        
        stored_alert_ids = []
        
        for alert in final_alerts:
            # Create GeoJSON polygon (simplified: point buffer)
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
            
            # Insert alert
            alert_data = {
                'detection_date': alert['detection_date'],
                'confidence_score': alert['confidence_score'],
                'area_hectares': config.TARGET_CLUSTER_HECTARES,
                'risk_tier': 'TIER_1',  # Will be updated by spatial join
                'boundary_id': None,
                'alt_vv_drop_db': alert['vv_drop_db'],
                'alt_vh_drop_db': alert['vh_drop_db'],
                'source_image_id': alert['source_image_id'],
                'optical_score': alert.get('optical_score'),
                'combined_score': alert.get('combined_score'),
                'ndvi_drop': alert.get('ndvi_drop'),
                'geom': json.dumps(geojson)
            }
            
            alert_id = db.insert_alert(alert_data)
            stored_alert_ids.append(alert_id)
        
        # Spatial join to classify by protected areas
        if stored_alert_ids:
            classified = db.spatial_join_alerts_to_boundaries(stored_alert_ids)
            
            tier2_count = sum(1 for a in classified.values() if a['risk_tier'] == 'TIER_2')
            logger.info(f"Spatial classification: {tier2_count} TIER 2 (protected), "
                       f"{len(stored_alert_ids) - tier2_count} TIER 1 (standard)")
            
            # TODO: Send notifications for TIER 2 alerts
        
        logger.success(f"✓ Stored {len(stored_alert_ids)} alerts to database")
        
        # ========================================================================
        # Pipeline Complete
        # ========================================================================
        logger.info("\n" + "="*80)
        logger.success("PIPELINE EXECUTION COMPLETE")
        logger.info(f"- Images processed: {len(unprocessed_images)}")
        logger.info(f"- ALT detections: {len(detections)}")
        logger.info(f"- MLP validated: {len(validated_alerts)}")
        logger.info(f"- Alerts stored: {len(stored_alert_ids)}")
        logger.info("="*80)
        
        return True
        
    except Exception as e:
        logger.exception(f"Pipeline failed with fatal error: {e}")
        return False





if __name__ == "__main__":
    """Run the pipeline"""
    import json
    
    success = run_pipeline()
    sys.exit(0 if success else 1)
