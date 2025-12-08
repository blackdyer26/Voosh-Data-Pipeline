"""
Main pipeline orchestrator.
Coordinates extraction, transformation, and loading of recipe data.
"""

import sys
import psycopg2
from psycopg2 import OperationalError
from src.config import Config
from src.monitor import PipelineMonitor
from src.extractor import SpoonacularExtractor
from src.transformer import RecipeTransformer
from src.loader import PostgreSQLLoader

class RecipePipeline:
    """Main pipeline orchestrator for ETL process."""
    
    def __init__(self):
        """Initialize pipeline components."""
        self.db_conn = None
        self.monitor = None
        self.extractor = None
        self.transformer = None
        self.loader = None
    
    def setup(self) -> bool:
        """
        Set up pipeline components and connections.
        
        Returns:
            True if setup successful, False otherwise
        """
        try:
            # Validate configuration
            Config.validate()
            
            # Connect to database
            self.db_conn = self._connect_to_database()
            
            # Initialize monitor
            self.monitor = PipelineMonitor(self.db_conn)
            self.monitor.log("INFO", "Pipeline setup started", "pipeline")
            
            # Initialize components
            self.extractor = SpoonacularExtractor(self.monitor)
            self.transformer = RecipeTransformer(self.monitor)
            self.loader = PostgreSQLLoader(self.db_conn, self.monitor)
            
            self.monitor.log("INFO", "Pipeline setup completed successfully", "pipeline")
            return True
            
        except Exception as e:
            if self.monitor:
                self.monitor.log("CRITICAL", f"Pipeline setup failed: {e}", "pipeline", str(e))
            else:
                print(f"CRITICAL: Pipeline setup failed: {e}")
            return False
    
    def _connect_to_database(self):
        """
        Establish database connection with retry logic.
        
        Returns:
            psycopg2 connection object
            
        Raises:
            OperationalError: If connection fails
        """
        try:
            conn = psycopg2.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                dbname=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                connect_timeout=10
            )
            
            # Test connection
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            
            print(f"✓ Connected to PostgreSQL database: {Config.DB_NAME}")
            return conn
            
        except OperationalError as e:
            print(f"✗ Failed to connect to database: {e}")
            print(f"\nConnection details:")
            print(f"  Host: {Config.DB_HOST}")
            print(f"  Port: {Config.DB_PORT}")
            print(f"  Database: {Config.DB_NAME}")
            print(f"  User: {Config.DB_USER}")
            print(f"\nPlease check:")
            print(f"  1. PostgreSQL is running")
            print(f"  2. Database '{Config.DB_NAME}' exists")
            print(f"  3. User has proper permissions")
            print(f"  4. .env file is configured correctly")
            raise
    
    def run(self, batch_size: int = None) -> bool:
        """
        Execute the pipeline.
        
        Args:
            batch_size: Number of recipes to process (uses Config.BATCH_SIZE if None)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.setup():
            return False
        
        try:
            self.monitor.log("INFO", "=" * 60, "pipeline")
            self.monitor.log("INFO", "Starting Recipe Data Pipeline", "pipeline")
            self.monitor.log("INFO", "=" * 60, "pipeline")
            
            # Get last successful run
            last_run = self.monitor.get_last_successful_run()
            if last_run:
                self.monitor.log("INFO", f"Last successful run: {last_run}", "pipeline")
            
            # Step 1: Extract
            self.monitor.log("INFO", "Step 1/3: Extracting data from Spoonacular API", "pipeline")
            raw_recipes = self.extractor.fetch_batch_recipes(batch_size)
            
            if not raw_recipes:
                raise Exception("No recipes extracted from API")
            
            # Step 2: Transform
            self.monitor.log("INFO", "Step 2/3: Transforming data", "pipeline")
            transformed_recipes = self.transformer.transform_batch(raw_recipes)
            
            if not transformed_recipes:
                raise Exception("No recipes successfully transformed")
            
            # Step 3: Load
            self.monitor.log("INFO", "Step 3/3: Loading data to PostgreSQL", "pipeline")
            successful, failed = self.loader.load_batch(transformed_recipes)
            
            # Get statistics
            stats = self.loader.get_statistics()
            
            self.monitor.log("INFO", "=" * 60, "pipeline")
            self.monitor.log("INFO", "Pipeline completed successfully!", "pipeline")
            self.monitor.log("INFO", f"Total recipes in database: {stats.get('total_recipes', 0)}", "pipeline")
            self.monitor.log("INFO", f"Average health score: {stats.get('avg_health_score', 0):.1f}", "pipeline")
            self.monitor.log("INFO", "=" * 60, "pipeline")
            
            # Update status BEFORE closing connection
            self.monitor.update_status("success")
            
            return True
            
        except Exception as e:
            error_msg = f"Pipeline failed: {e}"
            self.monitor.log("CRITICAL", error_msg, "pipeline", str(e))
            # Update status BEFORE closing connection
            self.monitor.update_status("failed", error_msg)
            self.monitor.send_alert(error_msg, "CRITICAL")
            return False
            
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources."""
        if self.db_conn:
            try:
                # Log to file only, not database (connection about to close)
                if self.monitor:
                    self.monitor.logger.info("Database connection closed")
                self.db_conn.close()
            except Exception as e:
                if self.monitor:
                    self.monitor.logger.warning(f"Error closing database connection: {e}")
    
    def get_health_status(self) -> dict:
        """
        Get pipeline health status.
        
        Returns:
            Dictionary with health metrics
        """
        if not self.monitor:
            return {"status": "not_initialized"}
        
        health = self.monitor.get_pipeline_health()
        health['status'] = 'healthy' if health.get('success_rate', 0) >= 80 else 'degraded'
        
        return health


def main():
    """Main entry point for the pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Recipe Data Pipeline')
    parser.add_argument('--batch-size', type=int, default=Config.BATCH_SIZE,
                       help=f'Number of recipes to fetch (default: {Config.BATCH_SIZE})')
    parser.add_argument('--health-check', action='store_true',
                       help='Check pipeline health status')
    
    args = parser.parse_args()
    
    pipeline = RecipePipeline()
    
    if args.health_check:
        # Health check mode
        if pipeline.setup():
            health = pipeline.get_health_status()
            print("\n" + "=" * 60)
            print("PIPELINE HEALTH STATUS")
            print("=" * 60)
            for key, value in health.items():
                print(f"{key}: {value}")
            print("=" * 60 + "\n")
            pipeline.cleanup()
            sys.exit(0)
        else:
            print("Failed to initialize pipeline for health check")
            sys.exit(1)
    else:
        # Normal pipeline execution
        success = pipeline.run(args.batch_size)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()