# Gemini Bitbucket Code Reviewer

This script automates the process of reviewing pull requests in Bitbucket using the Gemini API. It can approve pull requests that look good, and it can also post comments with feedback on pull requests that need changes.

## Gemini Assist Authentication

The method used here requires a one-time setup to authorize the script.

Here’s what you need to do:

1.  **Create an OAuth 2.0 Client ID**:

    *   Go to the [Google Cloud Console Credentials page](https://console.cloud.google.com/apis/credentials).
    *   Click on "+ CREATE CREDENTIALS" and select "OAuth client ID".
    *   For the "Application type", choose "Desktop app".
    *   Give it a name (e.g., "PR Reviewer Script").
    *   Click "Create".
    *   A window will pop up showing your client ID and secret. Click the "DOWNLOAD JSON" button to download the client secret file.
    *   Rename the downloaded file to `client_secret.json` and place it in the same directory as the `pr_reviewer.py` script.

2.  **Run the script**:

    *   Once the `client_secret.json` file is in place, run the script as usual:
        ```bash
        python pr_reviewer.py
        ```

3.  **Authorize the script**:

    *   The first time you run the script, it will automatically open a new tab in your web browser.
    *   Log in to the Google account you use for Gemini.
    *   Grant the script permission to access the Gemini API.
    *   After you grant permission, you can close the browser tab.

The script will then be authenticated and will proceed to fetch the pull requests. You will only need to do this authorization step once. On subsequent runs, the script will use the stored token to authenticate automatically.

## Configuration

The script can be configured using a `.configs` file in the root directory. This file should contain the following key-value pairs:

```
BITBUCKET_EMAIL=your_email@example.com
BITBUCKET_API_TOKEN=your_api_token
BITBUCKET_WORKSPACE=your_workspace
BITBUCKET_REPO_SLUG=your_repo_slug_1,your_repo_slug_2
```

An example of this file can be found in `.configs_example`.

You can also configure the script using environment variables. The following environment variables are supported:

*   `BITBUCKET_EMAIL`
*   `BITBUCKET_API_TOKEN`
*   `BITBUCKET_WORKSPACE`
*   `BITBUCKET_REPO_SLUG`

If a configuration value is not found in the environment variables or the `.configs` file, the script will prompt you for it.