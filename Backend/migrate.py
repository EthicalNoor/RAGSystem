from sqlalchemy import create_engine, text
from app.models import Base
from app.config import get_logger

logger = get_logger(__name__)

def run_migrations(database_url: str):
    """
    Runs schema creation and dynamic table alters.
    Triggered automatically only when the database_url changes.
    """
    if not database_url:
        logger.error("No database URL provided for migration.")
        return False

    safe_url = database_url.split('@')[-1] if '@' in database_url else "configured DB"
    logger.info(f"Running database migrations for: {safe_url}")
    
    engine = create_engine(database_url, pool_pre_ping=True)
    
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            Base.metadata.create_all(bind=engine)

            try:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS database_url VARCHAR"))
                conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS page_number INTEGER"))
                conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS session_id VARCHAR"))
                conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS is_summarized BOOLEAN DEFAULT FALSE"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR DEFAULT 'user'"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password VARCHAR"))
                conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS user_id VARCHAR REFERENCES users(id) ON DELETE CASCADE"))
                conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS user_id VARCHAR REFERENCES users(id) ON DELETE CASCADE"))
                
                conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS feedback_score INTEGER"))
                conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS feedback_text VARCHAR"))
            except Exception as e:
                logger.warning(f"Alter table migration skipped or failed (columns might already exist): {e}")

            logger.info("Running User & Auth Migrations...")
            conn.execute(text("""
                INSERT INTO users (id, email, name, role, password) 
                VALUES ('admin_sys_001', 'admin', 'System Administrator', 'admin', 'admin123')
                ON CONFLICT (email) DO NOTHING
            """))
            conn.commit()
            
        logger.info("Database tables and pgvector extension initialized successfully.")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise e