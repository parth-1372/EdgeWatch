"""
EdgeWatch Database Storage System

This module provides database connectivity and storage operations for EdgeWatch monitoring data.
Supports SQLite, PostgreSQL, and other database backends through SQLAlchemy.
"""

import sqlite3
import threading
import time
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from pathlib import Path
import logging

try:
    from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, Session
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

from ..core.config_manager import ConfigManager
from ..core.utils import get_logger, SystemUtils

logger = get_logger("storage")

# Database Models
if SQLALCHEMY_AVAILABLE:
    Base = declarative_base()
    
    class NodeData(Base):
        __tablename__ = 'node_data'
        
        id = Column(Integer, primary_key=True)
        run_id = Column(String(50), index=True)
        node_id = Column(String(50), index=True)
        ip = Column(String(45))
        port = Column(Integer)
        round_number = Column(Integer, index=True)
        cycle = Column(Integer)
        timestamp = Column(DateTime, default=datetime.utcnow)
        data_json = Column(Text)
        digest = Column(String(64))
        is_alive = Column(Boolean, default=True)
        
    class NodeMetrics(Base):
        __tablename__ = 'node_metrics'
        
        id = Column(Integer, primary_key=True)
        run_id = Column(String(50), index=True)
        node_id = Column(String(50), index=True)
        round_number = Column(Integer, index=True)
        timestamp = Column(DateTime, default=datetime.utcnow)
        cpu_usage = Column(Float)
        memory_usage = Column(Float)
        network_bytes = Column(Integer)
        storage_free = Column(Integer)
        metrics_sent = Column(Integer, default=0)
        metrics_filtered = Column(Integer, default=0)
        
    class CommunicationStats(Base):
        __tablename__ = 'communication_stats'
        
        id = Column(Integer, primary_key=True)
        run_id = Column(String(50), index=True)
        node_id = Column(String(50), index=True)
        round_number = Column(Integer, index=True)
        timestamp = Column(DateTime, default=datetime.utcnow)
        new_data_count = Column(Integer, default=0)  # nd
        fresh_data_count = Column(Integer, default=0)  # fd
        received_messages = Column(Integer, default=0)  # rm
        incoming_connections = Column(Integer, default=0)  # ic
        bytes_transmitted = Column(Integer, default=0)


class EdgeWatchDatabase:
    """
    Main database interface for EdgeWatch monitoring system.
    Provides unified access to different database backends.
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        self.config = ConfigManager.instance()
        self.connection_string = connection_string or self._build_connection_string()
        self.engine = None
        self.session_factory = None
        self._lock = threading.RLock()
        self._connection_pool = {}
        self.current_run_id = self._generate_run_id()
        
        # Initialize database
        self._initialize_database()
        
    def _build_connection_string(self) -> str:
        """Build database connection string from configuration"""
        db_type = self.config.get('Storage', 'database_type', 'sqlite')
        
        if db_type.lower() == 'sqlite':
            db_path = self.config.get('Storage', 'database_path', 'data/edgewatch.db')
            # Ensure directory exists
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{db_path}"
            
        elif db_type.lower() == 'postgresql':
            host = self.config.get('Storage', 'host', 'localhost')
            port = self.config.get_int('Storage', 'port', 5432)
            database = self.config.get('Storage', 'database', 'edgewatch')
            username = self.config.get('Storage', 'username', 'edgewatch')
            password = self.config.get('Storage', 'password', '')
            return f"postgresql://{username}:{password}@{host}:{port}/{database}"
            
        else:
            logger.warning(f"Unsupported database type: {db_type}, defaulting to SQLite")
            return "sqlite:///data/edgewatch.db"
    
    def _initialize_database(self):
        """Initialize database connection and create tables"""
        try:
            if SQLALCHEMY_AVAILABLE:
                self.engine = create_engine(
                    self.connection_string,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    echo=False
                )
                self.session_factory = sessionmaker(bind=self.engine)
                
                # Create tables
                Base.metadata.create_all(self.engine)
                logger.info(f"Database initialized: {self.connection_string}")
            else:
                logger.warning("SQLAlchemy not available, using basic SQLite connection")
                self._init_sqlite_fallback()
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _init_sqlite_fallback(self):
        """Initialize basic SQLite connection as fallback"""
        db_path = self.config.get('Storage', 'database_path', 'data/edgewatch.db')
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        connection = sqlite3.connect(db_path, check_same_thread=False)
        self._create_sqlite_tables(connection)
        connection.close()
        
        logger.info(f"SQLite fallback initialized: {db_path}")
    
    def _create_sqlite_tables(self, connection):
        """Create SQLite tables manually"""
        cursor = connection.cursor()
        
        # Node data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS node_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                node_id TEXT,
                ip TEXT,
                port INTEGER,
                round_number INTEGER,
                cycle INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                data_json TEXT,
                digest TEXT,
                is_alive BOOLEAN DEFAULT 1
            )
        ''')
        
        # Node metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS node_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                node_id TEXT,
                round_number INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                cpu_usage REAL,
                memory_usage REAL,
                network_bytes INTEGER,
                storage_free INTEGER,
                metrics_sent INTEGER DEFAULT 0,
                metrics_filtered INTEGER DEFAULT 0
            )
        ''')
        
        # Communication stats table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS communication_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                node_id TEXT,
                round_number INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                new_data_count INTEGER DEFAULT 0,
                fresh_data_count INTEGER DEFAULT 0,
                received_messages INTEGER DEFAULT 0,
                incoming_connections INTEGER DEFAULT 0,
                bytes_transmitted INTEGER DEFAULT 0
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_node_data_run_id ON node_data(run_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_node_data_node_id ON node_data(node_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_node_data_round ON node_data(round_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_node_metrics_run_id ON node_metrics(run_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_comm_stats_run_id ON communication_stats(run_id)')
        
        connection.commit()
    
    def _generate_run_id(self) -> str:
        """Generate unique run ID for this session"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"edgewatch_{timestamp}"
    
    def get_session(self) -> Optional[Session]:
        """Get database session"""
        if SQLALCHEMY_AVAILABLE and self.session_factory:
            return self.session_factory()
        return None
    
    def get_sqlite_connection(self):
        """Get SQLite connection (fallback)"""
        db_path = self.config.get('Storage', 'database_path', 'data/edgewatch.db')
        return sqlite3.connect(db_path, check_same_thread=False)
    
    def store_node_data(self, node_id: str, ip: str, port: int, round_number: int, 
                       cycle: int, data: Dict, digest: str = "") -> bool:
        """Store node data"""
        try:
            with self._lock:
                if SQLALCHEMY_AVAILABLE and self.session_factory:
                    return self._store_node_data_sqlalchemy(
                        node_id, ip, port, round_number, cycle, data, digest
                    )
                else:
                    return self._store_node_data_sqlite(
                        node_id, ip, port, round_number, cycle, data, digest
                    )
        except Exception as e:
            logger.error(f"Error storing node data: {e}")
            return False
    
    def _store_node_data_sqlalchemy(self, node_id: str, ip: str, port: int, 
                                   round_number: int, cycle: int, data: Dict, digest: str) -> bool:
        """Store node data using SQLAlchemy"""
        session = self.get_session()
        try:
            # Remove existing data for this round
            session.query(NodeData).filter(
                NodeData.run_id == self.current_run_id,
                NodeData.node_id == node_id,
                NodeData.round_number == round_number
            ).delete()
            
            # Insert new data
            node_data = NodeData(
                run_id=self.current_run_id,
                node_id=node_id,
                ip=ip,
                port=port,
                round_number=round_number,
                cycle=cycle,
                data_json=json.dumps(data),
                digest=digest
            )
            
            session.add(node_data)
            session.commit()
            
            logger.debug(f"Stored node data for {node_id} round {round_number}")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"SQLAlchemy error storing node data: {e}")
            return False
        finally:
            session.close()
    
    def _store_node_data_sqlite(self, node_id: str, ip: str, port: int, 
                               round_number: int, cycle: int, data: Dict, digest: str) -> bool:
        """Store node data using SQLite"""
        connection = self.get_sqlite_connection()
        try:
            cursor = connection.cursor()
            
            # Remove existing data
            cursor.execute(
                "DELETE FROM node_data WHERE run_id = ? AND node_id = ? AND round_number = ?",
                (self.current_run_id, node_id, round_number)
            )
            
            # Insert new data
            cursor.execute(
                '''INSERT INTO node_data 
                   (run_id, node_id, ip, port, round_number, cycle, data_json, digest)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (self.current_run_id, node_id, ip, port, round_number, cycle, 
                 json.dumps(data), digest)
            )
            
            connection.commit()
            logger.debug(f"Stored node data for {node_id} round {round_number}")
            return True
            
        except Exception as e:
            logger.error(f"SQLite error storing node data: {e}")
            return False
        finally:
            connection.close()
    
    def store_node_metrics(self, node_id: str, round_number: int, metrics: Dict) -> bool:
        """Store node metrics"""
        try:
            with self._lock:
                if SQLALCHEMY_AVAILABLE and self.session_factory:
                    return self._store_node_metrics_sqlalchemy(node_id, round_number, metrics)
                else:
                    return self._store_node_metrics_sqlite(node_id, round_number, metrics)
        except Exception as e:
            logger.error(f"Error storing node metrics: {e}")
            return False
    
    def _store_node_metrics_sqlalchemy(self, node_id: str, round_number: int, metrics: Dict) -> bool:
        """Store node metrics using SQLAlchemy"""
        session = self.get_session()
        try:
            node_metrics = NodeMetrics(
                run_id=self.current_run_id,
                node_id=node_id,
                round_number=round_number,
                cpu_usage=metrics.get('cpu'),
                memory_usage=metrics.get('memory'),
                network_bytes=metrics.get('network'),
                storage_free=metrics.get('storage'),
                metrics_sent=metrics.get('metrics_sent', 0),
                metrics_filtered=metrics.get('metrics_filtered', 0)
            )
            
            session.add(node_metrics)
            session.commit()
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error storing metrics: {e}")
            return False
        finally:
            session.close()
    
    def _store_node_metrics_sqlite(self, node_id: str, round_number: int, metrics: Dict) -> bool:
        """Store node metrics using SQLite"""
        connection = self.get_sqlite_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(
                '''INSERT INTO node_metrics 
                   (run_id, node_id, round_number, cpu_usage, memory_usage, 
                    network_bytes, storage_free, metrics_sent, metrics_filtered)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (self.current_run_id, node_id, round_number,
                 metrics.get('cpu'), metrics.get('memory'),
                 metrics.get('network'), metrics.get('storage'),
                 metrics.get('metrics_sent', 0), metrics.get('metrics_filtered', 0))
            )
            connection.commit()
            return True
        except Exception as e:
            logger.error(f"SQLite error storing metrics: {e}")
            return False
        finally:
            connection.close()
    
    def store_communication_stats(self, node_id: str, round_number: int, stats: Dict) -> bool:
        """Store communication statistics"""
        try:
            with self._lock:
                if SQLALCHEMY_AVAILABLE and self.session_factory:
                    return self._store_communication_stats_sqlalchemy(node_id, round_number, stats)
                else:
                    return self._store_communication_stats_sqlite(node_id, round_number, stats)
        except Exception as e:
            logger.error(f"Error storing communication stats: {e}")
            return False
    
    def _store_communication_stats_sqlalchemy(self, node_id: str, round_number: int, stats: Dict) -> bool:
        """Store communication stats using SQLAlchemy"""
        session = self.get_session()
        try:
            comm_stats = CommunicationStats(
                run_id=self.current_run_id,
                node_id=node_id,
                round_number=round_number,
                new_data_count=stats.get('nd', 0),
                fresh_data_count=stats.get('fd', 0),
                received_messages=stats.get('rm', 0),
                incoming_connections=stats.get('ic', 0),
                bytes_transmitted=stats.get('bytes', 0)
            )
            
            session.add(comm_stats)
            session.commit()
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error storing communication stats: {e}")
            return False
        finally:
            session.close()
    
    def _store_communication_stats_sqlite(self, node_id: str, round_number: int, stats: Dict) -> bool:
        """Store communication stats using SQLite"""
        connection = self.get_sqlite_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(
                '''INSERT INTO communication_stats 
                   (run_id, node_id, round_number, new_data_count, fresh_data_count,
                    received_messages, incoming_connections, bytes_transmitted)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (self.current_run_id, node_id, round_number,
                 stats.get('nd', 0), stats.get('fd', 0), stats.get('rm', 0),
                 stats.get('ic', 0), stats.get('bytes', 0))
            )
            connection.commit()
            return True
        except Exception as e:
            logger.error(f"SQLite error storing communication stats: {e}")
            return False
        finally:
            connection.close()
    
    def get_node_data(self, node_id: str = None, round_number: int = None, 
                     limit: int = 100) -> List[Dict]:
        """Retrieve node data with optional filtering"""
        try:
            if SQLALCHEMY_AVAILABLE and self.session_factory:
                return self._get_node_data_sqlalchemy(node_id, round_number, limit)
            else:
                return self._get_node_data_sqlite(node_id, round_number, limit)
        except Exception as e:
            logger.error(f"Error retrieving node data: {e}")
            return []
    
    def _get_node_data_sqlalchemy(self, node_id: str, round_number: int, limit: int) -> List[Dict]:
        """Retrieve node data using SQLAlchemy"""
        session = self.get_session()
        try:
            query = session.query(NodeData).filter(NodeData.run_id == self.current_run_id)
            
            if node_id:
                query = query.filter(NodeData.node_id == node_id)
            if round_number:
                query = query.filter(NodeData.round_number == round_number)
            
            results = query.order_by(NodeData.timestamp.desc()).limit(limit).all()
            
            return [
                {
                    'node_id': r.node_id,
                    'ip': r.ip,
                    'port': r.port,
                    'round_number': r.round_number,
                    'cycle': r.cycle,
                    'timestamp': r.timestamp.isoformat(),
                    'data': json.loads(r.data_json) if r.data_json else {},
                    'digest': r.digest
                }
                for r in results
            ]
            
        finally:
            session.close()
    
    def _get_node_data_sqlite(self, node_id: str, round_number: int, limit: int) -> List[Dict]:
        """Retrieve node data using SQLite"""
        connection = self.get_sqlite_connection()
        try:
            cursor = connection.cursor()
            query = "SELECT * FROM node_data WHERE run_id = ?"
            params = [self.current_run_id]
            
            if node_id:
                query += " AND node_id = ?"
                params.append(node_id)
            if round_number:
                query += " AND round_number = ?"
                params.append(round_number)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            columns = [description[0] for description in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                if row_dict.get('data_json'):
                    row_dict['data'] = json.loads(row_dict['data_json'])
                results.append(row_dict)
            
            return results
            
        finally:
            connection.close()
    
    def cleanup_old_data(self, retention_days: int = None):
        """Clean up old data based on retention policy"""
        try:
            retention_days = retention_days or self.config.get_int('Storage', 'data_retention_days', 30)
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            if SQLALCHEMY_AVAILABLE and self.session_factory:
                self._cleanup_old_data_sqlalchemy(cutoff_date)
            else:
                self._cleanup_old_data_sqlite(cutoff_date)
                
            logger.info(f"Cleaned up data older than {retention_days} days")
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
    
    def _cleanup_old_data_sqlalchemy(self, cutoff_date: datetime):
        """Clean up old data using SQLAlchemy"""
        session = self.get_session()
        try:
            # Clean node data
            deleted_node_data = session.query(NodeData).filter(
                NodeData.timestamp < cutoff_date
            ).delete()
            
            # Clean metrics
            deleted_metrics = session.query(NodeMetrics).filter(
                NodeMetrics.timestamp < cutoff_date
            ).delete()
            
            # Clean communication stats
            deleted_comm_stats = session.query(CommunicationStats).filter(
                CommunicationStats.timestamp < cutoff_date
            ).delete()
            
            session.commit()
            
            logger.info(f"Cleaned up {deleted_node_data} node data, {deleted_metrics} metrics, "
                       f"{deleted_comm_stats} communication stats records")
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def _cleanup_old_data_sqlite(self, cutoff_date: datetime):
        """Clean up old data using SQLite"""
        connection = self.get_sqlite_connection()
        try:
            cursor = connection.cursor()
            cutoff_str = cutoff_date.isoformat()
            
            cursor.execute("DELETE FROM node_data WHERE timestamp < ?", (cutoff_str,))
            deleted_node_data = cursor.rowcount
            
            cursor.execute("DELETE FROM node_metrics WHERE timestamp < ?", (cutoff_str,))
            deleted_metrics = cursor.rowcount
            
            cursor.execute("DELETE FROM communication_stats WHERE timestamp < ?", (cutoff_str,))
            deleted_comm_stats = cursor.rowcount
            
            connection.commit()
            
            logger.info(f"Cleaned up {deleted_node_data} node data, {deleted_metrics} metrics, "
                       f"{deleted_comm_stats} communication stats records")
            
        finally:
            connection.close()
    
    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        try:
            if SQLALCHEMY_AVAILABLE and self.session_factory:
                return self._get_database_stats_sqlalchemy()
            else:
                return self._get_database_stats_sqlite()
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
    
    def _get_database_stats_sqlalchemy(self) -> Dict:
        """Get database statistics using SQLAlchemy"""
        session = self.get_session()
        try:
            node_data_count = session.query(NodeData).filter(
                NodeData.run_id == self.current_run_id
            ).count()
            
            metrics_count = session.query(NodeMetrics).filter(
                NodeMetrics.run_id == self.current_run_id
            ).count()
            
            comm_stats_count = session.query(CommunicationStats).filter(
                CommunicationStats.run_id == self.current_run_id
            ).count()
            
            return {
                'current_run_id': self.current_run_id,
                'node_data_records': node_data_count,
                'metrics_records': metrics_count,
                'communication_stats_records': comm_stats_count,
                'database_type': 'SQLAlchemy',
                'connection_string': self.connection_string
            }
            
        finally:
            session.close()
    
    def _get_database_stats_sqlite(self) -> Dict:
        """Get database statistics using SQLite"""
        connection = self.get_sqlite_connection()
        try:
            cursor = connection.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM node_data WHERE run_id = ?", (self.current_run_id,))
            node_data_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM node_metrics WHERE run_id = ?", (self.current_run_id,))
            metrics_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM communication_stats WHERE run_id = ?", (self.current_run_id,))
            comm_stats_count = cursor.fetchone()[0]
            
            return {
                'current_run_id': self.current_run_id,
                'node_data_records': node_data_count,
                'metrics_records': metrics_count,
                'communication_stats_records': comm_stats_count,
                'database_type': 'SQLite',
                'database_path': self.config.get('Storage', 'database_path', 'data/edgewatch.db')
            }
            
        finally:
            connection.close()
    
    def close(self):
        """Close database connections"""
        try:
            if self.engine:
                self.engine.dispose()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")


# Alias for compatibility
DatabaseManager = EdgeWatchDatabase


# Global database instance
_database_instance = None
_database_lock = threading.Lock()

def get_database() -> EdgeWatchDatabase:
    """Get singleton database instance"""
    global _database_instance
    if _database_instance is None:
        with _database_lock:
            if _database_instance is None:
                _database_instance = EdgeWatchDatabase()
    return _database_instance
