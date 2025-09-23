import utils
utils.install_needed_libraries()

import os
import time
from datetime import datetime
import json
import requests
from atlassian.bitbucket import Cloud
from atlassian.errors import ApiError
from google_auth_oauthlib.flow import InstalledAppFlow

# --- PLEASE CONFIGURE THESE VALUES --- #
# 1. Go to https://console.cloud.google.com/apis/credentials
# 2. Create an "OAuth 2.0 Client ID" for a "Desktop app".
# 3. Download the JSON file and save it as 'client_secret.json' in the same directory as this script.
CLIENT_SECRET_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/generative-language.retriever"]
GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent"
BITBUCKET_API_BASE_URL = "https://api.bitbucket.org/2.0"
# Codex (OpenAI) configuration
OPENAI_API_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENAI_DEFAULT_MODEL = "gpt-5-nano" #"gpt-4o-mini"
# --- END OF CONFIGURATION --- #

def get_config(config_name, prompt, is_list=False):
    """Gets a configuration value from environment variables, a .configs file, or user input."""
    # Try to get from environment variable
    value = os.environ.get(config_name)
    if value:
        value = value.strip()
        if value:
            if is_list:
                return [item.strip() for item in value.split(',')]
            return value

    # Try to get from .configs file
    try:
        with open(".configs", "r") as f:
            for line in f:
                if line.startswith(config_name + "="):
                    value = line.removeprefix(config_name + "=").strip()
                    if value:
                        if is_list:
                            return [item.strip() for item in value.split(',')]
                        return value
    except FileNotFoundError:
        pass

    # Fallback to user input
    value = input(prompt)
    if is_list:
        return [item.strip() for item in value.split(',')]
    return value

def get_credentials():
    """Gets Bitbucket credentials from the user."""
    email = get_config("BITBUCKET_EMAIL", "Enter your Atlassian account email: ")
    api_token = get_config("BITBUCKET_API_TOKEN", "Enter your Bitbucket API token: ")
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
    prompt = f"""Please review the following code diff and provide your feedback (only critical). ignore submodule changes and don't comment on them. If the changes are good and can be approved, please respond with only the word 'approve'. 
    Otherwise, provide your comments for changes in a JSON array format, where each object in the array has 'file_path', 'line_content', and 'comment' keys. 
    The line_content should be the exact line from the diff that the comment is about and it should be one line without new line characters.
    Example:
    ```json
    [
        {{
            "file_path": "path/to/file.py",
            "line_content": "...",
            "comment": "This is a comment."
        }}
    ]
    ```
    
    Here is the diff:
    {diff}
    """
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
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
            elif e.response.status_code == 503 and i < retries - 1:
                print(f"Gemini API returned 503. Retrying... ({retries - i - 1} retries left)")
                time.sleep(5)
            elif i == retries - 1:
                print("Gemini API is unavailable after multiple retries.")
                print_prompt_when_ai_agent_fail = get_config("PRINT_PROMPT_WHEN_AI_AGENT_FAIL", "Would you like to get the complete Gemini/Codex prompt to get the feedback on your own? (yes/no): ")
                if print_prompt_when_ai_agent_fail.lower() == 'yes':
                    print("\n--- Gemini Prompt ---\n")
                    print(prompt)
                    print("\n--- End of Gemini Prompt ---")
                raise
            else:
                print(f"Error calling Gemini API: {e}")
                raise

def get_codex_credentials():
    """Gets OpenAI (Codex) API key from the user/environment."""
    api_key = get_config("OPENAI_API_KEY", "Enter your OpenAI API key: ")
    return api_key

def get_codex_feedback(diff, api_key):
    """Gets structured feedback from OpenAI (Codex) for the given diff."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    prompt = f"""Please review the following code diff and provide your feedback (only critical). ignore submodule changes and don't comment on them. If the changes are good and can be approved, please respond with only the word 'approve'. 
    Otherwise, provide your comments for changes in a JSON array format, where each object in the array has 'file_path', 'line_content', and 'comment' keys. 
    The line_content should be the exact line from the diff that the comment is about and it should be one line without new line characters.
    Example:
    ```json
    [
        {{
            "file_path": "path/to/file.py",
            "line_content": "...",
            "comment": "This is a comment."
        }}
    ]
    ```
    
    Here is the diff:
    {diff}
    """

    body = {
        "model": OPENAI_DEFAULT_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
    }

    retries = 5
    delay = 15  # seconds

    for i in range(retries):
        try:
            response = requests.post(OPENAI_API_ENDPOINT, headers=headers, json=body)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429 and i < retries - 1:
                print(f"OpenAI rate limit exceeded. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2
            elif e.response is not None and e.response.status_code == 503 and i < retries - 1:
                print(f"OpenAI API returned 503. Retrying... ({retries - i - 1} retries left)")
                time.sleep(5)
            elif i == retries - 1:
                print("OpenAI API is unavailable after multiple retries.")
                raise
            else:
                print(f"Error calling OpenAI API: {e}")
                raise

def parse_ai_feedback(feedback):
    """Parses the feedback from the AI agent API."""
    if feedback.lower() == "approve":
        return "approve", None
    
    try:
        if feedback.startswith("```json"):
            feedback = feedback[7:-4]
        return "comment", json.loads(feedback)
    except json.JSONDecodeError:
        return "comment", feedback

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

def already_commented_on_line(pr, file_path, line_number, email, api_token, workspace, repo_slug):
    """Returns True if an identical inline comment already exists on the given file/line."""
    url = f"{BITBUCKET_API_BASE_URL}/repositories/{workspace}/{repo_slug}/pullrequests/{pr.id}/comments"
    next_url = url

    while next_url:
        response = requests.get(next_url, auth=(email, api_token))
        response.raise_for_status()
        data = response.json()

        for c in data.get("values", []):
            inline = c.get("inline") or {}
            path = inline.get("path")
            to_line = inline.get("to")

            if path == file_path and to_line == line_number:
                return True

        next_url = data.get("next")

    return False

def parse_diff(diff_text):
    """Parses the diff text and returns a map of file paths to their hunks."""
    files = {}
    current_file = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            current_file = line.split(" b/")[1]
            files[current_file] = []
        elif line.startswith("@@") and current_file:
            parts = line.split(" ")
            new_start_line = int(parts[2].split(",")[0][1:])
            files[current_file].append({"new_start_line": new_start_line, "lines": []})
        elif current_file and files[current_file]:
            files[current_file][-1]["lines"].append(line)
    return files

def review_pr(pr, user_uuid, email, api_token, workspace, repo_slug, ai_agent, ai_creds, skip_if_user_interacted):
    """Reviews a single pull request."""
    print(f"\nChecking PR: {pr.title}")
    print(f"URL: https://bitbucket.org/{workspace}/{repo_slug}/pull-requests/{pr.id}/")
    
    if skip_if_user_interacted:
        interacted, reason = has_user_interacted(pr, user_uuid, email, api_token, workspace, repo_slug)
        if interacted:
            print(f"Skipping PR: {reason}")
            return

    print(f"Reviewing PR: {pr.title}")
    diff = pr.diff()
    parsed_diff = parse_diff(diff)

    try:
        if str(ai_agent).lower() == "codex":
            feedback = get_codex_feedback(diff, ai_creds)
        else:
            feedback = get_gemini_feedback(diff, ai_creds)
        action, comments = parse_ai_feedback(feedback)

        if action == "approve":
            pr.approve()
            print(f"PR approved.")
        elif isinstance(comments, list):
            added_comments_counter = 0
            for comment in comments:
                file_path = comment["file_path"]
                line_content = comment["line_content"].strip()
                comment_text = comment["comment"]
                comment_posted = False

                if not line_content:
                    continue

                if file_path in parsed_diff:
                    for hunk in parsed_diff[file_path]:
                        current_line_in_new_file = hunk["new_start_line"]
                        for line in hunk["lines"]:
                            # Strip leading '+' or '-' to match content
                            stripped_line = line[1:].strip() if line.startswith(('+', '-')) else line.strip()
                            if stripped_line == line_content:
                                if already_commented_on_line(pr, file_path, current_line_in_new_file, email, api_token, workspace, repo_slug):
                                    print(f"Skipping duplicate comment on {file_path}:{current_line_in_new_file}")
                                    comment_posted = True
                                    break

                                post_inline_comment(
                                    pr,
                                    file_path,
                                    current_line_in_new_file,
                                    comment_text,
                                    email,
                                    api_token,
                                    workspace,
                                    repo_slug,
                                )
                                comment_posted = True
                                added_comments_counter += 1
                                break
                            if line.startswith("+") or line.startswith(" "):
                                current_line_in_new_file += 1
                        if comment_posted:
                            break
                
                if not comment_posted:
                    print(f"Warning: Could not find line with content '{line_content}' in file {file_path} to post a comment.")
                    print(f"Gemini review comment: '{comment_text}'")

            print(f"{added_comments_counter} comments were added.")
        else:
            print("Could not parse Gemini's feedback as JSON. Posting as a general comment.")
            post_general_comment(pr, feedback, email, api_token, workspace, repo_slug)

    except Exception as e:
        print(f"Could not get feedback for PR: {pr.title}. Error: {e}")

def get_mode():
    """Gets the desired mode of operation from the user."""
    while True:
        mode = get_config("MODE", "Please select a mode:\n1. Loop over opened PRs.\n2. Review a specific PR.\n3. Loop over all PRs in a specific time periods.\nEnter 1, 2, or 3: ")
        if mode in ["1", "2", "3"]:
            return int(mode)
        else:
            print("Invalid mode selected. Please try again.")

def main():
    """Main function to review and approve pull requests."""
    email, api_token = get_credentials()
    workspace = get_config("BITBUCKET_WORKSPACE", "Enter your Bitbucket workspace:")

    try:
        print("Connecting to Bitbucket...")
        
        user_info_url = f"{BITBUCKET_API_BASE_URL}/user"
        response = requests.get(user_info_url, auth=(email, api_token))
        response.raise_for_status()
        user_info = response.json()
        user_uuid = user_info["uuid"]
        print(f"Connected as {user_info['display_name']}.")

        bitbucket = Cloud(username=email, password=api_token)
        
        mode = get_mode()

        ai_agent = get_config("AI_AGENT", "Select AI agent (Gemini/Codex): ") or "Gemini"
        ai_agent_norm = ai_agent.strip().lower()
        if ai_agent_norm not in ("gemini", "codex"):
            print("Unknown AI agent selected; defaulting to Gemini.")
            ai_agent_norm = "gemini"

        if ai_agent_norm == "codex":
            ai_creds = get_codex_credentials()
        else:
            ai_creds = get_gemini_credentials()
        if mode == 1:
            repo_slugs = get_config("MODE_1_REPO_SLUG_LIST", "Enter your Bitbucket repository slug(s) (comma-separated): ", is_list=True)
            for repo_slug in repo_slugs:
                print(f"\n--- Processing repository: {repo_slug} ---")
                try:
                    repo = bitbucket.repositories.get(workspace, repo_slug)
                    pull_requests = list(repo.pullrequests.each())
                    
                    if not pull_requests:
                        print("No open pull requests found.")
                        continue

                    print(f"Found {len(pull_requests)} open pull requests.")

                    print("\n--- Pull Request Review Summary ---")

                    for pr in pull_requests:
                        review_pr(pr, user_uuid, email, api_token, workspace, repo_slug, ai_agent_norm, ai_creds, True)
                except Exception as e:
                    print(f"Error processing repository {repo_slug}: {e}")
        elif mode == 3:
            repo_slugs = get_config("MODE_3_REPO_SLUG_LIST", "Enter your Bitbucket repository slug(s) (comma-separated): ", is_list=True)
            start_date = get_config("MODE_3_START_DATE", "Enter your start date (YYYY-MM-DD): ") + "T00:00:00-00:00"
            end_date = get_config("MODE_3_END_DATE", "Enter your end date (YYYY-MM-DD): ") + "T23:59:59-00:00"
            for repo_slug in repo_slugs:
                print(f"\n--- Processing repository: {repo_slug} ---")
                try:
                    repo = bitbucket.repositories.get(workspace, repo_slug)
                    pull_requests = list(repo.pullrequests.each(f"created_on >= {start_date} AND created_on <= {end_date}"))
                    if not pull_requests:
                        print("No pull requests found.")
                        continue

                    print(f"Found {len(pull_requests)} pull requests.")

                    print("\n--- Pull Request Review Summary ---")

                    for pr in pull_requests:
                        review_pr(pr, user_uuid, email, api_token, workspace, repo_slug, ai_agent_norm, ai_creds, True)
                except Exception as e:
                    print(f"Error processing repository {repo_slug}: {e}")
        
        elif mode == 2:
            repo_slug = get_config("MODE_2_REPO_SLUG", "Enter the repository slug for the PR: ")
            pr_id = get_config("MODE_2_PR_ID", "Enter the PR ID: ")
            try:
                repo = bitbucket.repositories.get(workspace, repo_slug)
                pr = repo.pullrequests.get(pr_id)
                review_pr(pr, user_uuid, email, api_token, workspace, repo_slug, ai_agent_norm, ai_creds, False)
            except Exception as e:
                print(f"Error processing PR #{pr_id} in repository {repo_slug}: {e}")


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
