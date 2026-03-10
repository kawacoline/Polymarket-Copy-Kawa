import logging
import os

def setup_logger(name="PolymarketBot"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        # Create handlers
        c_handler = logging.StreamHandler()
        f_handler = logging.FileHandler('bot.log')
        e_handler = logging.FileHandler('error.log')
        
        c_handler.setLevel(logging.INFO)
        f_handler.setLevel(logging.INFO)
        e_handler.setLevel(logging.ERROR)
        
        # Create formatters and add it to handlers
        log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(log_format)
        f_handler.setFormatter(log_format)
        e_handler.setFormatter(log_format)
        
        # Add handlers to the logger
        logger.addHandler(c_handler)
        logger.addHandler(f_handler)
        logger.addHandler(e_handler)
        
        logger.propagate = False
        
    return logger
