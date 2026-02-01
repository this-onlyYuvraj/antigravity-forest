"""
Adaptive Linear Thresholding (ALT) Detector
Primary pass algorithm for detecting sudden backscatter drops indicating deforestation
"""

import numpy as np
from typing import List, Dict, Any, Tuple
from loguru import logger
from config import config


class ALTDetector:
    """
    Adaptive Linear Thresholding detector for deforestation
    
    Detects sudden drops in SAR backscatter compared to historical baseline,
    with threshold modulation based on proximity to previous disturbances.
    """
    
    def __init__(
        self,
        vv_threshold_db: float = None,
        vh_threshold_db: float = None,
        min_observations: int = 30
    ):
        """
        Initialize ALT detector
        
        Args:
            vv_threshold_db: VV backscatter drop threshold in dB (negative value)
            vh_threshold_db: VH backscatter drop threshold in dB (negative value)
            min_observations: Minimum historical observations required for baseline
        """
        self.vv_threshold = vv_threshold_db or config.ALT_THRESHOLD_VV  # e.g., -2.0 dB
        self.vh_threshold = vh_threshold_db or config.ALT_THRESHOLD_VH  # e.g., -2.3 dB
        self.min_observations = min_observations
        
        logger.info(f"ALT Detector initialized: VV={self.vv_threshold}dB, VH={self.vh_threshold}dB")
    
    def calculate_baseline(
        self,
        historical_data: List[Dict[str, float]]
    ) -> Dict[str, float]:
        """
        Calculate baseline statistics from historical backscatter observations
        
        Args:
            historical_data: List of dicts with 'vv_mean', 'vh_mean' keys
        
        Returns:
            Dict with baseline statistics (median, std, etc.)
        """
        if len(historical_data) < self.min_observations:
            raise ValueError(
                f"Insufficient historical data: {len(historical_data)} < {self.min_observations}"
            )
        
        # Extract time series
        vv_series = np.array([obs['vv_mean'] for obs in historical_data])
        vh_series = np.array([obs['vh_mean'] for obs in historical_data])
        
        # Calculate baseline statistics
        baseline = {
            'vv_median': np.median(vv_series),
            'vv_std': np.std(vv_series),
            'vv_mean': np.mean(vv_series),
            'vh_median': np.median(vh_series),
            'vh_std': np.std(vh_series),
            'vh_mean': np.mean(vh_series),
            'n_observations': len(historical_data)
        }
        
        logger.debug(f"Baseline calculated from {len(historical_data)} observations")
        return baseline
    
    def _detect_pattern_signature(
        self,
        historical_data: List[Dict[str, float]],
        current_vv_db: float,
        current_vh_db: float,
        baseline_vv_db: float,
        baseline_vh_db: float
    ) -> Tuple[bool, float]:
        """
        Detect the deforestation signature: brief increase followed by sharp drop (Silva et al. 2022)
        
        Args:
            historical_data: Recent historical observations (last 3-4 before current)
            current_vv_db: Current VV in dB
            current_vh_db: Current VH in dB
            baseline_vv_db: Baseline VV in dB
            baseline_vh_db: Baseline VH in dB
        
        Returns:
            Tuple of (has_pattern, pattern_confidence)
        """
        if len(historical_data) < 3:
            # Not enough data to detect pattern
            return False, 0.0
        
        # Get last 3-4 observations before current
        recent_obs = historical_data[-4:] if len(historical_data) >= 4 else historical_data[-3:]
        
        # Convert to dB
        vv_series_db = [10 * np.log10(obs['vv_mean']) if obs['vv_mean'] > 0 else -40 for obs in recent_obs]
        vh_series_db = [10 * np.log10(obs['vh_mean']) if obs['vh_mean'] > 0 else -40 for obs in recent_obs]
        
        # Check for increase from baseline before the drop
        # Pattern: baseline -> increase -> sharp drop
        vv_had_increase = any(val > baseline_vv_db + 0.5 for val in vv_series_db)  # 0.5 dB increase
        vh_had_increase = any(val > baseline_vh_db + 0.5 for val in vh_series_db)
        
        # Check if current shows the drop
        vv_current_drop = current_vv_db < baseline_vv_db + self.vv_threshold
        vh_current_drop = current_vh_db < baseline_vh_db + self.vh_threshold
        
        # Pattern detected if we had increase followed by current drop
        has_pattern = (vv_had_increase or vh_had_increase) and (vv_current_drop and vh_current_drop)
        
        # Calculate pattern confidence (0.0 to 1.0)
        if has_pattern:
            # Higher confidence if both polarizations show the pattern
            confidence = 0.7 + (0.3 if (vv_had_increase and vh_had_increase) else 0.0)
        else:
            confidence = 0.0
        
        return has_pattern, confidence
    
    def detect_drop(
        self,
        current_vv: float,
        current_vh: float,
        baseline: Dict[str, float],
        proximity_factor: float = 1.0,
        historical_data: List[Dict[str, float]] = None
    ) -> Tuple[bool, Dict[str, float]]:
        """
        Detect if current observation shows significant backscatter drop
        
        Enhanced with pattern detection per Silva et al. (2022):
        - Detects "increase then sharp drop" signature
        - Uses pattern confidence to enhance detection
        
        Args:
            current_vv: Current VV backscatter (linear units)
            current_vh: Current VH backscatter (linear units)
            baseline: Baseline statistics from historical data
            proximity_factor: Multiplier to adjust threshold based on distance to clearings
                             (1.0 = standard, <1.0 = more sensitive near clearings)
            historical_data: Optional recent observations for pattern detection
        
        Returns:
            Tuple of (is_detection, metadata_dict)
        """
        # Convert linear to dB
        current_vv_db = 10 * np.log10(current_vv) if current_vv > 0 else -40
        current_vh_db = 10 * np.log10(current_vh) if current_vh > 0 else -40
        
        baseline_vv_db = 10 * np.log10(baseline['vv_median']) if baseline['vv_median'] > 0 else -40
        baseline_vh_db = 10 * np.log10(baseline['vh_median']) if baseline['vh_median'] > 0 else -40
        
        # Calculate drops
        vv_drop_db = current_vv_db - baseline_vv_db
        vh_drop_db = current_vh_db - baseline_vh_db
        
        # Pattern detection (Silva et al. 2022: increase then sharp drop)
        has_pattern = False
        pattern_confidence = 0.0
        if historical_data and len(historical_data) >= 3:
            has_pattern, pattern_confidence = self._detect_pattern_signature(
                historical_data, current_vv_db, current_vh_db, baseline_vv_db, baseline_vh_db
            )
        
        # Apply proximity-based threshold modulation
        effective_vv_threshold = self.vv_threshold * proximity_factor
        effective_vh_threshold = self.vh_threshold * proximity_factor
        
        # Detection logic: drop must be below threshold in at least VH
        # (VH is more sensitive to vegetation changes)
        vv_detection = vv_drop_db < effective_vv_threshold
        vh_detection = vh_drop_db < effective_vh_threshold
        
        # Primary criterion: VH drop
        # Secondary: combined VH + VV
        # Enhanced: Pattern detection boosts confidence
        is_detection = vh_detection and (vv_detection or vh_drop_db < (effective_vh_threshold * 1.2))
        
        # If pattern detected, slightly relax threshold (pattern confidence acts as boost)
        if has_pattern and pattern_confidence > 0.5:
            # Pattern gives us more confidence, so borderline cases can be accepted
            is_detection = is_detection or (vh_drop_db < (effective_vh_threshold * 1.4) and vv_drop_db < (effective_vv_threshold * 1.4))
        
        metadata = {
            'vv_drop_db': float(vv_drop_db),
            'vh_drop_db': float(vh_drop_db),
            'vv_current_db': float(current_vv_db),
            'vh_current_db': float(current_vh_db),
            'vv_baseline_db': float(baseline_vv_db),
            'vh_baseline_db': float(baseline_vh_db),
            'vv_threshold_applied': float(effective_vv_threshold),
            'vh_threshold_applied': float(effective_vh_threshold),
            'proximity_factor': float(proximity_factor),
            'vv_detection': bool(vv_detection),
            'vh_detection': bool(vh_detection),
            'has_pattern': bool(has_pattern),
            'pattern_confidence': float(pattern_confidence),
            'combined_detection': bool(is_detection)
        }
        
        if is_detection:
            pattern_str = f" [PATTERN: {pattern_confidence:.2f}]" if has_pattern else ""
            logger.debug(f"Detection: VV drop={vv_drop_db:.2f}dB, VH drop={vh_drop_db:.2f}dB{pattern_str}")
        
        return is_detection, metadata
    
    def calculate_proximity_factor(
        self,
        distance_to_clearing_meters: float,
        max_distance: float = 5000.0
    ) -> float:
        """
        Calculate proximity-based threshold modulation factor
        
        Uses polynomial decay to increase sensitivity near existing clearings.
        
        Args:
            distance_to_clearing_meters: Distance to nearest known clearing
            max_distance: Distance beyond which factor = 1.0 (no modulation)
        
        Returns:
            Proximity factor (0.7 to 1.0)
        """
        if distance_to_clearing_meters >= max_distance:
            return 1.0
        
        # Normalize distance to [0, 1]
        d_norm = distance_to_clearing_meters / max_distance
        
        # Polynomial decay: factor = 0.7 + 0.3 * d_norm^2
        # At d=0: factor=0.7 (30% more sensitive)
        # At d=max: factor=1.0 (standard sensitivity)
        factor = 0.7 + 0.3 * (d_norm ** 2)
        
        return factor
    
    def batch_detect(
        self,
        observations: List[Dict[str, Any]],
        baseline_data: Dict[str, List[Dict[str, float]]],
        proximity_data: Dict[str, float] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect deforestation in a batch of grid cell observations
        
        Args:
            observations: List of current observations with grid_cell_id, vv_mean, vh_mean
            baseline_data: Dict mapping grid_cell_id to historical observations
            proximity_data: Dict mapping grid_cell_id to distance to nearest clearing
        
        Returns:
            List of detections with metadata
        """
        detections = []
        proximity_data = proximity_data or {}
        
        for obs in observations:
            grid_id = obs['grid_cell_id']
            
            # Check if we have baseline data
            if grid_id not in baseline_data:
                logger.debug(f"Skipping {grid_id}: Initial establishment phase (No baseline yet)")
                continue
            
            historical = baseline_data[grid_id]
            
            if len(historical) < self.min_observations:
                logger.debug(f"Skipping {grid_id}: Cold Start in progress ({len(historical)}/{self.min_observations} observations)")
                continue
            
            # Calculate baseline
            try:
                baseline = self.calculate_baseline(historical)
            except ValueError as e:
                logger.warning(f"Baseline calculation failed for {grid_id}: {e}")
                continue
            
            # Get proximity factor
            distance = proximity_data.get(grid_id, 10000.0)  # Default: far from clearings
            proximity_factor = self.calculate_proximity_factor(distance)
            
            # The `historical` variable already contains the historical data for the current `grid_id`.
            # We can pass this directly for pattern detection.
            patch_history = historical 
            
            # Detect
            is_detection, metadata = self.detect_drop(
                current_vv=obs['vv_mean'],
                current_vh=obs['vh_mean'],
                baseline=baseline,
                proximity_factor=proximity_factor,
                historical_data=patch_history  # Pass history for pattern detection
            )
            
            if is_detection:
                detection = {
                    'grid_cell_id': grid_id,
                    'latitude': obs.get('lat'),
                    'longitude': obs.get('lon'),
                    'detection_date': obs.get('observation_date'),
                    'source_image_id': obs.get('source_image_id'),
                    **metadata
                }
                detections.append(detection)
        
        logger.info(f"ALT detected {len(detections)} candidates from {len(observations)} observations")
        
        return detections
    
    def persistence_check(
        self,
        detection: Dict[str, Any],
        next_observation: Dict[str, float],
        baseline: Dict[str, float]
    ) -> bool:
        """
        Check if detection persists in next satellite pass
        
        Args:
            detection: Initial detection metadata
            next_observation: Observation from next satellite pass (6-12 days later)
            baseline: Historical baseline statistics
        
        Returns:
            True if drop persists, False if recovered
        """
        # Re-run detection on next observation
        is_persistent, _ = self.detect_drop(
            current_vv=next_observation['vv_mean'],
            current_vh=next_observation['vh_mean'],
            baseline=baseline,
            proximity_factor=detection.get('proximity_factor', 1.0)
        )
        
        if is_persistent:
            logger.debug(f"Detection persists in follow-up observation")
        else:
            logger.debug(f"Detection did not persist (possible false positive)")
        
        return is_persistent


# Test function
def test_alt_detector():
    """Test the ALT detector with synthetic data"""
    detector = ALTDetector()
    
    # Synthetic historical data (stable forest)
    # VV ~ -11 dB (linear: 0.0794), VH ~ -18 dB (linear: 0.0158)
    historical = [
        {'vv_mean': 0.08 + np.random.normal(0, 0.005), 'vh_mean': 0.016 + np.random.normal(0, 0.002)}
        for _ in range(40)
    ]
    
    baseline = detector.calculate_baseline(historical)
    print(f"Baseline: VV={10*np.log10(baseline['vv_median']):.2f}dB, "
          f"VH={10*np.log10(baseline['vh_median']):.2f}dB")
    
    # Test cases
    test_cases = [
        ("Stable forest", 0.08, 0.016),
        ("Clear-cut (strong)", 0.02, 0.004),  # ~6 dB drop
        ("Degradation (weak)", 0.05, 0.010),  # ~2-3 dB drop
        ("Minor variation", 0.07, 0.014),     # <2 dB drop
    ]
    
    for name, vv, vh in test_cases:
        is_det, meta = detector.detect_drop(vv, vh, baseline)
        print(f"{name}: VV drop={meta['vv_drop_db']:.2f}dB, "
              f"VH drop={meta['vh_drop_db']:.2f}dB -> Detected: {is_det}")


if __name__ == "__main__":
    test_alt_detector()
