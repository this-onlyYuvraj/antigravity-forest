
import sys
import os
from loguru import logger

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db_utils import db

def apply_schema():
    """
    Reads database/schema.sql and applies it to the database
    using the existing Python DB connection.
    Useful if 'psql' is not in the system PATH.
    """
    # Path to schema.sql (relative to backend-python/)
    schema_path = os.path.join(os.path.dirname(__file__), '../database/schema.sql')
    schema_path = os.path.abspath(schema_path)
    
    logger.info(f"Reading schema from: {schema_path}")
    
    if not os.path.exists(schema_path):
        logger.error(f"Schema file not found at {schema_path}")
        sys.exit(1)
        
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
        
    try:
        # Use underlying connection to execute script
        # We assume db_utils is correctly configured in .env
        logger.info(f"Connecting to database: {db.connection_pool.minconn}..{db.connection_pool.maxconn} conns")
        
        with db.get_cursor() as cursor:
            logger.info("Executing schema SQL...")
            cursor.execute(schema_sql)
            logger.success("✅ Schema applied successfully!")
            
    except Exception as e:
        logger.error(f"❌ Failed to apply schema: {e}")
        sys.exit(1)

if __name__ == "__main__":
    apply_schema()
