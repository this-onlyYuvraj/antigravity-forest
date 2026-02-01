"""
Database Connection and Utilities
Provides PostgreSQL/PostGIS connection pool and helper functions
"""

import psycopg2
from psycopg2 import pool, extras
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from loguru import logger
from config import config


class Database:
    """PostgreSQL database connection manager with PostGIS support"""
    
    def __init__(self):
        self.connection_pool = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=config.DB_HOST,
                port=config.DB_PORT,
                database=config.DB_NAME,
                user=config.DB_USER,
                password=config.DB_PASSWORD
            )
            logger.info(f"Database connection pool initialized: {config.DB_NAME}@{config.DB_HOST}")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = self.connection_pool.getconn()
        try:
            yield conn
        finally:
            self.connection_pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, cursor_factory=None):
        """Context manager for database cursors"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory or extras.RealDictCursor)
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Database error: {e}")
                raise
            finally:
                cursor.close()
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute SELECT query and return results as list of dicts"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute INSERT/UPDATE/DELETE and return number of affected rows"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """Execute batch INSERT/UPDATE"""
        with self.get_cursor() as cursor:
            extras.execute_batch(cursor, query, params_list)
            return cursor.rowcount
    
    def verify_postgis(self) -> bool:
        """Verify PostGIS extension is installed and working"""
        try:
            result = self.execute_query("SELECT PostGIS_version();")
            version = result[0]['postgis_version']
            logger.info(f"PostGIS version: {version}")
            return True
        except Exception as e:
            logger.error(f"PostGIS verification failed: {e}")
            return False
    
    def get_aoi_boundary(self, municipality_code: str) -> Optional[Dict[str, Any]]:
        """Retrieve Area of Interest boundary from database"""
        query = """
            SELECT 
                id,
                name,
                official_code,
                ST_AsGeoJSON(geom) as geojson,
                ST_AsText(ST_Envelope(geom)) as bbox
            FROM forest_boundaries
            WHERE official_code = %s AND boundary_type = 'MUNICIPALITY'
            LIMIT 1;
        """
        results = self.execute_query(query, (municipality_code,))
        return results[0] if results else None
    
    def insert_processed_image(self, image_data: Dict[str, Any]) -> int:
        """Insert a processed image record"""
        query = """
            INSERT INTO processed_images (
                image_id, acquisition_date, polarization, orbit_direction,
                platform, status, geom
            ) VALUES (
                %(image_id)s, %(acquisition_date)s, %(polarization)s, %(orbit_direction)s,
                %(platform)s, %(status)s, ST_GeomFromGeoJSON(%(geom)s)
            )
            ON CONFLICT (image_id) DO UPDATE
            SET status = EXCLUDED.status, processing_date = CURRENT_TIMESTAMP
            RETURNING id;
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, image_data)
            return cursor.fetchone()['id']
    
    def insert_alert(self, alert_data: Dict[str, Any]) -> int:
        """Insert a new alert candidate"""
        # Ensure defaults for demo fields to maintain backward compatibility
        alert_data.setdefault('is_demo', False)
        alert_data.setdefault('demo_date', None)

        query = """
            INSERT INTO alert_candidate (
                detection_date, confidence_score, area_hectares,
                risk_tier, boundary_id, alt_vv_drop_db, alt_vh_drop_db,
                source_image_id, optical_score, combined_score, ndvi_drop, geom,
                is_demo, demo_date
            ) VALUES (
                %(detection_date)s, %(confidence_score)s, %(area_hectares)s,
                %(risk_tier)s, %(boundary_id)s, %(alt_vv_drop_db)s, %(alt_vh_drop_db)s,
                %(source_image_id)s, %(optical_score)s, %(combined_score)s, %(ndvi_drop)s, 
                ST_GeomFromGeoJSON(%(geom)s),
                %(is_demo)s, %(demo_date)s
            )
            RETURNING id;
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, alert_data)
            return cursor.fetchone()['id']
    
    def insert_backscatter_timeseries(self, timeseries_data: List[Dict[str, Any]]) -> int:
        """Batch insert backscatter time series data"""
        query = """
            INSERT INTO backscatter_timeseries (
                grid_cell_id, observation_date, vv_mean, vv_std, vv_mmd, vv_median,
                vh_mean, vh_std, vh_mmd, vh_median, pixel_count, source_image_id, geom
            ) VALUES (
                %(grid_cell_id)s, %(observation_date)s, %(vv_mean)s, %(vv_std)s, %(vv_mmd)s, %(vv_median)s,
                %(vh_mean)s, %(vh_std)s, %(vh_mmd)s, %(vh_median)s, %(pixel_count)s, %(source_image_id)s,
                ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)
            )
            ON CONFLICT (grid_cell_id, observation_date, source_image_id) DO NOTHING;
        """
        return self.execute_many(query, timeseries_data)
    
    def spatial_join_alerts_to_boundaries(self, alert_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Perform spatial join to classify alerts by intersecting boundaries"""
        query = """
            UPDATE alert_candidate a
            SET 
                boundary_id = fb.id,
                risk_tier = fb.risk_tier
            FROM forest_boundaries fb
            WHERE a.id = ANY(%s)
              AND ST_Intersects(a.geom, fb.geom)
              AND fb.risk_tier = 'TIER_2'
            RETURNING a.id, a.risk_tier, fb.name as boundary_name;
        """
        results = self.execute_query(query, (alert_ids,))
        return {r['id']: r for r in results}
    
    def get_historical_backscatter(self, grid_cell_id: str, days: int = 180) -> List[Dict[str, Any]]:
        """Retrieve historical backscatter data for a grid cell"""
        query = """
            SELECT 
                observation_date,
                vv_mean, vv_std, vv_median,
                vh_mean, vh_std, vh_median
            FROM backscatter_timeseries
            WHERE grid_cell_id = %s
              AND observation_date >= CURRENT_DATE - INTERVAL '%s days'
            ORDER BY observation_date ASC;
        """
        return self.execute_query(query, (grid_cell_id, days))
    
    def close(self):
        """Close all connections in the pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Database connection pool closed")


# Global database instance
db = Database()


# Utility functions
def test_connection():
    """Test database connection and PostGIS"""
    try:
        if db.verify_postgis():
            logger.success("✓ Database connection successful")
            logger.success("✓ PostGIS extension verified")
            return True
        else:
            logger.error("✗ PostGIS verification failed")
            return False
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return False


if __name__ == "__main__":
    # Test the database connection
    test_connection()
    
    # Test AOI retrieval
    aoi = db.get_aoi_boundary(config.AOI_MUNICIPALITY_CODE)
    if aoi:
        logger.info(f"AOI Retrieved: {aoi['name']} (Code: {aoi['official_code']})")
    else:
        logger.warning(f"AOI not found for code: {config.AOI_MUNICIPALITY_CODE}")
