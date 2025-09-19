import os
import subprocess
import sys
import time

def install_missing_libraries():
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

install_missing_libraries()

import requests
import json
from atlassian.bitbucket import Cloud
from atlassian.errors import ApiError
import google.auth
from google_auth_oauthlib.flow import InstalledAppFlow


# --- PLEASE CONFIGURE THESE VALUES --- #
# 1. Go to https://console.cloud.google.com/apis/credentials
# 2. Create an "OAuth 2.0 Client ID" for a "Desktop app".
# 3. Download the JSON file and save it as 'client_secret.json' in the same directory as this script.
CLIENT_SECRET_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/generative-language.retriever"]
GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent"
# --- END OF CONFIGURATION --- #

def get_credentials():
    """Gets Bitbucket credentials from the user."""
    email = input("Enter your Atlassian account email: ")
    api_token = input("Enter your Bitbucket API token: ")
    return email, api_token

def get_gemini_credentials():
    """Gets Gemini API credentials using OAuth 2.0."""
    if not os.path.exists(CLIENT_SECRET_FILE):
        raise FileNotFoundError(
            f"Please download your OAuth 2.0 client secret file and save it as '{CLIENT_SECRET_FILE}'."
        )

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    return creds

def get_gemini_feedback(diff, creds):
    """Gets feedback from the Gemini API for the given diff."""
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"Please review the following code diff and provide your feedback. If the changes are good and can be approved, please respond with only the word 'approve'. Otherwise, provide your comments for changes.:\n\n{diff}"
                    }
                ]
            }
        ]
    }

    retries = 5
    delay = 15  # seconds

    for i in range(retries):
        try:
            response = requests.post(GEMINI_API_ENDPOINT, headers=headers, json=data)
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and i < retries - 1:
                print(f"Rate limit exceeded. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                print(f"Error calling Gemini API: {e}")
                if e.response.status_code in [401, 403]:
                    print("This might be due to an authentication issue with the Gemini API.")
                raise

def main():
    """Main function to review and approve pull requests."""
    email, api_token = get_credentials()
    workspace = input("Enter your Bitbucket workspace: ")
    repo_slug = input("Enter your Bitbucket repository slug: ")

    gemini_creds = get_gemini_credentials()

    try:
        print("Connecting to Bitbucket...")
        bitbucket = Cloud(username=email, password=api_token)
        repo = bitbucket.repositories.get(workspace, repo_slug)
        pull_requests = list(repo.pullrequests.each())
        print("Successfully connected to Bitbucket.")

        if not pull_requests:
            print("No open pull requests found.")
            return

        print("Open Pull Requests:")
        for i, pr in enumerate(pull_requests):
            print(f"{i + 1}: {pr.title}")

        choice = int(input("Select a pull request to review (enter the number): "))
        selected_pr = pull_requests[choice - 1]

        diff = selected_pr.diff()
        print("\nGetting feedback from Gemini...")

        feedback = get_gemini_feedback(diff, gemini_creds)

        print(f"Gemini's feedback: {feedback}")

        if feedback.lower() == "approve":
            selected_pr.approve()
            print("\nPull request approved!")
        else:
            selected_pr.comments.create(content=feedback)
            print("\nComment added to the pull request.")

    except (ApiError, requests.exceptions.HTTPError) as e:
        print(f"Error connecting to Bitbucket: {e}")
        if hasattr(e, 'response') and e.response is not None and e.response.status_code in [401, 403]:
            print("This is likely due to an invalid or expired Bitbucket API token or insufficient permissions.")
        raise
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise

if __name__ == "__main__":
    main()