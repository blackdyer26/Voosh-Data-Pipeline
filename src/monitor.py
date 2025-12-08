"""
Monitoring and logging module for pipeline health tracking.
Provides comprehensive logging to both file and database.
"""

import logging
import sys
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
import psycopg2
from psycopg2.extras import execute_values
import colorlog
from src.config import Config

class PipelineMonitor:
    """Monitors pipeline execution and logs to multiple destinations."""
    
    def __init__(self, db_connection):
        """
        Initialize the monitor with database connection.
        
        Args:
            db_connection: psycopg2 database connection
        """
        self.db_conn = db_connection
        self.run_id = str(uuid.uuid4())
        self.start_time = datetime.now()
        self.records_processed = 0
        self.records_failed = 0
        self.logger = self._setup_logger()
        
        # Initialize pipeline status
        self._init_pipeline_status()
    
    def _setup_logger(self) -> logging.Logger:
        """Set up colored console and file logging."""
        Config.ensure_log_directory()
        
        logger = logging.getLogger(f"pipeline_{self.run_id}")
        logger.setLevel(getattr(logging, Config.LOG_LEVEL))
        
        # Remove existing handlers
        logger.handlers = []
        
        # Console handler with colors
        console_handler = colorlog.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # File handler
        file_handler = logging.FileHandler(Config.LOG_FILE)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    def _init_pipeline_status(self):
        """Initialize pipeline status record in database."""
        try:
            with self.db_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pipeline_status (run_id, status, started_at)
                    VALUES (%s, %s, %s)
                """, (self.run_id, 'running', self.start_time))
            self.db_conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to initialize pipeline status: {e}")
    
    def _is_connection_open(self) -> bool:
        """Check if database connection is still open."""
        try:
            return self.db_conn and not self.db_conn.closed
        except:
            return False
    
    def log(self, level: str, message: str, module: str = "pipeline", 
            error_details: Optional[str] = None, execution_time_ms: Optional[int] = None):
        """
        Log message to both file and database.
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            module: Module name
            error_details: Additional error details
            execution_time_ms: Execution time in milliseconds
        """
        # Log to file/console
        log_method = getattr(self.logger, level.lower())
        log_method(f"[{module}] {message}")
        
        # Log to database only if connection is open
        if self._is_connection_open():
            try:
                with self.db_conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO pipeline_logs 
                        (run_id, level, module, message, error_details, execution_time_ms)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (self.run_id, level, module, message, error_details, execution_time_ms))
                self.db_conn.commit()
            except Exception as e:
                # Only log to file if database logging fails
                self.logger.debug(f"Database logging skipped: {e}")
    
    def increment_processed(self, count: int = 1):
        """Increment processed records counter."""
        self.records_processed += count
    
    def increment_failed(self, count: int = 1):
        """Increment failed records counter."""
        self.records_failed += count
    
    def update_status(self, status: str, error_message: Optional[str] = None):
        """
        Update pipeline status in database.
        
        Args:
            status: Pipeline status ('running', 'success', 'failed')
            error_message: Error message if status is 'failed'
        """
        if not self._is_connection_open():
            self.logger.warning("Cannot update status: database connection closed")
            return
        
        try:
            end_time = datetime.now()
            duration = int((end_time - self.start_time).total_seconds())
            
            with self.db_conn.cursor() as cur:
                cur.execute("""
                    UPDATE pipeline_status
                    SET status = %s,
                        completed_at = %s,
                        records_processed = %s,
                        records_failed = %s,
                        error_message = %s,
                        duration_seconds = %s
                    WHERE run_id = %s
                """, (status, end_time, self.records_processed, self.records_failed,
                      error_message, duration, self.run_id))
            self.db_conn.commit()
            
            self.log("INFO", f"Pipeline completed with status: {status}", "monitor")
            self.log("INFO", f"Records processed: {self.records_processed}, Failed: {self.records_failed}", "monitor")
            self.log("INFO", f"Duration: {duration} seconds", "monitor")
            
        except Exception as e:
            self.logger.error(f"Failed to update pipeline status: {e}")
    
    def get_last_successful_run(self) -> Optional[datetime]:
        """Get timestamp of last successful pipeline run."""
        if not self._is_connection_open():
            return None
        
        try:
            with self.db_conn.cursor() as cur:
                cur.execute("""
                    SELECT completed_at 
                    FROM pipeline_status 
                    WHERE status = 'success' 
                    ORDER BY completed_at DESC 
                    LIMIT 1
                """)
                result = cur.fetchone()
                return result[0] if result else None
        except Exception as e:
            self.logger.error(f"Failed to get last successful run: {e}")
            return None
    
    def get_pipeline_health(self) -> Dict[str, Any]:
        """Get current pipeline health metrics."""
        if not self._is_connection_open():
            return {"error": "database connection closed"}
        
        try:
            with self.db_conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_runs,
                        COUNT(*) FILTER (WHERE status = 'success') as successful_runs,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed_runs,
                        AVG(duration_seconds) FILTER (WHERE status = 'success') as avg_duration,
                        MAX(completed_at) FILTER (WHERE status = 'success') as last_success
                    FROM pipeline_status
                    WHERE started_at > NOW() - INTERVAL '7 days'
                """)
                result = cur.fetchone()
                
                if result:
                    return {
                        'total_runs': result[0],
                        'successful_runs': result[1],
                        'failed_runs': result[2],
                        'avg_duration_seconds': float(result[3]) if result[3] else 0,
                        'last_successful_run': result[4],
                        'success_rate': (result[1] / result[0] * 100) if result[0] > 0 else 0
                    }
        except Exception as e:
            self.logger.error(f"Failed to get pipeline health: {e}")
        
        return {}
    
    def send_alert(self, message: str, level: str = "ERROR"):
        """
        Send alert notification (optional bonus feature).
        
        Args:
            message: Alert message
            level: Alert level
        """
        self.log(level, f"ALERT: {message}", "alerting")
        
        # Slack notification (if configured)
        if Config.SLACK_WEBHOOK_URL:
            try:
                import requests
                payload = {
                    "text": f"🚨 Pipeline Alert ({level})",
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*Run ID:* {self.run_id}\n*Message:* {message}"
                            }
                        }
                    ]
                }
                requests.post(Config.SLACK_WEBHOOK_URL, json=payload, timeout=5)
                self.log("INFO", "Slack alert sent successfully", "alerting")
            except Exception as e:
                self.logger.error(f"Failed to send Slack alert: {e}")
        
        # Email notification (if configured)
        if all([Config.SMTP_HOST, Config.SMTP_USER, Config.SMTP_PASSWORD, Config.ALERT_EMAIL]):
            try:
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                
                msg = MIMEMultipart()
                msg['From'] = Config.SMTP_USER
                msg['To'] = Config.ALERT_EMAIL
                msg['Subject'] = f"Pipeline Alert ({level}) - Run {self.run_id[:8]}"
                
                body = f"""
                Pipeline Alert
                
                Level: {level}
                Run ID: {self.run_id}
                Timestamp: {datetime.now()}
                
                Message:
                {message}
                
                ---
                This is an automated alert from the Recipe Data Pipeline.
                """
                
                msg.attach(MIMEText(body, 'plain'))
                
                with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
                    server.starttls()
                    server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                    server.send_message(msg)
                
                self.log("INFO", "Email alert sent successfully", "alerting")
            except Exception as e:
                self.logger.error(f"Failed to send email alert: {e}")