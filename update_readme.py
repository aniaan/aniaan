#!/usr/bin/env python3
"""
Script to update README.md with GitHub contribution statistics.
Uses GraphQL API to fetch all merged PRs and display contributions
sorted by PR count and star count.
"""

import os
import sys
import requests
from datetime import datetime, timezone
from collections import defaultdict


GRAPHQL_URL = "https://api.github.com/graphql"


def fetch_merged_prs_graphql(username, token):
    """
    Fetch all merged PRs for a user using GitHub GraphQL API.
    Returns a list of PRs with repository information.

    Note: GitHub Search API limits results to 1000 items maximum.
    """
    if not token:
        print("Error: GITHUB_TOKEN is required for GraphQL API", file=sys.stderr)
        return []

    query = """
    query($searchQuery: String!, $cursor: String) {
      search(query: $searchQuery, type: ISSUE, first: 100, after: $cursor) {
        issueCount
        edges {
          node {
            ... on PullRequest {
              title
              url
              merged
              repository {
                nameWithOwner
                url
                stargazerCount
                primaryLanguage {
                  name
                }
                owner {
                  login
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    search_query = f"is:pr is:merged author:{username}"
    all_prs = []
    cursor = None
    page = 0
    max_pages = 10  # 10 pages * 100 = 1000 max results

    try:
        while page < max_pages:
            variables = {
                "searchQuery": search_query,
                "cursor": cursor,
            }

            response = requests.post(
                GRAPHQL_URL,
                headers=headers,
                json={"query": query, "variables": variables},
            )
            response.raise_for_status()

            data = response.json()

            if "errors" in data:
                print(f"GraphQL errors: {data['errors']}", file=sys.stderr)
                break

            search_result = data.get("data", {}).get("search", {})
            edges = search_result.get("edges", [])

            for edge in edges:
                node = edge.get("node", {})
                if node and node.get("merged"):
                    all_prs.append(node)

            page_info = search_result.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break

            cursor = page_info.get("endCursor")
            page += 1

        print(f"Fetched {len(all_prs)} merged PRs (total found: {search_result.get('issueCount', 0)})")

    except requests.RequestException as e:
        print(f"Error fetching PRs: {e}", file=sys.stderr)
        return []

    return all_prs


def aggregate_contributions(prs, username):
    """
    Aggregate PRs by repository and filter out user's own repos.
    Returns a list of contributions sorted by PR count, then star count.
    """
    repo_stats = defaultdict(lambda: {
        "pr_count": 0,
        "stars": 0,
        "language": "Unknown",
        "url": "",
        "pr_urls": [],
    })

    for pr in prs:
        repo = pr.get("repository", {})
        if not repo:
            continue

        owner = repo.get("owner", {}).get("login", "")
        repo_name = repo.get("nameWithOwner", "")

        # Skip user's own repositories (including forks)
        if owner.lower() == username.lower():
            continue

        stats = repo_stats[repo_name]
        stats["pr_count"] += 1
        stats["stars"] = repo.get("stargazerCount", 0)
        stats["url"] = repo.get("url", "")
        stats["pr_urls"].append(pr.get("url", ""))

        language = repo.get("primaryLanguage")
        if language:
            stats["language"] = language.get("name", "Unknown")

    # Convert to list and sort
    contributions = []
    for repo_name, stats in repo_stats.items():
        contributions.append({
            "name": repo_name,
            "url": stats["url"],
            "stars": stats["stars"],
            "language": stats["language"],
            "pr_count": stats["pr_count"],
            "pr_search_url": f"https://github.com/{repo_name}/pulls?q=is%3Apr+is%3Amerged+author%3A{username}",
        })

    # Sort by PR count (desc), then by stars (desc)
    contributions.sort(key=lambda x: (-x["pr_count"], -x["stars"]))

    return contributions


def format_stars(stars):
    """Format star count with k suffix for thousands."""
    if stars >= 1000:
        if stars < 10000:
            formatted = f"{stars / 1000:.1f}".rstrip('0').rstrip('.')
            return f"{formatted}k"
        return f"{stars // 1000}k"
    return str(stars)


def generate_contributions_table(contributions, username):
    """
    Generate a markdown table with contribution statistics.
    """
    if not contributions:
        return "No contributions found yet. Keep coding!"

    table = "| Project | Language | Stars | PRs |\n"
    table += "|---------|----------|-------|-----|\n"

    for contrib in contributions:
        project_link = f"[{contrib['name']}]({contrib['url']})"
        language = contrib['language']
        stars = format_stars(contrib['stars'])
        pr_link = f"[{contrib['pr_count']}]({contrib['pr_search_url']})"
        table += f"| {project_link} | {language} | {stars} | {pr_link} |\n"

    return table


def update_readme(contributions, username):
    """
    Update README.md with contribution statistics and stats cards.
    """
    readme_path = 'README.md'

    # Generate the contributions section
    contributions_section = f"""## Open Source Contributions

{generate_contributions_table(contributions, username)}

<sub>Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC</sub>
"""

    # Read current README
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = f"## Hi there\n\n"

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

    print(f"README updated with {len(contributions)} contributed repositories")


def main():
    """Main function."""
    username = os.environ.get('GITHUB_REPOSITORY_OWNER', 'aniaan')
    token = os.environ.get('GITHUB_TOKEN')

    if not token:
        print("Warning: GITHUB_TOKEN not set, GraphQL API requires authentication", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching merged PRs for user: {username}")
    prs = fetch_merged_prs_graphql(username, token)

    print(f"Aggregating contributions...")
    contributions = aggregate_contributions(prs, username)
    print(f"Found {len(contributions)} repositories with merged PRs")

    update_readme(contributions, username)
    print("Done!")


if __name__ == '__main__':
    main()
