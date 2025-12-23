"""
Database connection utilities with resilience patterns

Provides:
- SafeSQLiteConnection: Context manager with WAL mode, busy_timeout, and retry logic
- get_db_connection: FastAPI dependency for per-request connection sharing
- Robust error handling for SQLite concurrency issues
"""

import sqlite3
import time
import logging
from typing import Optional, Generator
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)


class SafeSQLiteConnection:
    """
    Context manager for SQLite connections with resilience patterns

    Features:
    - WAL mode for concurrent reads/writes
    - busy_timeout for internal retry
    - Application-level retry for OperationalError
    - Proper connection cleanup
    - Row factory for dict-like access

    Usage:
        with SafeSQLiteConnection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vulnerabilities")
            results = cursor.fetchall()
    """

    def __init__(
        self,
        db_path: str,
        timeout: float = 5.0,
        max_retries: int = 3,
        retry_delay: float = 0.1,
        check_same_thread: bool = False,
        row_factory: bool = True
    ):
        """
        Initialize safe connection manager

        Args:
            db_path: Path to SQLite database file
            timeout: busy_timeout in seconds (SQLite internal retry)
            max_retries: Max application-level retry attempts
            retry_delay: Base delay between retries (exponential backoff)
            check_same_thread: Allow connection sharing across threads (False for FastAPI)
            row_factory: Enable dict-like row access (True recommended)
        """
        self.db_path = db_path
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.check_same_thread = check_same_thread
        self.row_factory = row_factory
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        """
        Open connection with retry logic

        Returns:
            SQLite connection with WAL mode and busy_timeout configured

        Raises:
            sqlite3.OperationalError: If all retries exhausted
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                # Open connection
                self.conn = sqlite3.connect(
                    self.db_path,
                    timeout=self.timeout,  # Initial timeout for opening
                    check_same_thread=self.check_same_thread
                )

                # Configure row factory for dict-like access
                if self.row_factory:
                    self.conn.row_factory = sqlite3.Row

                # Enable WAL mode for better concurrency
                # WAL allows multiple readers + 1 writer concurrently
                cursor = self.conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")

                # Set busy_timeout (milliseconds) - SQLite will retry internally
                # This is cleaner than Python-level retries for lock contention
                timeout_ms = int(self.timeout * 1000)
                cursor.execute(f"PRAGMA busy_timeout={timeout_ms}")

                # Optional: Enable foreign key constraints (good practice)
                cursor.execute("PRAGMA foreign_keys=ON")

                cursor.close()

                logger.debug(
                    f"DB connection established: {self.db_path} "
                    f"(WAL mode, busy_timeout={timeout_ms}ms)"
                )

                return self.conn

            except sqlite3.OperationalError as e:
                last_error = e
                error_msg = str(e).lower()

                # Only retry on "database is locked" errors
                if "locked" in error_msg or "busy" in error_msg:
                    if attempt < self.max_retries:
                        # Exponential backoff
                        delay = self.retry_delay * (2 ** (attempt - 1))
                        logger.warning(
                            f"DB locked (attempt {attempt}/{self.max_retries}), "
                            f"retrying in {delay:.2f}s: {e}"
                        )
                        time.sleep(delay)
                        continue

                # Non-retryable error or max retries reached
                logger.error(f"DB connection failed after {attempt} attempts: {e}")
                raise

            except Exception as e:
                # Unexpected error - don't retry
                logger.error(f"Unexpected DB connection error: {e}")
                raise

        # Max retries exhausted
        error_msg = f"Failed to connect to database after {self.max_retries} attempts"
        if last_error:
            error_msg += f": {last_error}"
        logger.error(error_msg)
        raise sqlite3.OperationalError(error_msg)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Close connection and handle transaction rollback on error

        Args:
            exc_type: Exception type (None if no error)
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        if self.conn:
            try:
                if exc_type is None:
                    # No error - commit any pending transaction
                    self.conn.commit()
                    logger.debug("DB transaction committed")
                else:
                    # Error occurred - rollback
                    self.conn.rollback()
                    logger.warning(f"DB transaction rolled back due to: {exc_val}")
            except Exception as e:
                logger.error(f"Error during connection cleanup: {e}")
            finally:
                self.conn.close()
                logger.debug("DB connection closed")
                self.conn = None

        # Return False to propagate exceptions
        return False


@contextmanager
def get_db_connection(
    db_path: str = "vulnerability_db.sqlite",
    **kwargs
) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for getting a safe database connection

    This is a convenience wrapper around SafeSQLiteConnection.
    Use this for standalone scripts or FastAPI dependencies.

    Args:
        db_path: Path to SQLite database
        **kwargs: Additional SafeSQLiteConnection parameters

    Yields:
        SQLite connection

    Example:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vulnerabilities")
            results = cursor.fetchall()
    """
    with SafeSQLiteConnection(db_path, **kwargs) as conn:
        yield conn


# FastAPI dependency for per-request connection
def get_db_dependency(
    db_path: str = "vulnerability_db.sqlite"
) -> Generator[sqlite3.Connection, None, None]:
    """
    FastAPI dependency for database connection

    Provides a single connection per request, shared across all operations.
    Automatically commits on success, rolls back on error, and closes connection.

    Usage in FastAPI routes:
        @router.get("/devices")
        async def list_devices(conn: sqlite3.Connection = Depends(get_db_dependency)):
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM device_inventory")
            return cursor.fetchall()

    Args:
        db_path: Path to SQLite database

    Yields:
        SQLite connection (one per request)
    """
    with get_db_connection(db_path) as conn:
        yield conn


def init_database(db_path: str, schema_file: Optional[str] = None) -> None:
    """
    Initialize database with schema if needed

    Args:
        db_path: Path to SQLite database
        schema_file: Path to SQL schema file (optional)
    """
    db_file = Path(db_path)

    if db_file.exists():
        logger.info(f"Database already exists: {db_path}")
        return

    logger.info(f"Creating new database: {db_path}")

    with get_db_connection(db_path) as conn:
        if schema_file:
            schema_path = Path(schema_file)
            if schema_path.exists():
                logger.info(f"Applying schema: {schema_file}")
                with open(schema_path, 'r') as f:
                    schema_sql = f.read()
                conn.executescript(schema_sql)
                logger.info("Schema applied successfully")
            else:
                logger.warning(f"Schema file not found: {schema_file}")
        else:
            logger.info("No schema file provided")


def check_db_health(db_path: str) -> dict:
    """
    Check database health and configuration

    Returns diagnostic information useful for troubleshooting.

    Args:
        db_path: Path to SQLite database

    Returns:
        dict: Health check results
    """
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # Get journal mode
            cursor.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]

            # Get busy timeout
            cursor.execute("PRAGMA busy_timeout")
            busy_timeout = cursor.fetchone()[0]

            # Get foreign keys status
            cursor.execute("PRAGMA foreign_keys")
            foreign_keys = cursor.fetchone()[0]

            # Get table count
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            # Get database size
            db_size_bytes = Path(db_path).stat().st_size
            db_size_mb = db_size_bytes / (1024 * 1024)

            return {
                'status': 'healthy',
                'db_path': db_path,
                'journal_mode': journal_mode,
                'busy_timeout_ms': busy_timeout,
                'foreign_keys_enabled': bool(foreign_keys),
                'tables': tables,
                'table_count': len(tables),
                'size_mb': round(db_size_mb, 2)
            }

    except Exception as e:
        return {
            'status': 'unhealthy',
            'db_path': db_path,
            'error': str(e)
        }


# Example usage patterns
if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test 1: Basic connection
    print("\n=== Test 1: Basic Connection ===")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 5")
        tables = cursor.fetchall()
        print(f"Found {len(tables)} tables")
        for table in tables:
            print(f"  - {table[0]}")

    # Test 2: Health check
    print("\n=== Test 2: Health Check ===")
    health = check_db_health("vulnerability_db.sqlite")
    for key, value in health.items():
        print(f"{key}: {value}")

    # Test 3: Simulated retry (would need actual contention to test)
    print("\n=== Test 3: Connection with Custom Settings ===")
    with get_db_connection(timeout=10.0, max_retries=5) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        print(f"Journal mode: {mode}")
