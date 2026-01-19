#!/usr/bin/env python3
"""
Script to update README.md with GitHub contribution statistics.
Fetches user's contributions and updates the README with:
- List of contributed projects
- Commit counts per project (clickable to view commits)
- Primary language per project
"""

import os
import sys
import requests
from datetime import datetime, timezone
from collections import defaultdict


def fetch_user_contributions(username, token=None):
    """
    Fetch all repositories where the user has made contributions.
    Returns a list of repositories with contribution counts and languages.
    
    Note: Uses the GitHub Events API which provides recent user activity.
    Counts are based on push events (commits) and PR events from the last ~90 events.
    This provides a good approximation of recent contributions, though not a complete
    historical count.
    """
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    contributions = []
    repo_stats = defaultdict(int)
    
    # Fetch user events to find contributed repositories
    events_url = f'https://api.github.com/users/{username}/events/public'
    
    try:
        # Fetch multiple pages of events
        for page in range(1, 4):  # Get up to 3 pages (90 events)
            response = requests.get(f'{events_url}?page={page}&per_page=30', headers=headers)
            response.raise_for_status()
            events = response.json()
            
            if not events:
                break
            
            # Count commits per repository from events
            for event in events:
                # All events are already for this user, so we know they're the actor
                repo_name = event['repo']['name']
                # Skip the user's own profile repository
                if repo_name == f'{username}/{username}':
                    continue
                
                if event['type'] == 'PushEvent':
                    # Count commits in push events
                    commits = event.get('payload', {}).get('commits', [])
                    if commits:
                        repo_stats[repo_name] += len(commits)
                
                elif event['type'] == 'PullRequestEvent':
                    # Only count PR opened events to avoid double-counting
                    # Note: This counts PRs, not commits, but shows activity level
                    if event.get('payload', {}).get('action') == 'opened':
                        repo_stats[repo_name] += 1
        
        # Get repository details for each contributed repo
        for repo_name, commit_count in repo_stats.items():
            try:
                repo_url = f'https://api.github.com/repos/{repo_name}'
                repo_response = requests.get(repo_url, headers=headers)
                repo_response.raise_for_status()
                repo_data = repo_response.json()
                
                contributions.append({
                    'name': repo_name,
                    'url': repo_data['html_url'],
                    'language': repo_data.get('language') or 'Unknown',
                    'commit_count': commit_count,
                    'commits_url': f"https://github.com/{repo_name}/commits?author={username}"
                })
            except Exception as e:
                print(f"Warning: Could not fetch details for {repo_name}: {e}", file=sys.stderr)
                continue
        
        # Sort by commit count (descending)
        contributions.sort(key=lambda x: x['commit_count'], reverse=True)
        
    except Exception as e:
        print(f"Error fetching contributions: {e}", file=sys.stderr)
        return []
    
    return contributions


def generate_contributions_table(contributions):
    """
    Generate a markdown table with contribution statistics.
    Note: Counts are based on recent events and may include both commits and PRs.
    """
    if not contributions:
        return "No contributions found yet. Keep coding! 🚀"
    
    table = "| Contributions | Project | Language |\n"
    table += "|---------------|---------|----------|\n"
    
    for contrib in contributions:
        contributions_link = f"[{contrib['commit_count']}]({contrib['commits_url']})"
        project_link = f"[{contrib['name']}]({contrib['url']})"
        language = contrib['language']
        table += f"| {contributions_link} | {project_link} | {language} |\n"
    
    return table


def update_readme(contributions):
    """
    Update README.md with contribution statistics.
    """
    readme_path = 'README.md'
    
    # Generate the contributions section
    contributions_section = f"""## 📊 My Open Source Contributions

{generate_contributions_table(contributions)}

<sub>Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC</sub>
"""
    
    # Read current README
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = "# Hi there 👋\n\n"
    
    # Check if the contributions section exists
    start_marker = "<!-- CONTRIBUTION_STATS:START -->"
    end_marker = "<!-- CONTRIBUTION_STATS:END -->"
    
    if start_marker in content and end_marker in content:
        # Replace existing section
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker) + len(end_marker)
        new_content = (
            content[:start_idx] +
            f"{start_marker}\n{contributions_section}\n{end_marker}" +
            content[end_idx:]
        )
    else:
        # Add new section at the end
        new_content = content.rstrip() + f"\n\n{start_marker}\n{contributions_section}\n{end_marker}\n"
    
    # Write updated README
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ README updated with {len(contributions)} contributions")


def main():
    """Main function."""
    username = os.environ.get('GITHUB_REPOSITORY_OWNER', 'aniaan')
    token = os.environ.get('GITHUB_TOKEN')
    
    print(f"Fetching contributions for user: {username}")
    contributions = fetch_user_contributions(username, token)
    print(f"Found {len(contributions)} repositories with contributions")
    
    update_readme(contributions)
    print("✅ Done!")


if __name__ == '__main__':
    main()
