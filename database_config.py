"""
Database configuration optimized for large-scale data storage (1TB+)
Implements advanced PostgreSQL features for performance and scalability
"""

from sqlalchemy import text
from app import db, app
import logging

def configure_database_for_large_scale():
    """Configure PostgreSQL database for optimal large-scale performance"""
    
    with app.app_context():
        try:
            # Enable advanced PostgreSQL features for large datasets
            optimization_queries = [
                # Configure connection pooling and memory
                "ALTER SYSTEM SET shared_buffers = '4GB';",
                "ALTER SYSTEM SET effective_cache_size = '12GB';",
                "ALTER SYSTEM SET maintenance_work_mem = '1GB';",
                "ALTER SYSTEM SET checkpoint_completion_target = 0.9;",
                "ALTER SYSTEM SET wal_buffers = '64MB';",
                "ALTER SYSTEM SET default_statistics_target = 500;",
                
                # Optimize for large table operations
                "ALTER SYSTEM SET random_page_cost = 1.1;",
                "ALTER SYSTEM SET effective_io_concurrency = 200;",
                "ALTER SYSTEM SET max_worker_processes = 8;",
                "ALTER SYSTEM SET max_parallel_workers_per_gather = 4;",
                "ALTER SYSTEM SET max_parallel_workers = 8;",
                
                # Enable compression for large data
                "ALTER SYSTEM SET wal_compression = on;",
                "ALTER SYSTEM SET log_min_duration_statement = 1000;",
                
                # Configure autovacuum for large tables
                "ALTER SYSTEM SET autovacuum_max_workers = 4;",
                "ALTER SYSTEM SET autovacuum_vacuum_scale_factor = 0.1;",
                "ALTER SYSTEM SET autovacuum_analyze_scale_factor = 0.05;",
            ]
            
            # Execute optimization queries (will require restart to take effect)
            for query in optimization_queries:
                try:
                    db.session.execute(text(query))
                    db.session.commit()
                except Exception as e:
                    logging.warning(f"Could not execute {query}: {e}")
                    db.session.rollback()
            
            logging.info("Database optimization configuration applied")
            
        except Exception as e:
            logging.error(f"Error configuring database: {e}")

def create_large_data_tables():
    """Create optimized table structures for large-scale data"""
    # Skip expensive operations for faster startup
    return
    
    with app.app_context():
        try:
            # Create message archive table for old messages (partition-like behavior)
            archive_table_sql = """
            CREATE TABLE IF NOT EXISTS message_archive (
                id BIGSERIAL PRIMARY KEY,
                original_message_id BIGINT NOT NULL,
                content TEXT NOT NULL,
                author_id VARCHAR NOT NULL,
                channel_id INTEGER NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                archived_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                message_type VARCHAR(20) DEFAULT 'text'
            );
            
            CREATE INDEX IF NOT EXISTS idx_archive_channel_date 
            ON message_archive(channel_id, created_at);
            
            CREATE INDEX IF NOT EXISTS idx_archive_author_date 
            ON message_archive(author_id, created_at);
            """
            
            # Create file storage metadata table for external file references
            file_metadata_sql = """
            CREATE TABLE IF NOT EXISTS file_metadata (
                id BIGSERIAL PRIMARY KEY,
                file_hash VARCHAR(64) UNIQUE NOT NULL,
                storage_path VARCHAR(1000) NOT NULL,
                compression_type VARCHAR(20),
                original_size BIGINT NOT NULL,
                compressed_size BIGINT,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_file_hash ON file_metadata(file_hash);
            CREATE INDEX IF NOT EXISTS idx_file_size ON file_metadata(original_size);
            """
            
            # Create user activity log for analytics
            activity_log_sql = """
            CREATE TABLE IF NOT EXISTS user_activity_log (
                id BIGSERIAL PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                activity_type VARCHAR(50) NOT NULL,
                details JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_activity_user_date 
            ON user_activity_log(user_id, created_at);
            
            CREATE INDEX IF NOT EXISTS idx_activity_type_date 
            ON user_activity_log(activity_type, created_at);
            
            CREATE INDEX IF NOT EXISTS idx_activity_details 
            ON user_activity_log USING GIN(details);
            """
            
            # Execute table creation
            for sql in [archive_table_sql, file_metadata_sql, activity_log_sql]:
                db.session.execute(text(sql))
                db.session.commit()
            
            logging.info("Large-scale data tables created successfully")
            
        except Exception as e:
            logging.error(f"Error creating large data tables: {e}")
            db.session.rollback()

def setup_table_compression():
    """Enable table compression for large data storage"""
    # Skip for faster startup
    return
    
    with app.app_context():
        try:
            # Enable compression on large tables
            compression_queries = [
                "ALTER TABLE messages SET (toast_tuple_target = 128);",
                "ALTER TABLE direct_messages SET (toast_tuple_target = 128);",
                "ALTER TABLE shared_files SET (toast_tuple_target = 128);",
                "ALTER TABLE message_archive SET (toast_tuple_target = 128);",
            ]
            
            for query in compression_queries:
                try:
                    db.session.execute(text(query))
                    db.session.commit()
                except Exception as e:
                    logging.warning(f"Could not apply compression: {e}")
                    db.session.rollback()
            
            logging.info("Table compression configured")
            
        except Exception as e:
            logging.error(f"Error setting up compression: {e}")

def create_performance_monitoring():
    """Set up performance monitoring for large-scale operations"""
    # Skip for faster startup
    return
    
    with app.app_context():
        try:
            # Create performance monitoring views
            monitoring_sql = """
            -- View for table sizes
            CREATE OR REPLACE VIEW table_sizes AS
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
            
            -- View for index usage
            CREATE OR REPLACE VIEW index_usage AS
            SELECT 
                schemaname,
                tablename,
                indexname,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch
            FROM pg_stat_user_indexes
            ORDER BY idx_scan DESC;
            
            -- View for slow queries monitoring
            CREATE OR REPLACE VIEW slow_queries AS
            SELECT 
                query,
                calls,
                total_time,
                mean_time,
                rows
            FROM pg_stat_statements
            WHERE mean_time > 1000
            ORDER BY mean_time DESC;
            """
            
            db.session.execute(text(monitoring_sql))
            db.session.commit()
            
            logging.info("Performance monitoring views created")
            
        except Exception as e:
            logging.warning(f"Could not create monitoring views: {e}")
            db.session.rollback()

if __name__ == "__main__":
    configure_database_for_large_scale()
    create_large_data_tables()
    setup_table_compression()
    create_performance_monitoring()