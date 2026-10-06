import datetime

def log(msg):
    """Prints a message with a timestamp for log files."""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now}] {msg}")