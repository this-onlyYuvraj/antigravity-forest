
"""
Script to generate Google Earth Engine map tile URLs for a given alert.
Intended to be called by the Node.js backend on demand.

Usage:
    python generate_layers.py <lat> <lon> <date_iso_string>

Output:
    JSON dictionary of layer URLs
"""
import sys
import json
import argparse
from datetime import datetime
from services.gee_service import gee_service
from loguru import logger

# Configure logger to stderr so JSON output on stdout is clean
logger.remove()
logger.add(sys.stderr, level="INFO")

def main():
    parser = argparse.ArgumentParser(description='Generate GEE Tile URLs')
    parser.add_argument('lat', type=float, help='Latitude')
    parser.add_argument('lon', type=float, help='Longitude')
    parser.add_argument('date', type=str, help='Detection Date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    try:
        if not gee_service or not gee_service.initialized:
            logger.error("GEE Service not initialized")
            sys.exit(1)
            
        date_obj = datetime.strptime(args.date, '%Y-%m-%d')
        
        logger.info(f"Generating layers for {args.lat}, {args.lon} on {args.date}")
        
        urls = gee_service.get_layer_tile_urls(args.lat, args.lon, date_obj)
        
        # Output ONLY JSON to stdout
        print(json.dumps(urls))
        
    except Exception as e:
        logger.exception(f"Failed to generate layers: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
