import requests
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import sys
import os
import argparse
import re

# Try to import configuration from jira_config.py
try:
    import jira_config as config
    
    # Validate that required config variables exist
    required_vars = [
        'JIRA_URL', 'JIRA_EMAIL', 'JIRA_API_TOKEN'
    ]
    
    missing_vars = [var for var in required_vars if not hasattr(config, var) or getattr(config, var) == ""]
    
    if missing_vars:
        print(f"Error: Missing required configuration variables: {', '.join(missing_vars)}")
        print("Please update the jira_config.py file with your settings.")
        sys.exit(1)
    
except ImportError:
    print("Error: Could not find jira_config.py file.")
    print("Please ensure jira_config.py is in the same directory as this script.")
    sys.exit(1)

# Load configuration
base_url = config.JIRA_URL
email = config.JIRA_EMAIL
api_token = config.JIRA_API_TOKEN
project_keys = getattr(config, 'PROJECT_KEYS', [])

# File output options
save_report_to_file = getattr(config, 'SAVE_REPORT_TO_FILE', True)
report_file_path = getattr(config, 'REPORT_FILE_PATH', "reports/")

# Statuses to exclude from estimation
excluded_statuses = getattr(config, 'EXCLUDED_STATUSES', ["Won't Do", "Won't Fix", "Cancelled"])

# Authentication setup
auth = HTTPBasicAuth(email, api_token)
headers = {
   "Accept": "application/json",
   "Content-Type": "application/json"
}


def parse_arguments():
    """Parse command line arguments for report configuration"""
    parser = argparse.ArgumentParser(description='Generate Jira time report')
    
    # Create a mutually exclusive group for input methods
    input_group = parser.add_mutually_exclusive_group(required=True)
    
    # Command line arguments
    input_group.add_argument('--from-date', dest='from_date',
                        help='Start date for the report (format: DD MMM YYYY, e.g., 25 May 2025)')
    
    parser.add_argument('--to-date', dest='to_date',
                        help='End date for the report (format: DD MMM YYYY, e.g., 15 Jun 2025)')
    
    parser.add_argument('--participants', nargs='+',
                        help='List of participants with availability in format "Name (Available for X hours)"')
    
    # File-based input option
    input_group.add_argument('--args-file', dest='args_file',
                        help='Path to a file containing the report parameters')
    
    args = parser.parse_args()
    
    # If using a file for arguments, parse it
    if args.args_file:
        from_date, to_date, participants = parse_args_file(args.args_file)
        args.from_date = from_date
        args.to_date = to_date
        args.participants = participants
    elif not all([args.from_date, args.to_date, args.participants]):
        parser.error("When not using --args-file, all of --from-date, --to-date, and --participants are required")
    
    return args


def parse_args_file(file_path):
    """Parse report parameters from a file"""
    try:
        with open(file_path, 'r') as file:
            content = file.read()
            
            # Extract from date
            from_match = re.search(r'From:\s*(.*?)$', content, re.MULTILINE)
            if not from_match:
                raise ValueError("Could not find 'From:' date in the file")
            from_date = from_match.group(1).strip()
            
            # Extract to date
            to_match = re.search(r'To:\s*(.*?)$', content, re.MULTILINE)
            if not to_match:
                raise ValueError("Could not find 'To:' date in the file")
            to_date = to_match.group(1).strip()
            
            # Extract participants
            participants_match = re.search(r'Participant Names:(.*?)(?=\n\n|\Z)', content, re.DOTALL)
            if not participants_match:
                raise ValueError("Could not find 'Participant Names:' section in the file")
            
            participants_text = participants_match.group(1).strip()
            participants = [p.strip() for p in participants_text.split('\n') if p.strip()]
            
            # Add year to dates if not present
            from_date = add_year_if_needed(from_date)
            to_date = add_year_if_needed(to_date)
            
            return from_date, to_date, participants
            
    except Exception as e:
        print(f"Error parsing arguments file: {e}")
        sys.exit(1)


def add_year_if_needed(date_str):
    """Add current year to date if not present"""
    if not re.search(r'\d{4}', date_str):
        current_year = datetime.now().year
        date_str += f" {current_year}"
    return date_str


def parse_participant_info(participant_str):
    """Extract name and availability from participant string"""
    match = re.match(r'(.+?)\s*\(Available for (\d+) hours\)', participant_str)
    if match:
        name = match.group(1).strip()
        availability = int(match.group(2))
        return name, availability
    else:
        # If no availability specified, assume default
        return participant_str.strip(), 80  # Default to 80 hours


def convert_date_format(date_str):
    """Convert date from '25 May 2025' to ISO format '2025-05-25T00:00:00+00:00'"""
    try:
        # Try various date formats
        for fmt in ["%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y"]:
            try:
                date_obj = datetime.strptime(date_str, fmt)
                return date_obj.replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                continue
                
        raise ValueError(f"Could not parse date: {date_str}")
    except Exception as e:
        print(f"Error: Invalid date format '{date_str}'. Error: {e}")
        print("Please use format like '25 May 2025' or '25 May'")
        sys.exit(1)


def main():
    """Main function to run the enhanced Jira time report"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Process participants
    participants = {}
    for p in args.participants:
        name, availability = parse_participant_info(p)
        participants[name] = availability
    
    # Convert dates to ISO format
    start_date_str = convert_date_format(args.from_date)
    end_date_str = convert_date_format(args.to_date)
    
    print("\nJIRA TIME REPORT - ACTUALS vs ESTIMATES")
    print("=" * 60)
    
    # Parse the reporting period dates
    start_date, end_date = parse_date_range(start_date_str, end_date_str)
    
    print(f"Period: {start_date.date()} to {end_date.date()}")
    print(f"Projects: {', '.join(project_keys) if project_keys else 'All projects'}")
    print(f"Participants: {', '.join([f'{name} ({hours}h)' for name, hours in participants.items()])}")
    print(f"Excluded Statuses: {', '.join(excluded_statuses)}")
    print("=" * 60)
    
    # Build JQL query and fetch issues
    jql = build_jql_query(project_keys, start_date, end_date)
    issues = fetch_all_issues(jql)
    
    # Organize issues by type (Epic, Story, Subtask, etc.)
    issues_by_type, parent_child_map = organize_issues_by_type(issues)
    
    # Process worklogs and get actuals
    user_hours, user_names, issue_hours, user_issue_hours = process_worklogs(issues, start_date, end_date)
    
    # Add participants with zero hours if they're missing
    for participant_name in participants.keys():
        # Try to find the participant by display name
        user_id = None
        for uid, name in user_names.items():
            if name.lower() == participant_name.lower():
                user_id = uid
                break
        
        # If participant not found, create a placeholder
        if user_id is None:
            user_id = f"placeholder_{participant_name}"
            user_names[user_id] = participant_name
            user_hours[user_id] = 0
            user_issue_hours[user_id] = {}
    
    # Calculate estimates and actuals for stories based on subtasks
    recalculate_story_metrics(issues_by_type, parent_child_map, issue_hours)
    
    # Calculate user estimates based on tickets they worked on
    user_estimates = calculate_user_estimates(user_issue_hours, issues)
    
    # Fetch comments for issues with deviation (only positive variance)
    issue_deviation_reasons = fetch_deviation_reasons(issues, issue_hours)
    
    # Generate report
    report_text = generate_report(
        issues, user_hours, user_names, issue_hours, user_issue_hours, 
        user_estimates, participants, issues_by_type, issue_deviation_reasons
    )
    
    # Print report
    print(report_text)
    
    # Save report to file if enabled
    if save_report_to_file:
        save_report(report_text, start_date, end_date)


def parse_date_range(start_date_str, end_date_str):
    """Parse and validate the report date range"""
    try:
        start_date = datetime.fromisoformat(start_date_str)
        end_date = datetime.fromisoformat(end_date_str)
        
        # Ensure dates have timezone info
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        
        # Make end_date inclusive if it's set to midnight
        if end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        return start_date, end_date
        
    except ValueError as e:
        print(f"Error parsing report dates: {e}")
        print("Please use ISO format: YYYY-MM-DDThh:mm:ss±hh:mm")
        sys.exit(1)


def build_jql_query(project_keys, start_date, end_date):
    """Build the JQL query to find relevant issues"""
    jql_parts = []

    # Add project filter if specified
    if project_keys:
        if len(project_keys) == 1:
            jql_parts.append(f"project = {project_keys[0]}")
        else:
            jql_parts.append(f"project in ({','.join(project_keys)})")

    # Add date range filter for worklogs
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    date_clause = f"worklogDate >= '{start_date_str}' AND worklogDate <= '{end_date_str}'"
    jql_parts.append(f"({date_clause})")

    # Combine JQL parts
    jql = " AND ".join(jql_parts)
    print(f"JQL query: {jql}")
    
    return jql


def fetch_all_issues(jql):
    """Fetch all issues matching the JQL query"""
    issues_url = f"{base_url}/rest/api/3/search"
    
    # Include fields needed for the report
    fields = [
        "key", "summary", "issuetype", "assignee", "status",
        "timeoriginalestimate", "timeestimate", "timespent",
        "parent", "issuelinks", "subtasks"
    ]
    
    issues_query = {
        "jql": jql,
        "fields": fields,
        "maxResults": 100,
    }

    print(f"Fetching issues...")
    all_issues = []
    start_at = 0
    total = None

    while total is None or start_at < total:
        issues_query["startAt"] = start_at
        
        response = requests.post(
            issues_url,
            headers=headers,
            auth=auth,
            json=issues_query
        )
        
        if response.status_code != 200:
            print(f"Error fetching issues: {response.status_code}")
            print(response.text)
            sys.exit(1)
            
        data = response.json()
        
        if total is None:
            total = data["total"]
            print(f"Found {total} issues with worklogs in the period")
        
        all_issues.extend(data["issues"])
        start_at += len(data["issues"])
        
        if len(data["issues"]) == 0:
            break

    print(f"Fetched {len(all_issues)} issues")
    
    # Also fetch subtasks of stories that might not have worklogs themselves
    subtasks = fetch_additional_subtasks(all_issues)
    if subtasks:
        all_issues.extend(subtasks)
        print(f"Added {len(subtasks)} additional subtasks for stories")
    
    return all_issues


def fetch_additional_subtasks(issues):
    """Fetch subtasks for stories that may not have worklogs themselves"""
    # Find stories that need their subtasks fetched
    story_keys = []
    for issue in issues:
        if issue["fields"]["issuetype"]["name"] == "Story":
            # If this story has subtasks field but we don't have details
            if "subtasks" in issue["fields"] and issue["fields"]["subtasks"]:
                subtask_keys = [st["key"] for st in issue["fields"]["subtasks"]]
                story_keys.append(issue["key"])
    
    if not story_keys:
        return []
    
    # Build JQL to fetch all subtasks for these stories
    jql = f"parent in ({','.join(story_keys)})"
    
    # Include fields needed for subtasks
    fields = [
        "key", "summary", "issuetype", "status",
        "timeoriginalestimate", "timeestimate", "timespent",
        "parent"
    ]
    
    issues_query = {
        "jql": jql,
        "fields": fields,
        "maxResults": 100
    }
    
    issues_url = f"{base_url}/rest/api/3/search"
    
    print(f"Fetching additional subtasks for stories...")
    all_subtasks = []
    start_at = 0
    total = None
    
    while total is None or start_at < total:
        issues_query["startAt"] = start_at
        
        response = requests.post(
            issues_url,
            headers=headers,
            auth=auth,
            json=issues_query
        )
        
        if response.status_code != 200:
            print(f"Error fetching subtasks: {response.status_code}")
            print(response.text)
            return all_subtasks
            
        data = response.json()
        
        if total is None:
            total = data["total"]
            
        all_subtasks.extend(data["issues"])
        start_at += len(data["issues"])
        
        if len(data["issues"]) == 0:
            break
    
    return all_subtasks


def organize_issues_by_type(issues):
    """Organize issues by their type and build parent-child relationship map"""
    issues_by_type = defaultdict(list)
    parent_child_map = defaultdict(list)
    
    # First pass: categorize issues by type
    for issue in issues:
        issue_type = issue["fields"]["issuetype"]["name"]
        issues_by_type[issue_type].append(issue)
        
        # Build parent-child relationships
        if "parent" in issue["fields"]:
            parent_key = issue["fields"]["parent"]["key"]
            parent_child_map[parent_key].append(issue["key"])
    
    return issues_by_type, parent_child_map


def process_worklogs(issues, start_date, end_date):
    """Process worklogs for all issues"""
    user_hours = defaultdict(float)  # Total hours per user
    user_names = {}  # User display names
    issue_hours = {}  # Total hours per issue
    user_issue_hours = defaultdict(lambda: defaultdict(float))  # Hours per user per issue
    
    print(f"\nProcessing worklogs...")
    
    for i, issue in enumerate(issues):
        issue_key = issue["key"]
        
        # Fetch worklogs for this issue
        worklog_url = f"{base_url}/rest/api/3/issue/{issue_key}/worklog"
        
        response = requests.get(worklog_url, headers=headers, auth=auth)
        
        if response.status_code != 200:
            print(f"Error fetching worklogs for {issue_key}: {response.status_code}")
            continue
        
        worklog_data = response.json()
        issue_total_hours = 0
        
        # Process each worklog entry
        for worklog in worklog_data["worklogs"]:
            # Parse worklog date
            try:
                worklog_started = datetime.fromisoformat(worklog["started"].replace('Z', '+00:00'))
            except ValueError:
                continue
            
            # Check if worklog is in our date range
            if start_date <= worklog_started <= end_date:
                user_id = worklog["author"]["accountId"]
                user_name = worklog["author"]["displayName"]
                hours = worklog["timeSpentSeconds"] / 3600
                
                user_hours[user_id] += hours
                user_names[user_id] = user_name
                user_issue_hours[user_id][issue_key] += hours
                issue_total_hours += hours
        
        if issue_total_hours > 0:
            issue_hours[issue_key] = issue_total_hours
        
        if (i + 1) % 10 == 0 or (i + 1) == len(issues):
            print(f"Processed {i + 1}/{len(issues)} issues")

    return user_hours, user_names, issue_hours, user_issue_hours


def recalculate_story_metrics(issues_by_type, parent_child_map, issue_hours):
    """Recalculate estimates and actuals for stories based on subtasks"""
    print("\nRecalculating story metrics based on subtasks...")
    stories_recalculated = 0
    
    # Process stories
    if "Story" in issues_by_type:
        for story in issues_by_type["Story"]:
            story_key = story["key"]
            
            # If the story has subtasks, calculate based on them
            if story_key in parent_child_map and parent_child_map[story_key]:
                # For stories, we'll calculate the time differently
                subtask_total_estimate = 0
                subtask_total_actual = 0
                valid_subtasks = 0
                
                # Sum up from all valid subtasks
                for subtask_key in parent_child_map[story_key]:
                    # Find the subtask
                    subtask = None
                    for st in issues_by_type.get("Subtask", []):
                        if st["key"] == subtask_key:
                            subtask = st
                            break
                    
                    if subtask:
                        # Check if subtask status is not in excluded list
                        status_name = subtask["fields"]["status"]["name"]
                        if status_name not in excluded_statuses:
                            valid_subtasks += 1
                            
                            # Add to estimates
                            estimate = get_estimate_hours(subtask["fields"].get("timeoriginalestimate"))
                            subtask_total_estimate += estimate
                            
                            # Add to actuals
                            if subtask_key in issue_hours:
                                subtask_total_actual += issue_hours[subtask_key]
                
                if valid_subtasks > 0:
                    # Override the story's original estimate with sum of subtasks
                    story["fields"]["timeoriginalestimate"] = subtask_total_estimate * 3600
                    
                    # Update or add the story's actual hours
                    if subtask_total_actual > 0:
                        issue_hours[story_key] = subtask_total_actual
                    
                    stories_recalculated += 1
    
    print(f"Recalculated metrics for {stories_recalculated} stories based on their subtasks")
    if stories_recalculated > 0:
        print(f"Excluded statuses: {', '.join(excluded_statuses)}")


def calculate_user_estimates(user_issue_hours, issues):
    """Calculate total estimated hours for each user based on tickets they worked on"""
    user_estimates = defaultdict(float)
    issue_lookup = {issue["key"]: issue for issue in issues}
    
    # For each user, sum up the original estimates for tickets they worked on
    for user_id, tickets in user_issue_hours.items():
        for issue_key in tickets.keys():
            if issue_key in issue_lookup:
                issue = issue_lookup[issue_key]
                original_estimate = get_estimate_hours(issue["fields"].get("timeoriginalestimate"))
                if original_estimate > 0:
                    # Add the full estimate to the user's total
                    # Note: This means if multiple people work on the same ticket,
                    # the estimate is counted for each person
                    user_estimates[user_id] += original_estimate
    
    return user_estimates


def fetch_deviation_reasons(issues, issue_hours):
    """Fetch comments for issues with significant deviation to find reasons (only positive variance)"""
    issue_deviation_reasons = {}
    issue_lookup = {issue["key"]: issue for issue in issues}
    
    print("\nChecking for deviation reasons in comments...")
    deviations_found = 0
    
    for issue_key, actual_hours in issue_hours.items():
        if issue_key in issue_lookup:
            issue = issue_lookup[issue_key]
            original_estimate = get_estimate_hours(issue["fields"].get("timeoriginalestimate"))
            
            # Check if there's a significant deviation (more than 20%) AND actual > estimate
            # Only look for reasons when actual > estimate (positive variance)
            if original_estimate > 0 and actual_hours > original_estimate and actual_hours / original_estimate > 1.2:
                # Fetch comments to look for deviation reasons
                comments_url = f"{base_url}/rest/api/3/issue/{issue_key}/comment"
                response = requests.get(comments_url, headers=headers, auth=auth)
                
                if response.status_code == 200:
                    comments_data = response.json()
                    
                    # Look for comments that might explain deviation
                    deviation_reason = ""
                    for comment in comments_data.get("comments", []):
                        # Look for comments mentioning estimation or time
                        comment_text = extract_text_from_comment(comment)
                        if any(keyword in comment_text.lower() for keyword in 
                               ["estimate", "time", "hours", "deviation", "took longer", 
                                "delay", "delayed", "blocked", "blocker", "underestimate", 
                                "overestimate"]):
                            deviation_reason = comment_text[:200] + "..." if len(comment_text) > 200 else comment_text
                            deviations_found += 1
                            break
                    
                    issue_deviation_reasons[issue_key] = deviation_reason
    
    print(f"Found deviation reasons for {deviations_found} issues")
    return issue_deviation_reasons


def extract_text_from_comment(comment):
    """Extract plain text from a Jira comment (which could be in Atlassian Document Format)"""
    if "body" in comment:
        if isinstance(comment["body"], str):
            return comment["body"]
        elif isinstance(comment["body"], dict) and "content" in comment["body"]:
            # This is Atlassian Document Format, extract text
            text = ""
            for content in comment["body"]["content"]:
                if content.get("type") == "paragraph" and "content" in content:
                    for text_content in content["content"]:
                        if text_content.get("type") == "text":
                            text += text_content.get("text", "")
            return text
    return ""


def get_estimate_hours(time_seconds):
    """Convert time estimate from seconds to hours"""
    if time_seconds:
        return time_seconds / 3600
    return 0


def format_time(hours):
    """Format hours as hours and days"""
    if hours == 0:
        return "0h"
    
    days = hours / 8  # Assuming 8-hour work days
    if days >= 1:
        return f"{hours:.1f}h ({days:.1f}d)"
    else:
        return f"{hours:.1f}h"

def generate_report(issues, user_hours, user_names, issue_hours, user_issue_hours, 
                    user_estimates, participants, issues_by_type, issue_deviation_reasons):
    """Generate the enhanced report text and return it"""
    
    # Create issue lookup for easier access
    issue_lookup = {issue["key"]: issue for issue in issues}
    
    report_lines = []

    report_lines.append("=" * 100)
    report_lines.append("ACTUALS vs ESTIMATES BY TEAM MEMBER")
    report_lines.append("=" * 100)
    report_lines.append(f"{'Team Member':<30} {'Availability':<15} {'Est Hours':<15} {'Act Hours':<15} {'Variance':<15} {'Tickets':<10}")
    report_lines.append("-" * 100)
    
    # Count tickets per user
    user_ticket_counts = {user_id: len(tickets) for user_id, tickets in user_issue_hours.items()}
    
    # Sort users by hours logged (descending)
    total_estimated_all_users = 0
    total_actual_all_users = 0
    total_availability = 0
    
    for user_id, hours in sorted(user_hours.items(), key=lambda x: x[1], reverse=True):
        user_name = user_names.get(user_id, user_id)
        ticket_count = user_ticket_counts.get(user_id, 0)
        estimated = user_estimates.get(user_id, 0)
        variance = hours - estimated
        variance_str = f"{variance:+.1f}h" if estimated > 0 else "N/A"
        
        # Find availability for this user
        availability = 0
        for participant_name, avail in participants.items():
            if participant_name.lower() == user_name.lower():
                availability = avail
                break
            if availability == 0:
                availability = 80 # Default 80 hours
        
        # Add "-0" suffix to names of people with zero hours
        display_name = f"{user_name}-0" if hours == 0 else user_name
        
        total_estimated_all_users += estimated
        total_actual_all_users += hours
        total_availability += availability
        
        report_lines.append(f"{display_name:<30} {format_time(availability):<15} {format_time(estimated):<15} "
                           f"{format_time(hours):<15} {variance_str:<15} {ticket_count:<10}")
    
    report_lines.append("-" * 100)
    total_variance = total_actual_all_users - total_estimated_all_users
    total_variance_str = f"{total_variance:+.1f}h" if total_estimated_all_users > 0 else "N/A"
    report_lines.append(f"{'TOTAL':<30} {format_time(total_availability):<15} {format_time(total_estimated_all_users):<15} "
                       f"{format_time(total_actual_all_users):<15} {total_variance_str:<15} {len(issue_hours):<10}")
    
    report_lines.append(f"\nTeam Members: {len(user_hours)}")
    report_lines.append(f"Total Team Availability: {format_time(total_availability)}")
    report_lines.append(f"Average Estimated Hours per Person: {format_time(total_estimated_all_users / len(user_hours)) if user_hours else '0h'}")
    report_lines.append(f"Average Actual Hours per Person: {format_time(total_actual_all_users / len(user_hours)) if user_hours else '0h'}")
    
    if total_estimated_all_users > 0:
        accuracy = (1 - abs(total_actual_all_users - total_estimated_all_users) / total_estimated_all_users) * 100
        report_lines.append(f"Overall Estimation Accuracy: {accuracy:.1f}%")
    
    report_lines.append("\n" + "=" * 150)
    report_lines.append("ACTUALS vs ESTIMATES BY TICKET")
    report_lines.append("=" * 150)
    report_lines.append(f"{'Ticket':<12} {'Type':<10} {'Original Est':<14} {'Actual':<14} {'Variance':<12} {'Summary':<50} {'Deviation Reason'}")
    report_lines.append("-" * 150)
    
    total_estimated = 0
    total_actual = 0
    tickets_with_estimates = 0

    # Sort issues by key for consistent output
    for issue_key in sorted(issue_hours.keys()):
        if issue_key in issue_lookup:
            issue = issue_lookup[issue_key]
            fields = issue["fields"]
            
            # Get issue type
            issue_type = fields["issuetype"]["name"]
            
            # Get estimates and actuals
            original_estimate = get_estimate_hours(fields.get("timeoriginalestimate"))
            actual_hours = issue_hours[issue_key]
            
            # Calculate variance
            if original_estimate > 0:
                variance = actual_hours - original_estimate
                variance_str = f"{variance:+.1f}h"
                total_estimated += original_estimate
                tickets_with_estimates += 1
            else:
                variance_str = "N/A"
            
            total_actual += actual_hours
            
            # Get the full summary without truncation
            summary = fields["summary"]
            
            # Get deviation reason if available - only show if variance is positive
            deviation_reason = ""
            if original_estimate > 0 and actual_hours > original_estimate:
                deviation_reason = issue_deviation_reasons.get(issue_key, "")
            
            report_lines.append(f"{issue_key:<12} {issue_type:<10} {format_time(original_estimate):<14} "
                              f"{format_time(actual_hours):<14} {variance_str:<12} {summary:<50} {deviation_reason}")
    
    report_lines.append("-" * 150)
    report_lines.append(f"{'TOTALS':<12} {'':<10} {format_time(total_estimated):<12} "
                       f"{format_time(total_actual):<12} {format_time(total_actual - total_estimated):+<12}")
    
    if tickets_with_estimates > 0:
        accuracy = (1 - abs(total_actual - total_estimated) / total_estimated) * 100
        report_lines.append(f"\nEstimation Accuracy: {accuracy:.1f}%")
        report_lines.append(f"Tickets with Estimates: {tickets_with_estimates}/{len(issue_hours)}")
    
    # SECTION: Breakdown of actuals for each team member across stories
    report_lines.append("\n" + "=" * 150)
    report_lines.append("BREAKDOWN OF ACTUALS BY TEAM MEMBER ACROSS STORIES")
    report_lines.append("=" * 150)
    
    for user_id, hours in sorted(user_hours.items(), key=lambda x: x[1], reverse=True):
        user_name = user_names.get(user_id, user_id)
        user_total_estimate = user_estimates.get(user_id, 0)
        
        # Find availability for this user
        availability = 0
        for participant_name, avail in participants.items():
            if participant_name.lower() == user_name.lower():
                availability = avail
                break
            if availability == 0:
                availability = 80 # Default to 80 hours
        
        report_lines.append(f"\n{user_name} - Availability: {format_time(availability)} | Estimated: {format_time(user_total_estimate)} | Actual: {format_time(hours)}")
        report_lines.append("-" * 150)
        report_lines.append(f"{'Ticket':<12} {'Type':<10} {'Estimated':<14} {'Actual':<14} {'Summary'}")
        report_lines.append("-" * 150)
        
        # Sort this user's tickets by hours (descending)
        user_tickets = sorted(user_issue_hours[user_id].items(), key=lambda x: x[1], reverse=True)
        
        for issue_key, issue_hours_for_user in user_tickets:
            if issue_key in issue_lookup:
                issue = issue_lookup[issue_key]
                summary = issue["fields"]["summary"]
                issue_type = issue["fields"]["issuetype"]["name"]
                original_estimate = get_estimate_hours(issue["fields"].get("timeoriginalestimate"))
                
                # Display full summary without truncation
                report_lines.append(f"{issue_key:<12} {issue_type:<10} {format_time(original_estimate):<14} {format_time(issue_hours_for_user):<14} {summary}")
    
    # SECTION: For each ticket, breakdown of actuals per member
    report_lines.append("\n" + "=" * 150)
    report_lines.append("BREAKDOWN OF ACTUALS BY TICKET ACROSS TEAM MEMBERS")
    report_lines.append("=" * 150)
    
    # Create reverse mapping: issue -> users who worked on it
    issue_user_hours = defaultdict(dict)
    for user_id, tickets in user_issue_hours.items():
        for issue_key, hours in tickets.items():
            issue_user_hours[issue_key][user_id] = hours
    
    # Sort issues by total hours (descending)
    for issue_key in sorted(issue_hours.keys(), key=lambda x: issue_hours[x], reverse=True):
        if issue_key in issue_lookup:
            issue = issue_lookup[issue_key]
            summary = issue["fields"]["summary"]
            issue_type = issue["fields"]["issuetype"]["name"]
            total_hours = issue_hours[issue_key]
            original_estimate = get_estimate_hours(issue["fields"].get("timeoriginalestimate"))
            
            # Get deviation reason if available - only show if variance is positive
            deviation_reason = ""
            if original_estimate > 0 and total_hours > original_estimate:
                deviation_reason = issue_deviation_reasons.get(issue_key, "")
            
            report_lines.append(f"\n{issue_key} - Type: {issue_type} | Estimated: {format_time(original_estimate)} | Actual: {format_time(total_hours)}")
            report_lines.append(f"Summary: {summary}")
            if deviation_reason:
                report_lines.append(f"Deviation Reason: {deviation_reason}")
            report_lines.append("-" * 100)
            report_lines.append(f"{'Team Member':<30} {'Hours':<12} {'Percentage':<12}")
            report_lines.append("-" * 100)
            
            # Sort users by their hours on this ticket (descending)
            ticket_users = sorted(issue_user_hours[issue_key].items(), key=lambda x: x[1], reverse=True)
            
            for user_id, user_hours_on_ticket in ticket_users:
                user_name = user_names.get(user_id, user_id)
                percentage = (user_hours_on_ticket / total_hours) * 100
                report_lines.append(f"{user_name:<30} {format_time(user_hours_on_ticket):<12} {percentage:.1f}%")
    
    return "\n".join(report_lines)



def save_report(report_text, start_date, end_date):
    """Save the report to a file"""
    # Create the reports directory if it doesn't exist
    if not os.path.exists(report_file_path):
        os.makedirs(report_file_path)
    
    # Format the filename with date range
    project_suffix = "_".join(project_keys) if project_keys else "AllProjects"
    filename = f"Jira_Time_Report_{project_suffix}_{start_date.date()}_to_{end_date.date()}.txt"
    
    # Full path to the file
    file_path = os.path.join(report_file_path, filename)
    
    # Write the report to the file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    
    print(f"\n" + "=" * 50)
    print(f"REPORT SAVED TO FILE")
    print("=" * 50)
    print(f"File: {file_path}")
    print(f"Size: {os.path.getsize(file_path)} bytes")


if __name__ == "__main__":
    main()
