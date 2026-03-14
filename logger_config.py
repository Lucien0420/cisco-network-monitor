"""
Unified logging configuration for all modules.
"""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logger(name, log_dir='logs', log_level=logging.INFO):
    """
    Create and return a configured logger.

    Args:
        name: Logger name (usually module name)
        log_dir: Log directory
        log_level: Logging level

    Returns:
        Configured logger instance
    """
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Format: timestamp, name, level, thread, message
    formatter = logging.Formatter( 
        '%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler: rotate at 10MB, keep 5 backups
    log_file = os.path.join(log_dir, f'{name}.log')
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level) 
    file_handler.setFormatter(formatter)
    
    # Console handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Attach handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
