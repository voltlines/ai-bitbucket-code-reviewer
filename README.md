# AI Bitbucket Code Reviewer

This script automates the process of reviewing pull requests in Bitbucket using the Gemini or Codex API. It can approve pull requests that look good, and it can also post comments with feedback on pull requests that need changes.

## Modes of Operation

The script has two modes of operation:

1. **Loop over opened PRs**: This mode will loop over all open pull requests in the specified repositories and review them.
2. **Review a specific PR**: This mode will review a single, specified pull request.
3. **Loop over all PRs in a specific time periods**: This mode will loop over all pull requests (even the merged ones) in the specified repositories and review them.

## Gemini Assist Authentication

The method used here requires a one-time setup to authorize the script.

Here’s what you need to do:

1. **Create an OAuth 2.0 Client ID**:

    * Go to the [Google Cloud Console Credentials page](https://console.cloud.google.com/apis/credentials).
    * Click on "+ CREATE CREDENTIALS" and select "OAuth client ID".
    * For the "Application type", choose "Desktop app".
    * Give it a name (e.g., "PR Reviewer Script").
    * Click "Create".
    * A window will pop up showing your client ID and secret. Click the "DOWNLOAD JSON" button to download the client secret file.
    * Rename the downloaded file to `client_secret.json` and place it in the same directory as the `pr_reviewer.py` script.

2. **Run the script**:

    * Once the `client_secret.json` file is in place, run the script as usual:

    ```bash
    python pr_reviewer.py
    ```

3. **Authorize the script**:

    * The first time you run the script, it will automatically open a new tab in your web browser.
    * Log in to the Google account you use for Gemini.
    * Grant the script permission to access the Gemini API.
    * After you grant permission, you can close the browser tab.

The script will then be authenticated and will proceed to fetch the pull requests. You will only need to do this authorization step once. On subsequent runs, the script will use the stored token to authenticate automatically.

## Codex Authentication

The codex api calls are using an API key, you can create your key from https://platform.openai.com

## Configuration

The script can be configured using a `.configs` file in the root directory. This file should contain the following key-value pairs:

```txt
BITBUCKET_EMAIL=your_email@example.com
BITBUCKET_API_TOKEN=your_api_token
BITBUCKET_WORKSPACE=your_workspace
PRINT_PROMPT_WHEN_AI_AGENT_FAIL=yes|no
AI_AGENT=AI_agent__gemini_or_codex
MODE=1
MODE_1_REPO_SLUG_LIST=your_repo_slug_1,your_repo_slug_2
MODE_2_REPO_SLUG=your_repo_slug
MODE_2_PR_ID=your_pr_id
MODE_3_REPO_SLUG_LIST=your_repo_slug_1,your_repo_slug_2
MODE_3_START_DATE=YYYY-MM-DD
MODE_3_END_DATE=YYYY-MM-DD
```

An example of this file can be found in `.configs_example`.

You can also configure the script using environment variables. The following environment variables are supported:

* `BITBUCKET_EMAIL`
* `BITBUCKET_API_TOKEN`
* `BITBUCKET_WORKSPACE`
* `PRINT_PROMPT_WHEN_AI_AGENT_FAIL`
* `AI_AGENT`
* `MODE`
* `MODE_1_REPO_SLUG_LIST`
* `MODE_2_REPO_SLUG`
* `MODE_2_PR_ID`
* `MODE_3_REPO_SLUG_LIST`
* `MODE_3_START_DATE`
* `MODE_3_END_DATE`

If a configuration value is not found in the environment variables or the `.configs` file, the script will prompt you for it.
rompt you for it.
