import logging
import os
import sys

# Shared state for dynamic logs across modules
_log_counters = {}  # category -> count
_last_category = None

def setup_logger(name="PolymarketBot", console=True):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        os.makedirs('logs', exist_ok=True)
        
        f_handler = logging.FileHandler('logs/bot.log', encoding='utf-8')
        e_handler = logging.FileHandler('logs/error.log', encoding='utf-8')
        
        log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        f_handler.setFormatter(log_format)
        e_handler.setFormatter(log_format)
        
        logger.addHandler(f_handler)
        logger.addHandler(e_handler)
        
        if console:
            c_handler = logging.StreamHandler()
            c_handler.setFormatter(log_format)
            logger.addHandler(c_handler)
            
        logger.propagate = False
        
    return logger

def log_dynamic(logger, msg, category=None):
    """
    Overwrites the current line in terminal if the category is the same.
    Only logs to file on the first occurrence to avoid bloat.
    """
    global _last_category
    import sys
    
    # Default category to message content if not provided
    cat = category or msg
    
    # If we switch categories, move to a new line
    if _last_category is not None and _last_category != cat:
        sys.stdout.write("\n")
        sys.stdout.flush()
    
    _log_counters[cat] = _log_counters.get(cat, 0) + 1
    count = _log_counters[cat]
    tag = f" [x{count}]" if count > 1 else ""
    
    # Print to terminal with carriage return
    sys.stdout.write(f"\r{msg}{tag}" + " " * 12)
    sys.stdout.flush()
    
    _last_category = cat
    
    # Log to file on first occurrence
    if count == 1:
        # We manually call handles for file only to avoid double console print
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.emit(logger.makeRecord(logger.name, logging.INFO, None, 0, msg, None, None))
