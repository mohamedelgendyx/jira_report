# Jira Configuration File
# ==========================================
# Edit this file to set your credentials and report parameters

# Jira Authentication
# ------------------------------------------
JIRA_URL = ""        # Your Jira instance URL (e.g., "https://your-domain.atlassian.net")
JIRA_EMAIL = ""      # Your Jira email address
JIRA_API_TOKEN = ""  # Your Jira API token

# Report Date Range
# ------------------------------------------
# Format: "YYYY-MM-DDThh:mm:ss±hh:mm" (ISO 8601)
REPORT_START_DATE = "2025-05-15T00:00:00+00:00"  # Start of the reporting period
REPORT_END_DATE = "2025-06-28T23:59:59+00:00"    # End of the reporting period

# Project filter (optional)
# Leave empty list [] to include all projects
PROJECT_KEYS = []  # Example: ["PROJ1", "PROJ2"]

# File Output Options
# ------------------------------------------
# Save report to file
SAVE_REPORT_TO_FILE = True
REPORT_FILE_PATH = "reports/"  # Directory to save reports (will be created if doesn't exist)
