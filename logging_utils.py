import logging
import os
import sys

# Shared state for dynamic logs across modules
_log_counters = {}  # category -> count
_last_category = None

def setup_logger(name="PolymarketBot", console=True):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates on re-init
    for h in logger.handlers[:]:
        logger.removeHandler(h)
        
    f_handler = logging.FileHandler('main_log.log', encoding='utf-8')
    
    log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    f_handler.setFormatter(log_format)
    
    f_handler.setLevel(logging.INFO)
    
    logger.addHandler(f_handler)
    
    if console:
        c_handler = logging.StreamHandler(sys.stdout)
        c_handler.setFormatter(log_format)
        logger.addHandler(c_handler)
        
    logger.propagate = False
    return logger

def log_dynamic(logger, msg, category=None):
    """
    Overwrites the current line in terminal if the category is the same.
    Only logs to file on the first occurrence.
    """
    global _last_category
    
    # Default category to message content if not provided
    cat = category or msg
    
    # If we switch categories or if the msg contains newlines, force a newline
    if _last_category is not None and (_last_category != cat or "\n" in msg):
        sys.stdout.write("\n")
        sys.stdout.flush()
    
    _log_counters[cat] = _log_counters.get(cat, 0) + 1
    count = _log_counters[cat]
    tag = f" [x{count}]" if count > 1 else ""
    
    # Get terminal width for robust clearing
    try:
        terminal_width = os.get_terminal_size().columns
    except Exception:
        terminal_width = 80
        
    full_msg = f"{msg}{tag}"
    # Ensure message + tag doesn't exceed terminal width to prevent wrapping
    if len(full_msg) >= terminal_width:
        full_msg = full_msg[:terminal_width-4] + "..."
        
    # Clear line and print with carriage return
    # \r goes to start, then we write message, then some spaces to clear old trail
    # \033[K is the "clear until end of line" escape sequence
    sys.stdout.write(f"\r{full_msg}")
    sys.stdout.write(" " * (terminal_width - len(full_msg) - 1))
    sys.stdout.flush()
    
    _last_category = cat
    
    # Log to file: Always record to file so the user has a complete history
    record_to_file = True
    
    # Throttle HTTP_POLLING only, to prevent massive disk bloat (still logs every 20)
    if "POLLING" in cat and count > 1 and count % 20 != 0:
        record_to_file = False

    if record_to_file:
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                # Use handle() which includes formatting and flushing
                log_record = logger.makeRecord(logger.name, logging.INFO, None, 0, f"{msg}{tag}", None, None)
                handler.handle(log_record)
                handler.flush()
