"""
Script to load Novo Progresso municipal boundary from IBGE API
Fetches official shapefile and inserts into PostgreSQL/PostGIS database
"""

import requests
import json
from loguru import logger
from db_utils import db
from config import config


def fetch_municipality_boundary(municipality_code: str):
    """
    Fetch municipality boundary from IBGE API
    
    Args:
        municipality_code: IBGE 7-digit municipality code (e.g., '1505304' for Novo Progresso)
    
    Returns:
        GeoJSON geometry or None if failed
    """
    # IBGE API endpoint for municipal boundaries
    # Using malhas API: https://servicodados.ibge.gov.br/api/docs/malhas
    url = f"https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{municipality_code}"
    
    logger.info(f"Fetching boundary for municipality code: {municipality_code}")
    
    try:
        # Add headers to mimic browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, params={'formato': 'application/json'}, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            logger.success(f"Successfully fetched boundary data")
            return data
        else:
            logger.error(f"IBGE API returned status {response.status_code}")
            logger.info("Attempting alternative endpoint...")
            
            # Alternative: Use the malhas-simplificadas API (simplified geometries)
            alt_url = f"https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{municipality_code}?formato=application/vnd.geo+json&qualidade=minima"
            alt_response = requests.get(alt_url, headers=headers, timeout=30)
            
            if alt_response.status_code == 200:
                data = alt_response.json()
                logger.success("Successfully fetched from alternative endpoint")
                return data
            else:
                logger.error(f"Alternative endpoint also failed: {alt_response.status_code}")
                return None
            
    except requests.exceptions.Timeout:
        logger.error("Request timeout - IBGE API not responding")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        return None


def insert_boundary_to_db(municipality_code: str, name: str, state: str, geojson_geom):
    """
    Insert municipality boundary into database
    
    Args:
        municipality_code: IBGE code
        name: Municipality name
        state: State code (e.g., 'PA')
        geojson_geom: GeoJSON geometry object
    """
    # Calculate approximate area
    area_query = """
        SELECT ST_Area(ST_GeomFromGeoJSON(%s)::geography) / 10000 as area_hectares;
    """
    area_result = db.execute_query(area_query, (json.dumps(geojson_geom),))
    area_hectares = area_result[0]['area_hectares'] if area_result else None
    
    # Insert or update boundary
    insert_query = """
        INSERT INTO forest_boundaries (
            name, boundary_type, official_code, description,
            risk_tier, area_hectares, state, geom
        ) VALUES (
            %s, 'MUNICIPALITY', %s, %s, 'TIER_1', %s, %s,
            ST_GeomFromGeoJSON(%s)
        )
        ON CONFLICT ON CONSTRAINT forest_boundaries_pkey 
        DO UPDATE SET
            geom = EXCLUDED.geom,
            area_hectares = EXCLUDED.area_hectares,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id;
    """
    
    # Check if already exists
    check_query = """
        SELECT id FROM forest_boundaries 
        WHERE official_code = %s AND boundary_type = 'MUNICIPALITY';
    """
    existing = db.execute_query(check_query, (municipality_code,))
    
    if existing:
        # Update existing
        update_query = """
            UPDATE forest_boundaries
            SET geom = ST_GeomFromGeoJSON(%s),
                area_hectares = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE official_code = %s AND boundary_type = 'MUNICIPALITY'
            RETURNING id;
        """
        result = db.execute_query(update_query, (
            json.dumps(geojson_geom),
            area_hectares,
            municipality_code
        ))
        logger.info(f"Updated existing boundary record (ID: {result[0]['id']})")
    else:
        # Insert new
        description = f"Municipality of {name}, {state}, Brazil. " \
                     f"Official boundary from IBGE (Code: {municipality_code})."
        
        result = db.execute_query(insert_query, (
            name,
            municipality_code,
            description,
            area_hectares,
            state,
            json.dumps(geojson_geom)
        ))
        logger.success(f"Inserted new boundary record (ID: {result[0]['id']})")
    
    return result[0]['id'] if result else None


def load_novo_progresso():
    """Load Novo Progresso boundary from IBGE API"""
    municipality_code = config.AOI_MUNICIPALITY_CODE
    name = config.AOI_NAME
    state = config.AOI_STATE
    
    logger.info(f"Loading {name}, {state} (IBGE: {municipality_code})")
    
    # Fetch from IBGE
    geojson_data = fetch_municipality_boundary(municipality_code)
    
    if not geojson_data:
        logger.error("Failed to fetch boundary data from IBGE API")
        logger.warning("Using placeholder geometry instead...")
        
        # Fallback: Create approximate bounding box for Novo Progresso
        # Real coordinates: approximately -55.5 to -54.8 lon, -7.3 to -6.8 lat
        placeholder_geom = {
            "type": "Polygon",
            "coordinates": [[
                [-55.5, -7.3],
                [-55.5, -6.8],
                [-54.8, -6.8],
                [-54.8, -7.3],
                [-55.5, -7.3]
            ]]
        }
        
        # Insert placeholder
        boundary_id = insert_boundary_to_db(
            municipality_code,
            name,
            state,
            placeholder_geom
        )
        
        logger.warning(f"Inserted placeholder boundary (ID: {boundary_id})")
        logger.warning("Please replace with official boundary when IBGE API is accessible")
        return boundary_id
    
    # Extract geometry from GeoJSON response
    if isinstance(geojson_data, dict):
        # If it's a FeatureCollection
        if geojson_data.get('type') == 'FeatureCollection':
            features = geojson_data.get('features', [])
            if features:
                geometry = features[0].get('geometry')
            else:
                logger.error("No features found in FeatureCollection")
                return None
        # If it's a Feature
        elif geojson_data.get('type') == 'Feature':
            geometry = geojson_data.get('geometry')
        # If it's already a geometry
        elif geojson_data.get('type') in ['Polygon', 'MultiPolygon']:
            geometry = geojson_data
        else:
            logger.error(f"Unexpected GeoJSON structure: {geojson_data.get('type')}")
            return None
        
        # Convert Polygon to MultiPolygon if needed (PostGIS schema expects MultiPolygon)
        if geometry.get('type') == 'Polygon':
            geometry = {
                'type': 'MultiPolygon',
                'coordinates': [geometry['coordinates']]
            }
        
        # Insert into database
        boundary_id = insert_boundary_to_db(
            municipality_code,
            name,
            state,
            geometry
        )
        
        logger.success(f"✓ Novo Progresso boundary loaded successfully (ID: {boundary_id})")
        return boundary_id
    
    else:
        logger.error("Unexpected response format from IBGE API")
        return None


if __name__ == "__main__":
    """Run this script to load Novo Progresso boundary into the database"""
    from loguru import logger
    import sys
    
    # Configure logger
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    try:
        boundary_id = load_novo_progresso()
        if boundary_id:
            logger.success(f"✓ Boundary loaded successfully (Database ID: {boundary_id})")
            
            # Verify
            aoi = db.get_aoi_boundary(config.AOI_MUNICIPALITY_CODE)
            if aoi:
                logger.info(f"Verification: {aoi['name']} - Code: {aoi['official_code']}")
                logger.info(f"Bounding Box: {aoi['bbox']}")
        else:
            logger.error("✗ Failed to load boundary")
            sys.exit(1)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
