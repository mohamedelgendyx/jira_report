# Jira Logged Hours Report

This project generates a detailed report of actual hours logged versus original estimates for Jira issues, grouped by team member and ticket.

## Features
- Fetches worklogs from Jira Cloud using REST API
- Summarizes hours logged by user and by ticket
- Compares actual hours to original estimates
- Outputs a detailed report to the console and optionally to a file

## Prerequisites
- Python 3.7+
- Access to a Jira Cloud instance
- A Jira API token ([create one here](https://id.atlassian.com/manage-profile/security/api-tokens))
- Your Jira email address

## Setup
1. **Clone the repository or copy the project files.**

2. **Install dependencies:**
   
   This script uses the `requests` library. Install it if you don't have it:
   ```sh
   pip install requests
   ```

3. **Configure Jira credentials and report settings:**
   
   - Copy `jira_config.sample.py` to `jira_config.py`:
     ```sh
     cp jira_config.sample.py jira_config.py
     ```
   - Open `jira_config.py` and fill in:
     - `JIRA_URL`: Your Jira instance URL (e.g., `https://your-domain.atlassian.net`)
     - `JIRA_EMAIL`: Your Jira email address
     - `JIRA_API_TOKEN`: Your Jira API token
     - `REPORT_START_DATE` and `REPORT_END_DATE`: The date range for the report (ISO 8601 format)
     - Optionally, set `PROJECT_KEYS` to filter by project(s)
     - Adjust file output options if needed

   **Note:** `jira_config.py` is ignored by version control. Do not share your credentials.

4. **(Optional) Create the reports directory:**
   The script will create the `reports/` directory automatically if it does not exist.

## Running the Report

Run the script from the project directory:

```sh
python logged_hours.py
```

- The report will be printed to the console.
- If `SAVE_REPORT_TO_FILE` is set to `True` in your config, the report will be saved in the `reports/` directory.

## Troubleshooting
- Ensure your Jira credentials and API token are correct.
- Make sure your Jira user has permission to view worklogs and issues in the selected projects.
- Dates must be in ISO 8601 format (e.g., `2025-05-15T00:00:00+00:00`).
- If you see errors about missing configuration, check that `jira_config.py` exists and is filled in.

## Security
- Never commit your `jira_config.py` with credentials to version control.
- Your API token is sensitive—treat it like a password.

## License
This project is for internal use. Adapt as needed for your organization.
