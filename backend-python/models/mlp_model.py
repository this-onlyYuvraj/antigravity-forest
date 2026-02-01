"""
Multi-Layer Perceptron (MLP) Model for Deforestation Validation
Case 4 Configuration: 180 inputs -> 40 -> 10 -> 1 (Sigmoid output)
"""

import numpy as np
from typing import List, Dict, Any, Tuple
from loguru import logger
from config import config
import os

# Use TensorFlow/Keras for MLP
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, models
    HAS_TENSORFLOW = True
except ImportError:
    logger.warning("TensorFlow not available. MLP functionality will be limited.")
    HAS_TENSORFLOW = False


class MLPModel:
    """
    Multi-Layer Perceptron for deforestation detection validation
    
    Architecture (Case 4):
    - Input: 180 features (Mean + SD + MMD for VV and VH over 30 temporal observations)
    - Hidden Layer 1: 40 units, ReLU activation
    - Hidden Layer 2: 10 units, ReLU activation
    - Output: 1 unit, Sigmoid activation (probability 0.0-1.0)
    """
    
    def __init__(self, model_path: str = None):
        """
        Initialize MLP model
        
        Args:
            model_path: Path to saved model weights (optional)
        """
        self.model = None
        self.model_path = model_path or str(config.MLP_MODEL_PATH)
        self.input_size = config.MLP_INPUT_SIZE
        self.hidden_layers = config.MLP_HIDDEN_LAYERS
        self.threshold = config.MLP_CONFIDENCE_THRESHOLD
        
        if not HAS_TENSORFLOW:
            logger.error("TensorFlow not installed. Cannot use MLP model.")
            return
        
        # Try to load existing model, otherwise create new
        if os.path.exists(self.model_path):
            self.load_model()
        else:
            logger.info("No pre-trained model found. Creating new model architecture.")
            self.build_model()
    
    def build_model(self):
        """Build the MLP architecture"""
        if not HAS_TENSORFLOW:
            return
        
        model = models.Sequential([
            # Input layer (180 features, normalized 0-1)
            layers.Input(shape=(self.input_size,)),
            
            # Hidden layer 1: 40 units, ReLU activation
            layers.Dense(self.hidden_layers[0], activation='relu', name='hidden1'),
            layers.Dropout(0.2, name='dropout1'),  # Regularization
            
            # Hidden layer 2: 10 units, ReLU activation
            layers.Dense(self.hidden_layers[1], activation='relu', name='hidden2'),
            layers.Dropout(0.1, name='dropout2'),
            
            # Output layer: 1 unit, Sigmoid activation
            layers.Dense(1, activation='sigmoid', name='output')
        ])
        
        # Compile model
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy', keras.metrics.AUC(name='auc')]
        )
        
        self.model = model
        logger.info(f"MLP model built: {self.input_size} -> {' -> '.join(map(str, self.hidden_layers))} -> 1")
    
    def load_model(self):
        """Load pre-trained model from disk"""
        if not HAS_TENSORFLOW:
            return
        
        try:
            self.model = keras.models.load_model(self.model_path)
            logger.success(f"✓ MLP model loaded from: {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            logger.info("Building new model instead...")
            self.build_model()
    
    def save_model(self, path: str = None):
        """Save model to disk"""
        if not HAS_TENSORFLOW or self.model is None:
            return
        
        save_path = path or self.model_path
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        try:
            self.model.save(save_path)
            logger.success(f"✓ Model saved to: {save_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
    
    def extract_features(
        self,
        timeseries_data: List[Dict[str, float]]
    ) -> np.ndarray:
        """
        Extract 180-dimensional feature vector from time series
        
        Features per polarization (90 each for VV and VH):
        - 30 observations × Mean
        - 30 observations × Standard Deviation
        - 30 observations × MMD (Maximum - Minimum Difference, i.e., signal range)
        
        Args:
            timeseries_data: List of temporal observations with vv_mean, vv_std, vv_mmd, etc.
        
        Returns:
            Feature vector of shape (180,)
        """
        # Sort by observation date
        sorted_data = sorted(timeseries_data, key=lambda x: x.get('observation_date', ''))
        
        # Take last 30 observations
        n_obs = min(30, len(sorted_data))
        recent_data = sorted_data[-n_obs:]
        
        # Extract features (MMD = Max-Min Difference per Silva et al. 2022)
        vv_means = [obs['vv_mean'] for obs in recent_data]
        vv_stds = [obs['vv_std'] for obs in recent_data]
        vv_mmds = [obs.get('vv_mmd', obs.get('vv_max', 0) - obs.get('vv_min', 0)) for obs in recent_data]
        
        vh_means = [obs['vh_mean'] for obs in recent_data]
        vh_stds = [obs['vh_std'] for obs in recent_data]
        vh_mmds = [obs.get('vh_mmd', obs.get('vh_max', 0) - obs.get('vh_min', 0)) for obs in recent_data]
        
        # Pad with zeros if less than 30 observations
        if n_obs < 30:
            logger.warning(f"Only {n_obs} observations available (expected 30). Padding with zeros.")
            vv_means += [0.0] * (30 - n_obs)
            vv_stds += [0.0] * (30 - n_obs)
            vv_mmds += [0.0] * (30 - n_obs)
            vh_means += [0.0] * (30 - n_obs)
            vh_stds += [0.0] * (30 - n_obs)
            vh_mmds += [0.0] * (30 - n_obs)
        
        # Concatenate all features
        features = np.concatenate([
            vv_means, vv_stds, vv_mmds,
            vh_means, vh_stds, vh_mmds
        ])
        
        # Normalize to 0-1 range
        # Typical SAR backscatter range: 0.001 to 0.5 (linear units)
        features = np.clip(features, 0.0, 0.5) / 0.5
        
        return features
    
    def predict(
        self,
        features: np.ndarray
    ) -> Tuple[float, bool]:
        """
        Predict deforestation probability for feature vector
        
        Args:
            features: Feature vector of shape (180,) or (batch, 180)
        
        Returns:
            Tuple of (probability, is_alert)
        """
        if not HAS_TENSORFLOW or self.model is None:
            logger.warning("Model not available. Returning default prediction.")
            return 0.5, False
        
        # Ensure correct shape
        if len(features.shape) == 1:
            features = features.reshape(1, -1)
        
        # Predict
        try:
            probability = float(self.model.predict(features, verbose=0)[0][0])
            is_alert = probability >= self.threshold
            
            return probability, is_alert
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return 0.0, False
    
    def validate_detection(
        self,
        grid_cell_id: str,
        timeseries_data: List[Dict[str, float]]
    ) -> Dict[str, Any]:
        """
        Validate an ALT detection using the MLP model
        
        Args:
            grid_cell_id: Grid cell identifier
            timeseries_data: Historical time series for feature extraction
        
        Returns:
            Validation result dict
        """
        # Extract features
        try:
            features = self.extract_features(timeseries_data)
            
            # Get prediction
            probability, is_alert = self.predict(features)
            
            result = {
                'grid_cell_id': grid_cell_id,
                'confidence_score': probability,
                'is_valid_alert': is_alert,
                'threshold': self.threshold,
                'num_observations': len(timeseries_data)
            }
            
            if is_alert:
                logger.info(f"✓ Validated detection for {grid_cell_id}: {probability:.4f}")
            else:
                logger.debug(f"✗ Rejected detection for {grid_cell_id}: {probability:.4f} < {self.threshold}")
            
            return result
            
        except Exception as e:
            logger.error(f"Validation failed for {grid_cell_id}: {e}")
            return {
                'grid_cell_id': grid_cell_id,
                'confidence_score': 0.0,
                'is_valid_alert': False,
                'error': str(e)
            }
    
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray = None,
        y_val: np.ndarray = None,
        epochs: int = 50,
        batch_size: int = 32
    ) -> Dict[str, Any]:
        """
        Train the MLP model
        
        Args:
            X_train: Training features (n_samples, 180)
            y_train: Training labels (n_samples,) - binary 0/1
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
            epochs: Number of training epochs
            batch_size: Batch size for training
        
        Returns:
            Training history dict
        """
        if not HAS_TENSORFLOW or self.model is None:
            logger.error("Model not available for training")
            return {}
        
        # Prepare validation data
        validation_data = (X_val, y_val) if X_val is not None else None
        
        # Train model
        logger.info(f"Training MLP model: {len(X_train)} samples, {epochs} epochs")
        
        history = self.model.fit(
            X_train, y_train,
            validation_data=validation_data,
            epochs=epochs,
            batch_size=batch_size,
            verbose=1,
            callbacks=[
                keras.callbacks.EarlyStopping(
                    monitor='val_loss' if validation_data else 'loss',
                    patience=10,
                    restore_best_weights=True
                )
            ]
        )
        
        logger.success("✓ Training complete")
        
        # Save model
        self.save_model()
        
        return history.history


def generate_synthetic_training_data(n_samples: int = 1000) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic training data for initial model weights
    
    Simulates:
    - Stable forest: low variability, consistent signal
    - Deforestation: sharp drop in all metrics
    
    Args:
        n_samples: Number of samples to generate
    
    Returns:
        Tuple of (features, labels)
    """
    logger.info(f"Generating {n_samples} synthetic training samples...")
    
    features = []
    labels = []
    
    for _ in range(n_samples):
        # Random class: 0 = forest, 1 = deforestation
        is_deforestation = np.random.rand() > 0.7  # 30% deforestation samples
        
        if is_deforestation:
            # Deforestation pattern: drop in last few observations
            vv_means = np.concatenate([
                np.random.normal(0.08, 0.01, 25),  # Stable forest
                np.random.normal(0.03, 0.005, 5)   # Sharp drop
            ])
            vh_means = np.concatenate([
                np.random.normal(0.016, 0.003, 25),
                np.random.normal(0.006, 0.002, 5)
            ])
        else:
            # Stable forest pattern: consistent signal
            vv_means = np.random.normal(0.08, 0.01, 30)
            vh_means = np.random.normal(0.016, 0.003, 30)
        
        # Generate STD and MMD based on means
        vv_stds = np.abs(np.random.normal(0.01, 0.003, 30))
        vh_stds = np.abs(np.random.normal(0.003, 0.001, 30))
        
        vv_mmds = np.random.normal(0, 0.005, 30)
        vh_mmds = np.random.normal(0, 0.002, 30)
        
        # Concatenate features
        sample = np.concatenate([
            vv_means, vv_stds, vv_mmds,
            vh_means, vh_stds, vh_mmds
        ])
        
        # Normalize to 0-1
        sample = np.clip(sample, 0.0, 0.5) / 0.5
        
        features.append(sample)
        labels.append(int(is_deforestation))
    
    return np.array(features), np.array(labels)


if __name__ == "__main__":
    """Test and train the MLP model with synthetic data"""
    import sys
    from loguru import logger
    
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    # Create model
    mlp = MLPModel()
    
    if HAS_TENSORFLOW and mlp.model:
        # Generate synthetic data
        X, y = generate_synthetic_training_data(n_samples=2000)
        
        # Split train/val
        split = int(0.8 * len(X))
        X_train, X_val = X[:split], X[split:]
        y_train, y_val = y[:split], y[split:]
        
        logger.info(f"Training set: {len(X_train)} samples")
        logger.info(f"Validation set: {len(X_val)} samples")
        logger.info(f"Deforestation rate: {y.mean()*100:.1f}%")
        
        # Train
        history = mlp.train(X_train, y_train, X_val, y_val, epochs=30)
        
        # Evaluate
        val_loss, val_acc, val_auc = mlp.model.evaluate(X_val, y_val, verbose=0)
        logger.success(f"✓ Validation Accuracy: {val_acc*100:.2f}%")
        logger.success(f"✓ Validation AUC: {val_auc:.4f}")
    else:
        logger.error("TensorFlow not available. Cannot train model.")
