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
BITBUCKET_API_BASE_URL = "https://api.bitbucket.org/2.0"
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
    """Gets structured feedback from the Gemini API for the given diff."""
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"Please review the following code diff and provide your feedback. If the changes are good and can be approved, please respond with only the word 'approve'. Otherwise, provide your comments for changes in a JSON array format, where each object in the array has 'file_path', 'line_number', and 'comment' keys. Example: [{{ \"file_path\": \"path/to/file.py\", \"line_number\": 10, \"comment\": \"This is a comment.\" }}]\n\n{diff}"
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
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and i < retries - 1:
                print(f"Rate limit exceeded. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2
            else:
                print(f"Error calling Gemini API: {e}")
                raise

def post_inline_comment(pr, file_path, line_number, comment, email, api_token, workspace, repo_slug):
    """Posts an inline comment to a pull request."""
    url = f"{BITBUCKET_API_BASE_URL}/repositories/{workspace}/{repo_slug}/pullrequests/{pr.id}/comments"
    headers = {"Content-Type": "application/json"}
    payload = {
        "content": {"raw": comment},
        "inline": {"path": file_path, "to": line_number},
    }
    response = requests.post(
        url, headers=headers, data=json.dumps(payload), auth=(email, api_token)
    )
    response.raise_for_status()

def post_general_comment(pr, comment, email, api_token, workspace, repo_slug):
    """Posts a general comment to a pull request."""
    url = f"{BITBUCKET_API_BASE_URL}/repositories/{workspace}/{repo_slug}/pullrequests/{pr.id}/comments"
    headers = {"Content-Type": "application/json"}
    payload = {"content": {"raw": comment}}
    response = requests.post(
        url, headers=headers, data=json.dumps(payload), auth=(email, api_token)
    )
    response.raise_for_status()

def has_user_interacted(pr, user_uuid, email, api_token, workspace, repo_slug):
    """Checks if the user has already approved or commented on the PR."""
    activity_url = f"{BITBUCKET_API_BASE_URL}/repositories/{workspace}/{repo_slug}/pullrequests/{pr.id}/activity"
    response = requests.get(activity_url, auth=(email, api_token))
    response.raise_for_status()
    for activity in response.json().get("values", []):
        # Check for approvals
        if "approval" in activity and activity["approval"]["user"]["uuid"] == user_uuid:
            return True, "Already approved."
        # Check for comments
        if "comment" in activity and activity["comment"]["user"]["uuid"] == user_uuid:
            return True, "Already commented."

    return False, None

def main():
    """Main function to review and approve pull requests."""
    email, api_token = get_credentials()
    workspace = input("Enter your Bitbucket workspace: ")
    repo_slug = input("Enter your Bitbucket repository slug: ")

    gemini_creds = get_gemini_credentials()

    try:
        print("Connecting to Bitbucket...")
        
        # Get user info directly via API call
        user_info_url = f"{BITBUCKET_API_BASE_URL}/user"
        response = requests.get(user_info_url, auth=(email, api_token))
        response.raise_for_status()
        user_info = response.json()
        user_uuid = user_info["uuid"]
        print(f"Connected as {user_info['display_name']}.")

        # We still need the bitbucket object to get the pull requests
        bitbucket = Cloud(username=email, password=api_token)
        repo = bitbucket.repositories.get(workspace, repo_slug)
        pull_requests = list(repo.pullrequests.each())
        print(f"Found {len(pull_requests)} open pull requests.")

        print("\n--- Pull Request Review Summary ---")

        for pr in pull_requests:
            print(f"\nChecking PR: {pr.title}")
            
            interacted, reason = has_user_interacted(pr, user_uuid, email, api_token, workspace, repo_slug)
            if interacted:
                print(f"Skipping PR: {reason}")
                continue

            print(f"Reviewing PR: {pr.title}")
            diff = pr.diff()

            try:
                feedback = get_gemini_feedback(diff, gemini_creds)

                if feedback.lower() == "approve":
                    print("PR is approvable. Skipping.")
                else:
                    print("--- DEBUG: Raw feedback from Gemini ---")
                    print(feedback)
                    print("----------------------------------------")
                    try:
                        # The Gemini API might return the JSON in a code block, so we need to extract it.
                        if feedback.startswith("```json"):
                            feedback = feedback[7:-4]

                        comments = json.loads(feedback)
                        for comment in comments:
                            print(
                                f"Adding comment to {comment['file_path']}:{comment['line_number']}: {comment['comment']}"
                            )
                            post_inline_comment(
                                pr,
                                comment["file_path"],
                                comment["line_number"],
                                comment["comment"],
                                email,
                                api_token,
                                workspace,
                                repo_slug,
                            )
                        print("All comments added.")
                    except json.JSONDecodeError:
                        print("Could not parse Gemini's feedback as JSON. Posting as a general comment.")
                        post_general_comment(pr, feedback, email, api_token, workspace, repo_slug)

            except Exception as e:
                print(f"Could not get feedback for PR: {pr.title}. Error: {e}")

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