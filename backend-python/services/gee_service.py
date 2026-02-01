"""
Google Earth Engine Service
Handles Sentinel-1 SAR data acquisition and preprocessing using GEE Python API
"""

import ee
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from config import config
from db_utils import db


class GEEService:
    """Google Earth Engine service for Sentinel-1 SAR processing"""
    
    def __init__(self):
        self.initialized = False
        self._initialize_gee()
    
    def _initialize_gee(self):
        """Initialize Google Earth Engine with service account or user authentication"""
        try:
            # Check if using service account
            if config.GEE_SERVICE_ACCOUNT_EMAIL and config.GEE_PRIVATE_KEY_PATH:
                credentials = ee.ServiceAccountCredentials(
                    config.GEE_SERVICE_ACCOUNT_EMAIL,
                    config.GEE_PRIVATE_KEY_PATH
                )
                ee.Initialize(credentials)
                logger.success(f"✓ GEE initialized with service account: {config.GEE_SERVICE_ACCOUNT_EMAIL}")
            else:
                # Use default user authentication
                ee.Initialize()
                logger.success("✓ GEE initialized with user authentication")
            
            self.initialized = True
            
        except Exception as e:
            logger.error(f"✗ Failed to initialize Google Earth Engine: {e}")
            logger.warning("Run 'earthengine authenticate' if using user auth")
            self.initialized = False
            raise
    
    def get_aoi_geometry(
        self,
        country_name: str = None,
        state_name: str = None,
        district_name: str = None
    ) -> ee.Geometry:
        """Resolve AOI using FAO GAUL. Prefer Level 2 (district). Fall back to Level 1 only if needed."""
        
        country_name = country_name or config.AOI_COUNTRY or "Brazil"
        state_name = state_name or config.AOI_STATE or "Mato Grosso"
        district_name = district_name or config.AOI_DISTRICT or "Nova Santa Helena"

        if district_name:
            logger.info(
                f"Querying FAO GAUL Level 2 for AOI: {district_name}, {state_name}, {country_name}"
            )

            dataset_l2 = ee.FeatureCollection("FAO/GAUL/2015/level2")

            region = (
                dataset_l2
                .filter(ee.Filter.eq("ADM0_NAME", country_name))
                .filter(ee.Filter.eq("ADM1_NAME", state_name))
                .filter(ee.Filter.eq("ADM2_NAME", district_name))
                .first()
            )

            if region.getInfo():
                logger.success(
                    f"✓ Found boundary in GAUL Level 2: {district_name}"
                )
                return region.geometry()

            logger.warning(f"District {district_name} not found with strict filter, trying Level 2 district-only...")
            
            region_alt = dataset_l2.filter(ee.Filter.eq("ADM2_NAME", district_name)).first()
            if region_alt.getInfo():
                 logger.success(f"✓ Found boundary in GAUL Level 2 (district-only): {district_name}")
                 return region_alt.geometry()

            # Specific Fallback for Nova Santa Helena if GAUL fails
            if district_name == "Nova Santa Helena":
                logger.warning("Using fallback geometry for Nova Santa Helena")
                return ee.Geometry.Polygon([
                    [-55.35, -10.65], [-55.35, -10.95], 
                    [-55.05, -10.95], [-55.05, -10.65], 
                    [-55.35, -10.65]
                ])

            raise ValueError(
                f"District not found in GAUL Level 2: {district_name}"
            )

        # Fallback: State level
        logger.warning(
            f"No district provided or found. Falling back to GAUL Level 1: {state_name}"
        )

        dataset_l1 = ee.FeatureCollection("FAO/GAUL/2015/level1")

        region = (
            dataset_l1
            .filter(ee.Filter.eq("ADM0_NAME", country_name))
            .filter(ee.Filter.eq("ADM1_NAME", state_name))
            .first()
        )

        if not region.getInfo():
            raise ValueError(
                f"State not found in GAUL Level 1: {state_name}"
            )

        return region.geometry()

    


    
    def query_latest_images(
        self,
        aoi: ee.Geometry,
        days_back: int = 7,
        limit: int = 10,
        end_date: datetime = None
    ) -> List[Dict[str, Any]]:
    
        if end_date is None:
            end_date = datetime.utcnow()

        start_date = end_date - timedelta(days=days_back)

        collection = (
            ee.ImageCollection(config.S1_COLLECTION)
            .filterBounds(aoi)
            .filterDate(
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )
            .filter(ee.Filter.eq("instrumentMode", config.S1_INSTRUMENT_MODE))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
            .sort("system:time_start", False)
            .limit(limit)
        )

        if config.S1_ORBIT_PASS:
            collection = collection.filter(
                ee.Filter.eq("orbitProperties_pass", config.S1_ORBIT_PASS)
            )

        try:
            count = collection.size().getInfo()
            logger.info(f"Found {count} Sentinel-1 images in the last {days_back} days")

            if count == 0:
                return []

            # Convert images to Features with explicit properties
            features = collection.map(
                lambda img: ee.Feature(
                    img.geometry(),
                    {
                        "image_id": img.get("system:index"),
                        "time_start": img.get("system:time_start"),
                        "platform": img.get("platform_number"),
                        "orbit": img.get("orbitProperties_pass"),
                        "polarization": img.get("transmitterReceiverPolarisation"),
                    }
                )
            )

            feature_info = features.getInfo()["features"]

            images_metadata = []
            for f in feature_info:
                p = f["properties"]
                geom = f.get("geometry")

                images_metadata.append({
                    "image_id": p["image_id"],
                    "acquisition_date": datetime.fromtimestamp(
                        p["time_start"] / 1000
                    ),
                    "platform": p.get("platform", "Unknown"),
                    "orbit_direction": p.get("orbit", "Unknown"),
                    "polarization": ", ".join(p.get("polarization", [])),
                    "geom": json.dumps(geom) if geom else None,
                    "status": "PENDING"
                })

            return images_metadata

        except Exception as e:
            logger.exception("Sentinel-1 metadata extraction failed")
            raise



    def get_unprocessed_images(
        self,
        aoi: ee.Geometry,
        days_back: int = 7,
        end_date: datetime = None
    ) -> List[Dict[str, Any]]:
        """
        Get images that haven't been processed yet
        
        Args:
            aoi: Area of interest
            days_back: How far back to search
            end_date: End date for search
        
        Returns:
            List of unprocessed image metadata
        """
        # Get all recent images
        all_images = self.query_latest_images(aoi, days_back=days_back, limit=50, end_date=end_date)
        
        if not all_images:
            logger.info("No images found in the specified time range")
            return []
        
        # Check which ones are already processed
        processed_ids = set()
        for img in all_images:
            check_query = "SELECT image_id FROM processed_images WHERE image_id = %s"
            result = db.execute_query(check_query, (img['image_id'],))
            if result:
                processed_ids.add(img['image_id'])
        
        # Filter to unprocessed
        unprocessed = [img for img in all_images if img['image_id'] not in processed_ids]
        
        logger.info(f"Found {len(unprocessed)} unprocessed images (out of {len(all_images)} total)")
        
        return unprocessed
    
    def preprocess_image(
        self,
        image_id: str,
        aoi: ee.Geometry
    ) -> Tuple[ee.Image, ee.Image]:
        """
        Apply full preprocessing pipeline to a Sentinel-1 image
        
        Steps:
        1. Load image and clip to AOI
        2. Apply thermal noise removal (if available)
        3. Radiometric calibration to sigma0
        4. Terrain correction (gamma0)
        5. Signal stabilization (harmonic detrending)
        
        Args:
            image_id: Sentinel-1 image identifier
            aoi: Area of interest geometry
        
        Returns:
            Tuple of (preprocessed_image, stabilized_image)
        """
        try:
            # Load the image
            full_id = f"{config.S1_COLLECTION}/{image_id}"
            image = ee.Image(full_id)
            
            # CRITICAL: Clip to AOI BEFORE processing to reduce data volume
            image = image.clip(aoi)
            
            logger.info(f"Preprocessing image (Nova Santa Helena): {image_id}")
            
            # Select VV and VH polarizations
            vv = image.select('VV')
            vh = image.select('VH')
            
            # === 1. Radiometric Calibration ===
            # Convert from dB to linear power
            vv_linear = ee.Image(10).pow(vv.divide(10))
            vh_linear = ee.Image(10).pow(vh.divide(10))
            
            # === 2. Resample to 14.05m (Silva et al. 2022 specification) ===
            # GRD native resolution is ~10m, resample to match research
            vv_resampled = vv_linear.resample('bilinear').reproject(
                crs=vv_linear.projection().crs(),
                scale=14.05
            )
            vh_resampled = vh_linear.resample('bilinear').reproject(
                crs=vh_linear.projection().crs(),
                scale=14.05
            )
            
            # === 3. Terrain Correction (Gamma0) ===
            # GEE S1_GRD is already terrain-corrected to sigma0
            # Convert to gamma0 by dividing by cos(incidence angle)
            angle = image.select('angle').resample('bilinear').reproject(
                crs=image.select('angle').projection().crs(),
                scale=14.05
            )
            incidence_rad = angle.multiply(3.14159265359 / 180)
            
            vv_gamma = vv_resampled.divide(incidence_rad.cos())
            vh_gamma = vh_resampled.divide(incidence_rad.cos())
            
            # === 4. Speckle Filtering (Gamma-MAP per Silva et al. 2022) ===
            vv_filtered = self._gamma_map_filter(vv_gamma)
            vh_filtered = self._gamma_map_filter(vh_gamma)
            
            # Add date_string for metadata
            date = ee.Date(image.get('system:time_start'))
            date_string = date.format('YYYY-MM-dd')
            
            # Stack filtered bands - KEEP AS LINEAR for internal stabilization/filtering, 
            # but rename to clarify units if needed.
            preprocessed = ee.Image.cat([
                vv_filtered.rename('VV'),
                vh_filtered.rename('VH')
            ]).set({
                'system:time_start': image.get('system:time_start'),
                'system:index': image_id,
                'date_string': date_string,
                'image_id': image_id
            })
            
            # === 5. Harmonic Stabilization ===
            # This requires historical data, so we'll create a placeholder
            # In full implementation, fit a 2-year sinusoidal model
            stabilized = self._apply_harmonic_stabilization(preprocessed, aoi)
            
            logger.success(f"✓ Preprocessing complete for {image_id} at 14.05m resolution")
            
            return preprocessed, stabilized
            
        except Exception as e:
            logger.error(f"Preprocessing failed for {image_id}: {e}")
            raise
    
    def _gamma_map_filter(self, image: ee.Image, kernel_size: int = 7) -> ee.Image:
        """
        Apply Gamma-MAP speckle filter (Silva et al. 2022)
        
        Gamma-MAP is optimal for preserving edges while reducing speckle.
        It assumes a multiplicative speckle model and uses Maximum A Posteriori estimation.
        
        Args:
            image: Input image in linear units
            kernel_size: Filter window size (default: 7x7)
        
        Returns:
            Filtered image
        """
        # Define the kernel
        kernel = ee.Kernel.square(radius=(kernel_size - 1) / 2.0, units='pixels')
        
        # Calculate local statistics
        mean = image.reduceNeighborhood(
            reducer=ee.Reducer.mean(),
            kernel=kernel
        )
        
        variance = image.reduceNeighborhood(
            reducer=ee.Reducer.variance(),
            kernel=kernel
        )
        
        # Gamma-MAP parameters
        # ENL (Equivalent Number of Looks) for Sentinel-1 GRD: approximately 4.4
        enl = 4.4
        
        # Coefficient of variation for Gamma distribution
        cu = ee.Image.constant(1.0).divide(ee.Image.constant(enl).sqrt())
        cu2 = cu.multiply(cu)
        
        # Local coefficient of variation
        ci = variance.sqrt().divide(mean)
        ci2 = ci.multiply(ci)
        
        # Weight factor (Gamma-MAP formula)
        # w = (1 - cu2/ci2) / (1 + cu2)
        w = ee.Image.constant(1).subtract(cu2.divide(ci2)).divide(
            ee.Image.constant(1).add(cu2)
        )
        
        # Ensure weights are in valid range [0, 1]
        w = w.clamp(0, 1)
        
        # Apply filter: filtered = mean + w * (image - mean)
        filtered = mean.add(w.multiply(image.subtract(mean)))
        
        return filtered
    
    def _refined_lee_filter(self, image: ee.Image, kernel_size: int = 7) -> ee.Image:
        """
        Apply Refined Lee speckle filter (DEPRECATED)
        
        NOTE: Silva et al. (2022) uses Gamma-MAP filter.
        This method is kept for backward compatibility.
        Use _gamma_map_filter() instead.
        
        Args:
            image: Input SAR image (linear units)
            kernel_size: Filter kernel size (odd number)
        
        Returns:
            Filtered image
        """
        # Mean and variance in window
        mean = image.reduceNeighborhood(
            reducer=ee.Reducer.mean(),
            kernel=ee.Kernel.square(kernel_size / 2, 'pixels')
        )
        
        variance = image.reduceNeighborhood(
            reducer=ee.Reducer.variance(),
            kernel=ee.Kernel.square(kernel_size / 2, 'pixels')
        )
        
        # Lee filter weight calculation
        # w = variance / (variance + mean^2 * ENL^-1)
        # Assuming ENL (Equivalent Number of Looks) = 4 for Sentinel-1 GRD
        enl = 4.0
        weights = variance.divide(variance.add(mean.pow(2).divide(enl)))
        
        # Filtered = mean + weight * (original - mean)
        filtered = mean.add(weights.multiply(image.subtract(mean)))
        
        return filtered
    
    def _apply_harmonic_stabilization(
        self,
        image: ee.Image,
        aoi: ee.Geometry
    ) -> ee.Image:
        """
        Apply harmonic stabilization to remove seasonal variations
        
        Formula: S_stab = (S_orig - S_harmonic) + S_median
        
        Note: Full implementation requires 2-year historical data to fit sinusoidal model.
        This is a simplified version using recent median as baseline.
        
        Args:
            image: Preprocessed image
            aoi: Area of interest
        
        Returns:
            Stabilized image
        """
        # TODO: Implement full harmonic model fitting
        # For now, return the preprocessed image as-is
        # In production, this would:
        # 1. Fit S_harmonic = A*sin(2π*t/365 + φ) + B using 2 years of data
        # 2. Calculate S_median from historical observations
        # 3. Apply stabilization formula
        
        logger.debug("Harmonic stabilization placeholder (requires historical data)")
        
        return image.set('harmonically_stabilized', False)
    
    def extract_backscatter_statistics(
        self,
        image: ee.Image,
        aoi: ee.Geometry
    ) -> ee.FeatureCollection:
        """
        Extract backscatter statistics using a Change-First strategy.
        """
        logger.info("Executing Change-First detection pipeline...")
        
        # 1. Historical Baseline (6 months before target)
        baseline = self._create_baseline(aoi, image.get('system:time_start'))
        
        # 2. Change Mask (Delta detection)
        change_mask = self._detect_change_mask(image, baseline, aoi)
        
        # 3. Generate Candidate Patches (Sample points where change exists)
        candidate_patches = self._generate_candidate_patches(change_mask, aoi)
        
        # Check if we have any candidates
        count = candidate_patches.size().getInfo()
        if count == 0:
            logger.warning("No change candidates detected. Returning empty collection.")
            return ee.FeatureCollection([])
            
        logger.info(f"Detected {count} candidate change patches. Extracting features...")

        return self._run_statistical_extraction(image, candidate_patches, baseline)

    def _get_combined_reducer(self):
        """Standard reducer for backscatter statistics"""
        return (ee.Reducer.mean().setOutputs(['mean'])
            .combine(ee.Reducer.stdDev().setOutputs(['std']), sharedInputs=True)
            .combine(ee.Reducer.median().setOutputs(['median']), sharedInputs=True)
            .combine(ee.Reducer.minMax().setOutputs(['min', 'max']), sharedInputs=True)
            .combine(ee.Reducer.count().setOutputs(['pixel_count']), sharedInputs=True))

    def _run_statistical_extraction(self, image, patches, baseline=None):
        """Internal helper to run reduceRegions and format results"""
        # Defensive cast: ensure image is ee.Image, not Element
        image = ee.Image(image)
        if baseline is not None:
            baseline = ee.Image(baseline)
        
        reducer = self._get_combined_reducer()
        
        # Build image for extraction
        if baseline:
            stats_image = ee.Image.cat([
                image.select(['VV', 'VH']).rename(['vv', 'vh']),
                baseline.select(['VV', 'VH']).rename(['vv_baseline', 'vh_baseline'])
            ])
        else:
            stats_image = image.select(['VV', 'VH']).rename(['vv', 'vh'])

        # CRITICAL: Extract image metadata BEFORE reduceRegions to ensure we're working with ee.Image
        # This must happen before any Feature operations to avoid type confusion
        img_id = image.get('system:index')
        # Use ee.Date() on the property directly instead of image.date() to allow Feature/Element types
        img_date = ee.Date(image.get('system:time_start')).format('YYYY-MM-dd')
        img_time = image.get('system:time_start')
        
        # Now perform the statistical extraction at 14.05m resolution (Silva et al. 2022)
        results = stats_image.reduceRegions(
            collection=patches,
            reducer=reducer,
            scale=14.05,
            crs=image.select(0).projection()
        )

        def add_metadata(feature):
            f = ee.Feature(feature)
            props = f.toDictionary()
            centroid = f.geometry().centroid(1)
            coords = centroid.coordinates()
            lon = ee.Number(coords.get(0))
            lat = ee.Number(coords.get(1))
            
            # Global replace for literal dots in grid ID
            grid_id = ee.String('patch_').cat(lat.format('%.4f')).cat('_').cat(lon.format('%.4f')).replace(r'\.', '_', 'g')
            
            # CRITICAL FIX: MMD = Maximum - Minimum Difference (Silva et al. 2022)
            # This measures signal range, NOT distribution skew
            vv_max = ee.Number(props.get('vv_max', 0))
            vv_min = ee.Number(props.get('vv_min', 0))
            vh_max = ee.Number(props.get('vh_max', 0))
            vh_min = ee.Number(props.get('vh_min', 0))
            
            vv_mmd = vv_max.subtract(vv_min)  # Max - Min (signal range)
            vh_mmd = vh_max.subtract(vh_min)  # Max - Min (signal range)
            
            return f.set({
                'grid_cell_id': props.get('grid_cell_id', grid_id),
                'lon': props.get('lon', lon),
                'lat': props.get('lat', lat),
                'vv_mmd': vv_mmd,
                'vh_mmd': vh_mmd,
                'pixel_count': props.get('vv_pixel_count', props.get('pixel_count', 0)),
                'source_image_id': img_id,
                'observation_date': img_date,
                'system:time_start': img_time
            })

        return results.map(add_metadata)

    def extract_historical_statistics(
        self,
        patches: ee.FeatureCollection,
        target_date: datetime,
        days_back: int = 180
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract historical backscatter for a set of patches to build a baseline.
        Returns:
            Tuple of (statistics_list, image_metadata_list)
        """
        logger.info(f"Backfilling {days_back} days of history for {patches.size().getInfo()} patches...")
        
        end_date = target_date
        start_date = end_date - timedelta(days=days_back)
        
        collection = (ee.ImageCollection(config.S1_COLLECTION)
            .filterBounds(patches.geometry())
            .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            .filter(ee.Filter.eq('instrumentMode', config.S1_INSTRUMENT_MODE))
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
            .sort('system:time_start'))

        reducer = (ee.Reducer.mean().setOutputs(['mean'])
            .combine(ee.Reducer.stdDev().setOutputs(['std']), sharedInputs=True)
            .combine(ee.Reducer.median().setOutputs(['median']), sharedInputs=True)
            .combine(ee.Reducer.minMax().setOutputs(['min', 'max']), sharedInputs=True)
            .combine(ee.Reducer.count().setOutputs(['pixel_count']), sharedInputs=True))

        def process_image(img):
            # Cleanly cast to Image
            img = ee.Image(img)
            # Convert to linear power (standard S1 preprocessing)
            vv_linear = ee.Image(10).pow(img.select('VV').divide(10)).rename('VV')
            vh_linear = ee.Image(10).pow(img.select('VH').divide(10)).rename('VH')
            
            # Combine bands and preserve essential system metadata
            # CRITICAL: Double-cast to ee.Image after copyProperties to fix Element type issue
            linear_img = img.select().addBands([vv_linear, vh_linear]).copyProperties(img, ['system:time_start', 'system:index'])
            linear_img = ee.Image(linear_img)  # Explicit cast to ensure ee.Image type
            
            # Reuse the safe statistical extraction helper
            return self._run_statistical_extraction(linear_img, patches)

        def extract_image_metadata(img):
            # Extract minimal metadata needed for processed_images table
            return ee.Feature(None, {
                'image_id': img.get('system:index'),
                'acquisition_date': ee.Date(img.get('system:time_start')).format('YYYY-MM-dd'),
                'platform': img.get('platform_number'),
                'orbit_direction': img.get('orbitProperties_pass'),
                'polarization': img.get('transmitterReceiverPolarisation'),
                'status': 'PROCESSED' # Mark as processed since we're using it for history
            })

        try:
            # 1. Extract Metadata for all images in collection (for FK constraint)
            logger.info("Extracting metadata for historical images...")
            meta_features = collection.map(extract_image_metadata).getInfo()['features']
            
            image_metadata_list = []
            for f in meta_features:
                p = f['properties']
                image_metadata_list.append({
                    'image_id': p['image_id'],
                    'acquisition_date': datetime.strptime(p['acquisition_date'], '%Y-%m-%d'),
                    'platform': p.get('platform', 'Sentinel-1'),
                    'orbit_direction': p.get('orbit_direction', 'ASCENDING'),
                    'polarization': ", ".join(p.get('polarization', ['VV', 'VH'])),
                    'status': 'PROCESSED',
                    'geom': None # We don't need footprint for historical background images
                })

            # 2. Extract Statistics
            # Map extraction over the collection and flatten
            historical_stats = collection.map(process_image).flatten()
            features = historical_stats.getInfo()['features']
            results = []
            for f in features:
                p = f['properties']
                # Correctly handle band renaming from _run_statistical_extraction
                results.append({
                    'grid_cell_id': p['grid_cell_id'],
                    'observation_date': p['observation_date'],
                    'vv_mean': p.get('mean') if 'mean' in p else p.get('vv_mean'),
                    'vh_mean': p.get('vh_mean'),
                    'vv_std': p.get('std') if 'std' in p else p.get('vv_std'),
                    'vh_std': p.get('vh_std'),
                    'vv_median': p.get('median') if 'median' in p else p.get('vv_median'),
                    'vh_median': p.get('vh_median'),
                    'vv_mmd': p.get('vv_mmd', 0),
                    'vh_mmd': p.get('vh_mmd', 0),
                    'pixel_count': p.get('pixel_count', 0),
                    'lon': p['lon'],
                    'lat': p['lat'],
                    'source_image_id': p['source_image_id']
                })
            
            return results, image_metadata_list
            
        except Exception as e:
            logger.error(f"Historical extraction failed: {e}")
            return [], []

    def _create_baseline(self, aoi: ee.Geometry, target_time_ms: ee.Number) -> ee.Image:
        """
        Create a historical baseline (median) for the given AOI.
        Uses 6 months of data preceding the target time.
        """
        end_date = ee.Date(target_time_ms)
        start_date = end_date.advance(-6, 'month')
        
        # Explicit info for logging to avoid date string artifacts
        date_range_str = f"{start_date.format('YYYY-MM-dd').getInfo()} to {end_date.format('YYYY-MM-dd').getInfo()}"
        logger.info(f"Creating historical baseline from {date_range_str}")
        
        # Collection for baseline - Filter same orbit/properties as current logic
        collection = (ee.ImageCollection(config.S1_COLLECTION)
            .filterBounds(aoi)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.eq('instrumentMode', config.S1_INSTRUMENT_MODE))
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')))

        # Apply basic preprocessing to each image in collection (linear median is safer)
        def to_linear(img):
            # Simple linear conversion for baseline median
            vv = ee.Image(10).pow(img.select('VV').divide(10))
            vh = ee.Image(10).pow(img.select('VH').divide(10))
            return img.select().addBands([vv.rename('VV'), vh.rename('VH')])

        linear_col = collection.map(to_linear)
        baseline = linear_col.median()
        
        return baseline

    def _detect_change_mask(self, image: ee.Image, baseline: ee.Image, aoi: ee.Geometry) -> ee.Image:
        """
        Pixel-level change detection using thresholded deltas in Log-Domain (dB).
        """
        # CRITICAL FIX: Convert current image and baseline to dB for subtraction
        # Previously subtracting linear decimals (0.1 - 0.15 = -0.05) vs -0.3 threshold
        # always resulted in zero candidates.
        image_db = image.select(['VV', 'VH']).log10().multiply(10)
        baseline_db = baseline.select(['VV', 'VH']).log10().multiply(10)
        
        delta_vv = image_db.select('VV').subtract(baseline_db.select('VV'))
        delta_vh = image_db.select('VH').subtract(baseline_db.select('VH'))
        
        # Thresholds (Calibrated for Amazon/Cerrado clear-cuts)
        # In these regions, deforestation is typically a complete removal of biomass.
        T_VV = -2.5 # Stronger drop in VV
        T_VH = -3.5 # Stronger drop in VH
        
        change_mask = delta_vv.lt(T_VV).And(delta_vh.lt(T_VH))
        
        # Morphological Cleanup: Simplified to preserve small signals
        # Remove single pixels but keep components >= 2 pixels
        objects = change_mask.selfMask().connectedPixelCount(maxSize=10, eightConnected=True)
        final_mask = change_mask.updateMask(objects.gte(2)) 
        
        return final_mask

    def _generate_candidate_patches(self, mask: ee.Image, aoi: ee.Geometry) -> ee.FeatureCollection:
        """
        Sample points from the change mask and convert to fixed-size patches.
        """
        # Sample points from the mask
        # scale=10 matches S1 resolution
        # numPixels cap ensures we never exceed GEE limits
        points = mask.selfMask().sample(
            region=aoi,
            scale=10,
            numPixels=500, # MAX CAP: We don't want more than 500 alerts per image usually
            geometries=True
        )
        
        def to_patch(f):
            # Buffer by 50m (approx 10x10 pixel bounding box)
            # and convert to rectangle (patch)
            return ee.Feature(f.geometry().buffer(50).bounds(), f.toDictionary())
            
        patches = points.map(to_patch)
        
        # Dissolve overlapping patches to avoid identical duplicates
        # and keep the unit of analysis consistent.
        # However, for near-real-time monitoring, keeping them distinct but filtered 
        # is often better for localization. We use a simple union or keep as is.
        return patches
    
    def _tile_geometry(self, aoi: ee.Geometry, tile_size_deg: float = 0.1) -> List[ee.Geometry]:
        """
        Split a geometry into smaller tiles efficiently.
        """
        # ... logic preserved from previous implementation ...
        coords = aoi.bounds().coordinates().get(0).getInfo()
        min_lon, max_lon = min([c[0] for c in coords]), max([c[0] for c in coords])
        min_lat, max_lat = min([c[1] for c in coords]), max([c[1] for c in coords])
        
        import math
        lon_steps = math.ceil((max_lon - min_lon) / tile_size_deg)
        lat_steps = math.ceil((max_lat - min_lat) / tile_size_deg)
        
        all_tile_features = []
        for i in range(lon_steps):
            for j in range(lat_steps):
                tile = ee.Geometry.Rectangle([
                    min_lon + i * tile_size_deg,
                    min_lat + j * tile_size_deg,
                    min(min_lon + (i+1) * tile_size_deg, max_lon),
                    min(min_lat + (j+1) * tile_size_deg, max_lat)
                ])
                all_tile_features.append(ee.Feature(tile))
        
        # Server-side filter for intersection
        tiles_fc = ee.FeatureCollection(all_tile_features)
        intersecting_tiles = tiles_fc.filterBounds(aoi)
        
        tiles_info = intersecting_tiles.getInfo()['features']
        return [ee.Geometry(f['geometry']) for f in tiles_info]

    def extract_optical_data(
        self,
        patch_geometry: ee.Geometry,
        target_date: datetime,
        days_buffer: int = 15
    ) -> Dict[str, float]:
        """
        Extract optical data (NDVI) for a specific patch (Sentinel-2).
        Used for validation of alerts.
        
        Args:
            patch_geometry: Geometry of the alert patch
            target_date: Date of the radar alert
            days_buffer: Search window (+/- days)
        
        Returns:
            Dictionary with NDVI statistics (pre, post, drop)
        """
        # Define date range for optical search specifically AFTER the alert (to confirm bare ground)
        # and BEFORE (to confirm forest)
        
        alert_date_ee = ee.Date(target_date.strftime('%Y-%m-%d'))
        
        # Look for "After" image (0 to +30 days) to see if it's cleared
        after_start = alert_date_ee
        after_end = alert_date_ee.advance(30, 'day')
        
        # Look for "Before" image (-60 to -5 days) to ensure it was forest
        before_end = alert_date_ee.advance(-5, 'day')
        before_start = alert_date_ee.advance(-60, 'day')
        
        def get_best_ndvi(start, end):
            collection = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                         .filterBounds(patch_geometry)
                         .filterDate(start, end)
                         .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
                         .map(self._mask_s2_clouds))
            
            # We want the clearest image
            # Mosaic is risky if clouds persist, but median is robust for stable periods
            # For "change detection", we ideally want single clear scenes.
            # Let's use max NDVI (assuming forest > cloud/shadow in NDVI) to reduce noise?
            # No, deforestation drops NDVI. Max NDVI would hide deforestation.
            # We use Median to remove transient clouds/shadows if we have multiple images.
            image = collection.median()
            
            # Compute NDVI
            ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
            
            # Reduce region
            stats = ndvi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=patch_geometry,
                scale=10,
                maxPixels=1e5
            )
            return stats.get('NDVI')

        ndvi_before = get_best_ndvi(before_start, before_end)
        ndvi_after = get_best_ndvi(after_start, after_end)
        
        # Calculate generic S2 metadata
        # Since getInfo is expensive, we return an EE object structure or resolve it here?
        # The pipeline loop calls this for specific alerts, so resolving (validating) one by one is acceptable 
        # but slow if many alerts.
        # User constraint: "Sentinel-2 queries are cached" / "Optical validation runs only on confirmed patches"
        # Since this is Python pipeline, we'll effectively resolve it.
        
        try:
            # Resolve values
            res = ee.Dictionary({
                'ndvi_before': ndvi_before,
                'ndvi_after': ndvi_after
            }).getInfo()
            
            pre = res.get('ndvi_before')
            post = res.get('ndvi_after')
            
            if pre is None or post is None:
                return None
                
            return {
                'ndvi_before': pre,
                'ndvi_after': post,
                'ndvi_drop': pre - post
            }
            
        except Exception as e:
            logger.warning(f"Optical extraction failed: {e}")
            return None

    def _mask_s2_clouds(self, image: ee.Image) -> ee.Image:
        """Mask clouds in Sentinel-2 using QA60 band"""
        qa = image.select('QA60')
        
        # Bits 10 and 11 are clouds and cirrus, respectively.
        cloudBitMask = 1 << 10
        cirrusBitMask = 1 << 11
        
        # Both flags should be set to zero, indicating clear conditions.
        mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
        
        return image.updateMask(mask).divide(10000)


# Global GEE service instance
try:
    gee_service = GEEService()
except Exception as e:
    logger.warning(f"GEE service initialization failed: {e}")
    gee_service = None


if __name__ == "__main__":
    """Test GEE service"""
    import sys
    from loguru import logger
    
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    if gee_service and gee_service.initialized:
        try:
            # Test AOI loading (Nova Santa Helena, Mato Grosso, Brazil)
            country = "Brazil"
            state = "Mato Grosso"
            district = "Nova Santa Helena"
            aoi = gee_service.get_aoi_geometry(country, state, district)
            logger.success(f"✓ AOI loaded: {district}")
            
            # Test tiling logic
            area_km2 = aoi.area().divide(1e6).getInfo()
            logger.info(f"AOI Area: {area_km2:.1f} km^2")
            
            if area_km2 > 500:
                tiles = gee_service._tile_geometry(aoi)
                logger.info(f"Tiling result: {len(tiles)} tiles")
            
            # Test image query within target window (2023-02-28 to 2023-08-31)
            target_test_date = datetime(2023, 8, 1)
            images = gee_service.query_latest_images(aoi, days_back=10, limit=1, end_date=target_test_date)
            
            if images:
                img_metadata = images[0]
                logger.info(f"Testing extraction for: {img_metadata['image_id']} (Date: {img_metadata['acquisition_date']})")
                
                # Preprocess
                pre, stab = gee_service.preprocess_image(img_metadata['image_id'], aoi)
                
                # Extract
                stats = gee_service.extract_backscatter_statistics(stab, aoi) 
                
                count = stats.size().getInfo()
                logger.success(f"✓ Extracted {count} candidate patches")
                
                if count > 0:
                    first = stats.first().getInfo()['properties']
                    logger.info(f"Sample data: {first}")
            
        except Exception as e:
            logger.exception(f"Test failed: {e}")
            sys.exit(1)
    else:
        logger.error("GEE service not initialized")
        sys.exit(1)
