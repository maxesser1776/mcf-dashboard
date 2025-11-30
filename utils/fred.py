from fredapi import Fred
import os
from dotenv import load_dotenv

load_dotenv()

# Wrapper to initialize Fred connection using env variable
def get_fred_connection():
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise ValueError("FRED_API_KEY environment variable not set")
    return Fred(api_key=api_key)