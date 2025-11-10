import subprocess
import sys

def install_needed_libraries():
    """Checks for required libraries and installs them if they are missing."""
    try:
        import requests
    except ImportError:
        print("requests is not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    try:
        from atlassian.bitbucket import Cloud
        from atlassian.errors import ApiError
    except ImportError:
        print("atlassian-python-api is not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "atlassian-python-api"])
    try:
        import google.auth
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("google-auth and google-auth-oauthlib are not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "google-auth", "google-auth-oauthlib"])
