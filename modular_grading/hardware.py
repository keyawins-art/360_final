import re
from config import SERIAL_FILE

def read_target_serial():
    try:
        with open(SERIAL_FILE,"r") as f:
            return f.read().strip()
    except:
        print("Serial file missing")
        return None

def read_com_port_from_file(file_path):
    """
    Read COM port string from file and normalize to e.g. 'COM6'.
    Accepts '6', 'COM6', 'ASRL6::INSTR', etc.
    Returns normalized COM port string or None on error.
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()
    except FileNotFoundError:
        print(f"COM port file not found: {file_path}")
        return None
    except Exception as e:
        print(f"Error reading COM port file: {e}")
        return None

    if not content:
        print("COM port file is empty")
        return None

    # Try extract first group of digits
    m = re.search(r'(\d+)', content)
    if m:
        return f"COM{m.group(1)}"

    # Fallbacks
    if content.upper().startswith('COM'):
        return content
    return content
