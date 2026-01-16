#!/usr/bin/env python3
"""
Job Monitor - Daily Job Scraper
================================
Scrapes target company job boards for relevant positions.

Usage:
    python scraper.py              # Run scraper, output to console + file
    python scraper.py --email      # Run scraper and send email
    python scraper.py --open       # Run and open results in browser

Author: Eastman's Job Monitor
Last Updated: January 16, 2026
"""

import os
import sys
import json
import re
import hashlib
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import urllib.request
import urllib.parse
import ssl

# For local runs, try to import yaml; for GitHub Actions, use simple parser
try:
    import yaml
except ImportError:
    yaml = None


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Job:
    """Represents a job posting."""
    id: str
    title: str
    company: str
    location: str
    url: str
    description_snippet: str
    posted_date: str
    salary: str
    relevance_score: int
    matched_keywords: List[str]
    source: str
    first_seen: str
    
    def to_dict(self):
        return asdict(self)
    
    def __hash__(self):
        return hash(self.id)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def load_config(config_path: str = "config.yaml") -> Dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        if yaml:
            return yaml.safe_load(f)
        else:
            # Simple YAML parser fallback for GitHub Actions
            return simple_yaml_parse(f.read())


def simple_yaml_parse(content: str) -> Dict:
    """Simple YAML parser for basic config (fallback)."""
    # This is a simplified parser - for complex configs, install pyyaml
    config = {
        'notification': {'email': 'chennanli@gmail.com'},
        'companies': [],
        'title_patterns': {'high_priority': [], 'medium_priority': []},
        'required_keywords': [],
        'exclude_keywords': [],
        'locations': {'preferred': [], 'exclude': []},
    }
    
    # Extract email
    email_match = re.search(r'email:\s*(\S+@\S+)', content)
    if email_match:
        config['notification']['email'] = email_match.group(1)
    
    # Extract company names and greenhouse IDs
    company_blocks = re.findall(r'- name:\s*(\S+.*?)\n\s+.*?greenhouse_id:\s*(\S+)?', content, re.DOTALL)
    for name, gh_id in company_blocks:
        config['companies'].append({
            'name': name.strip(),
            'greenhouse_id': gh_id.strip() if gh_id and gh_id != 'null' else None
        })
    
    # Extract keywords
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('- ') and not line.startswith('- name:'):
            keyword = line[2:].strip().strip('"').strip("'")
            if keyword and len(keyword) > 2:
                config['required_keywords'].append(keyword.lower())
    
    return config


def load_seen_jobs(seen_path: str = "seen_jobs.json") -> Dict[str, Dict]:
    """Load previously seen jobs."""
    if os.path.exists(seen_path):
        with open(seen_path, 'r') as f:
            return json.load(f)
    return {}


def save_seen_jobs(seen_jobs: Dict[str, Dict], seen_path: str = "seen_jobs.json"):
    """Save seen jobs to file."""
    with open(seen_path, 'w') as f:
        json.dump(seen_jobs, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_url(url: str, timeout: int = 30) -> Optional[str]:
    """Fetch URL content with error handling."""
    try:
        # Create SSL context that doesn't verify (for some job sites)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/json, text/html, */*',
            }
        )
        
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  ⚠️  Error fetching {url}: {e}")
        return None


def fetch_json(url: str) -> Optional[Dict]:
    """Fetch and parse JSON from URL."""
    content = fetch_url(url)
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# GREENHOUSE SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_greenhouse(company_name: str, board_token: str, config: Dict) -> List[Job]:
    """Scrape jobs from Greenhouse job board API."""
    jobs = []
    
    if not board_token:
        return jobs
    
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
    print(f"  📡 Fetching Greenhouse: {board_token}")
    
    data = fetch_json(url)
    if not data or 'jobs' not in data:
        print(f"  ⚠️  No jobs found for {company_name}")
        return jobs
    
    for job_data in data.get('jobs', []):
        title = job_data.get('title', '')
        location = job_data.get('location', {}).get('name', 'Unknown')
        job_url = job_data.get('absolute_url', '')
        job_id = str(job_data.get('id', ''))
        updated_at = job_data.get('updated_at', '')[:10] if job_data.get('updated_at') else ''
        
        # Check if job matches criteria
        relevance, matched = calculate_relevance(title, '', location, config)
        
        if relevance > 0:
            jobs.append(Job(
                id=f"gh_{board_token}_{job_id}",
                title=title,
                company=company_name,
                location=location,
                url=job_url,
                description_snippet="",  # Would need additional API call
                posted_date=updated_at,
                salary="",
                relevance_score=relevance,
                matched_keywords=matched,
                source="greenhouse",
                first_seen=datetime.now().isoformat()[:10]
            ))
    
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
# LEVER SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_lever(company_name: str, lever_id: str, config: Dict) -> List[Job]:
    """Scrape jobs from Lever job board."""
    jobs = []
    
    if not lever_id:
        return jobs
    
    url = f"https://api.lever.co/v0/postings/{lever_id}"
    print(f"  📡 Fetching Lever: {lever_id}")
    
    data = fetch_json(url)
    if not data:
        return jobs
    
    for job_data in data:
        title = job_data.get('text', '')
        location = job_data.get('categories', {}).get('location', 'Unknown')
        job_url = job_data.get('hostedUrl', '')
        job_id = job_data.get('id', '')
        
        # Check if job matches criteria
        relevance, matched = calculate_relevance(title, '', location, config)
        
        if relevance > 0:
            jobs.append(Job(
                id=f"lever_{lever_id}_{job_id}",
                title=title,
                company=company_name,
                location=location,
                url=job_url,
                description_snippet=job_data.get('descriptionPlain', '')[:200],
                posted_date="",
                salary="",
                relevance_score=relevance,
                matched_keywords=matched,
                source="lever",
                first_seen=datetime.now().isoformat()[:10]
            ))
    
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
# GENERIC CAREERS PAGE SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_careers_page(company_name: str, careers_url: str, config: Dict) -> List[Job]:
    """
    Generic scraper for careers pages.
    Looks for common patterns in job listings.
    """
    jobs = []
    
    if not careers_url:
        return jobs
    
    print(f"  📡 Fetching careers page: {careers_url}")
    html = fetch_url(careers_url)
    
    if not html:
        return jobs
    
    # Look for job links - common patterns
    # Pattern 1: Links with "job" or "position" in URL
    job_links = re.findall(
        r'href=["\']([^"\']*(?:job|position|career|opening)[^"\']*)["\']',
        html, re.IGNORECASE
    )
    
    # Pattern 2: Links in job listing containers
    job_titles = re.findall(
        r'<(?:h[1-4]|a|div)[^>]*class=["\'][^"\']*(?:job|position|title)[^"\']*["\'][^>]*>([^<]+)<',
        html, re.IGNORECASE
    )
    
    # Deduplicate and create basic job entries
    seen_titles = set()
    for title in job_titles[:20]:  # Limit to first 20
        title = title.strip()
        if title and title not in seen_titles and len(title) > 5:
            seen_titles.add(title)
            
            relevance, matched = calculate_relevance(title, '', '', config)
            if relevance > 0:
                job_id = hashlib.md5(f"{company_name}_{title}".encode()).hexdigest()[:12]
                jobs.append(Job(
                    id=f"web_{job_id}",
                    title=title,
                    company=company_name,
                    location="See posting",
                    url=careers_url,
                    description_snippet="",
                    posted_date="",
                    salary="",
                    relevance_score=relevance,
                    matched_keywords=matched,
                    source="careers_page",
                    first_seen=datetime.now().isoformat()[:10]
                ))
    
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
# RELEVANCE SCORING
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_relevance(title: str, description: str, location: str, config: Dict) -> Tuple[int, List[str]]:
    """
    Calculate relevance score for a job.
    Returns (score, list of matched keywords).
    
    Score breakdown:
    - Title pattern match (high priority): +50
    - Title pattern match (medium priority): +30
    - Each required keyword found: +10
    - Preferred location: +10
    - Excluded keyword found: -100 (disqualify)
    - Excluded location: -100 (disqualify)
    """
    score = 0
    matched = []
    
    title_lower = title.lower()
    desc_lower = description.lower()
    location_lower = location.lower()
    combined = f"{title_lower} {desc_lower} {location_lower}"
    
    # Check exclusions first
    exclude_keywords = config.get('exclude_keywords', [])
    for kw in exclude_keywords:
        if kw.lower() in title_lower:
            return 0, []  # Disqualified
    
    exclude_locations = config.get('locations', {}).get('exclude', [])
    for loc in exclude_locations:
        if loc.lower() in location_lower and 'remote' not in location_lower:
            return 0, []  # Disqualified
    
    # Check title patterns
    high_priority = config.get('title_patterns', {}).get('high_priority', [])
    for pattern in high_priority:
        if re.search(pattern, title_lower, re.IGNORECASE):
            score += 50
            matched.append(f"title:{pattern}")
            break
    
    medium_priority = config.get('title_patterns', {}).get('medium_priority', [])
    for pattern in medium_priority:
        if re.search(pattern, title_lower, re.IGNORECASE):
            score += 30
            matched.append(f"title:{pattern}")
            break
    
    # Check required keywords
    required_keywords = config.get('required_keywords', [])
    keyword_found = False
    for kw in required_keywords:
        if kw.lower() in combined:
            score += 10
            matched.append(kw)
            keyword_found = True
    
    # Must have at least one keyword match OR high-priority title match
    if not keyword_found and score < 50:
        return 0, []
    
    # Bonus for preferred location
    preferred_locations = config.get('locations', {}).get('preferred', [])
    for loc in preferred_locations:
        if loc.lower() in location_lower:
            score += 10
            matched.append(f"location:{loc}")
            break
    
    return score, matched


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_all_companies(config: Dict) -> List[Job]:
    """Scrape all configured companies."""
    all_jobs = []
    
    for company in config.get('companies', []):
        name = company.get('name', 'Unknown')
        print(f"\n🔍 Scraping {name}...")
        
        # Try Greenhouse first
        gh_id = company.get('greenhouse_id')
        if gh_id:
            jobs = scrape_greenhouse(name, gh_id, config)
            all_jobs.extend(jobs)
            print(f"  ✅ Found {len(jobs)} matching jobs via Greenhouse")
        
        # Try Lever
        lever_id = company.get('lever_id')
        if lever_id:
            jobs = scrape_lever(name, lever_id, config)
            all_jobs.extend(jobs)
            print(f"  ✅ Found {len(jobs)} matching jobs via Lever")
        
        # Try careers page (if no API)
        if not gh_id and not lever_id:
            careers_url = company.get('careers_url')
            if careers_url:
                jobs = scrape_careers_page(name, careers_url, config)
                all_jobs.extend(jobs)
                print(f"  ✅ Found {len(jobs)} potential matches via careers page")
    
    return all_jobs


def filter_new_jobs(all_jobs: List[Job], seen_jobs: Dict[str, Dict]) -> List[Job]:
    """Filter out jobs we've already seen."""
    new_jobs = []
    for job in all_jobs:
        if job.id not in seen_jobs:
            new_jobs.append(job)
    return new_jobs


def update_seen_jobs(seen_jobs: Dict[str, Dict], new_jobs: List[Job]) -> Dict[str, Dict]:
    """Add new jobs to seen jobs tracker."""
    for job in new_jobs:
        seen_jobs[job.id] = {
            'title': job.title,
            'company': job.company,
            'first_seen': job.first_seen,
            'url': job.url
        }
    return seen_jobs


# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUT FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════════

def format_markdown(jobs: List[Job], is_new: bool = True) -> str:
    """Format jobs as Markdown."""
    status = "NEW" if is_new else "All Matching"
    
    lines = [
        f"# Job Monitor Results - {status}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Total Jobs:** {len(jobs)}",
        "",
    ]
    
    if not jobs:
        lines.append("No new matching jobs found today. 🎯")
        lines.append("")
        lines.append("Keep checking - the right role will appear!")
        return "\n".join(lines)
    
    # Group by company
    by_company = {}
    for job in jobs:
        if job.company not in by_company:
            by_company[job.company] = []
        by_company[job.company].append(job)
    
    # Sort companies by number of jobs
    for company in sorted(by_company.keys(), key=lambda c: -len(by_company[c])):
        company_jobs = by_company[company]
        lines.append(f"## {company} ({len(company_jobs)} jobs)")
        lines.append("")
        
        # Sort by relevance
        for job in sorted(company_jobs, key=lambda j: -j.relevance_score):
            lines.append(f"### [{job.title}]({job.url})")
            lines.append(f"- **Location:** {job.location}")
            lines.append(f"- **Relevance:** {job.relevance_score} ({', '.join(job.matched_keywords[:3])})")
            if job.salary:
                lines.append(f"- **Salary:** {job.salary}")
            if job.posted_date:
                lines.append(f"- **Posted:** {job.posted_date}")
            lines.append("")
    
    # Summary
    lines.append("---")
    lines.append("## Quick Apply Links")
    lines.append("")
    for job in sorted(jobs, key=lambda j: -j.relevance_score)[:10]:
        lines.append(f"- [{job.company}: {job.title}]({job.url})")
    
    return "\n".join(lines)


def format_email_html(jobs: List[Job]) -> str:
    """Format jobs as HTML email."""
    if not jobs:
        return """
        <html>
        <body style="font-family: Arial, sans-serif;">
        <h2>Job Monitor - No New Jobs Today</h2>
        <p>No new matching jobs found. Keep checking!</p>
        </body>
        </html>
        """
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #2563eb;">🎯 Job Monitor - {len(jobs)} New Jobs Found!</h2>
    <p style="color: #666;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    <hr>
    """
    
    for job in sorted(jobs, key=lambda j: -j.relevance_score)[:15]:
        html += f"""
        <div style="margin: 15px 0; padding: 10px; border-left: 3px solid #2563eb;">
            <h3 style="margin: 0;"><a href="{job.url}" style="color: #2563eb;">{job.title}</a></h3>
            <p style="margin: 5px 0; color: #333;"><strong>{job.company}</strong> - {job.location}</p>
            <p style="margin: 5px 0; color: #666; font-size: 12px;">
                Score: {job.relevance_score} | Keywords: {', '.join(job.matched_keywords[:3])}
            </p>
        </div>
        """
    
    html += """
    <hr>
    <p style="color: #666; font-size: 12px;">
        This email was generated by your Job Monitor.<br>
        <a href="https://github.com/chennanli/job-monitor">View on GitHub</a>
    </p>
    </body>
    </html>
    """
    
    return html


def print_console(jobs: List[Job], is_new: bool = True):
    """Print jobs to console with colors."""
    status = "NEW" if is_new else "All Matching"
    
    print("\n" + "=" * 70)
    print(f"  JOB MONITOR RESULTS - {status}")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Total Jobs: {len(jobs)}")
    print("=" * 70)
    
    if not jobs:
        print("\n  No new matching jobs found today. 🎯")
        print("  Keep checking - the right role will appear!\n")
        return
    
    for job in sorted(jobs, key=lambda j: -j.relevance_score)[:20]:
        print(f"\n  📌 {job.title}")
        print(f"     Company:  {job.company}")
        print(f"     Location: {job.location}")
        print(f"     Score:    {job.relevance_score} ({', '.join(job.matched_keywords[:3])})")
        print(f"     URL:      {job.url}")
    
    print("\n" + "=" * 70 + "\n")


# ═══════════════════════════════════════════════════════════════════════════════
# EMAIL SENDER (for GitHub Actions)
# ═══════════════════════════════════════════════════════════════════════════════

def send_email_via_github(to_email: str, subject: str, html_body: str):
    """
    Send email using GitHub Actions workflow.
    This creates a file that the workflow will use to send email.
    """
    email_data = {
        'to': to_email,
        'subject': subject,
        'body': html_body,
        'timestamp': datetime.now().isoformat()
    }
    
    with open('output/email_to_send.json', 'w') as f:
        json.dump(email_data, f, indent=2)
    
    print(f"  📧 Email prepared for: {to_email}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Job Monitor - Daily Job Scraper')
    parser.add_argument('--email', action='store_true', help='Send email notification')
    parser.add_argument('--open', action='store_true', help='Open results in browser')
    parser.add_argument('--all', action='store_true', help='Show all matching jobs, not just new')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    args = parser.parse_args()
    
    print("\n🚀 Job Monitor Starting...")
    print(f"   Config: {args.config}")
    
    # Load config
    try:
        config = load_config(args.config)
        print(f"   Companies: {len(config.get('companies', []))}")
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        sys.exit(1)
    
    # Load seen jobs
    seen_jobs = load_seen_jobs()
    print(f"   Previously seen: {len(seen_jobs)} jobs")
    
    # Scrape all companies
    all_jobs = scrape_all_companies(config)
    print(f"\n📊 Found {len(all_jobs)} total matching jobs")
    
    # Filter new jobs
    if args.all:
        display_jobs = all_jobs
        is_new = False
    else:
        display_jobs = filter_new_jobs(all_jobs, seen_jobs)
        is_new = True
    
    print(f"   New jobs: {len(display_jobs)}")
    
    # Update seen jobs
    seen_jobs = update_seen_jobs(seen_jobs, display_jobs)
    save_seen_jobs(seen_jobs)
    
    # Output results
    print_console(display_jobs, is_new)
    
    # Save markdown
    os.makedirs('output', exist_ok=True)
    markdown = format_markdown(display_jobs, is_new)
    with open('output/new_jobs.md', 'w') as f:
        f.write(markdown)
    print(f"📄 Results saved to: output/new_jobs.md")
    
    # Send email if requested
    if args.email and display_jobs:
        email = config.get('notification', {}).get('email', 'chennanli@gmail.com')
        subject = f"Job Monitor: {len(display_jobs)} New Jobs Found - {datetime.now().strftime('%Y-%m-%d')}"
        html = format_email_html(display_jobs)
        send_email_via_github(email, subject, html)
    elif args.email and not display_jobs:
        # Check if we should send empty notification
        if config.get('notification', {}).get('send_empty', False):
            email = config.get('notification', {}).get('email', 'chennanli@gmail.com')
            send_email_via_github(email, "Job Monitor: No New Jobs Today", format_email_html([]))
    
    # Open in browser if requested
    if args.open:
        import webbrowser
        output_path = os.path.abspath('output/new_jobs.md')
        webbrowser.open(f'file://{output_path}')
    
    print("\n✅ Job Monitor Complete!")
    return 0 if display_jobs else 1


if __name__ == "__main__":
    sys.exit(main())
