from db_utils import db
from loguru import logger

def apply_migration():
    try:
        logger.info("Applying schema migration...")
        
        # Check if column exists
        check_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='alert_candidate' AND column_name='is_demo';
        """
        result = db.execute_query(check_query)
        
        if not result:
            logger.info("Adding is_demo and demo_date columns...")
            db.execute_update("ALTER TABLE alert_candidate ADD COLUMN is_demo BOOLEAN DEFAULT FALSE;")
            db.execute_update("ALTER TABLE alert_candidate ADD COLUMN demo_date DATE;")
            db.execute_update("CREATE INDEX idx_alert_candidate_is_demo ON alert_candidate(is_demo);")
            logger.success("Migration successful")
        else:
            logger.info("Columns already exist. Skipping.")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")

if __name__ == "__main__":
    apply_migration()
