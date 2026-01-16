# Job Monitor 🎯

Automated daily job scraper targeting hot tech companies with energy/industrial verticals.

## Quick Start

### Local Run (On-Demand)

```bash
# Clone the repo
git clone https://github.com/chennanli/job-monitor.git
cd job-monitor

# Install dependencies
pip install -r requirements.txt

# Run the scraper
./run_local.sh

# Or with Python directly
python scraper.py
python scraper.py --open    # Open results in browser
python scraper.py --all     # Show all matching jobs, not just new
```

### GitHub Actions (Automatic Daily)

The scraper runs automatically every day at **8:00 AM Pacific**.

Results are:
- Committed to `output/new_jobs.md`
- Created as GitHub Issues (for email notification)
- Available in Actions artifacts

## Target Companies

| Company | Source | Focus |
|---------|--------|-------|
| Databricks | Greenhouse | Energy, Utilities, Industrial |
| Snowflake | Greenhouse | Energy, Industrial |
| Palantir | Greenhouse | Energy, Infrastructure |
| Scale AI | Greenhouse | Industrial |
| Google | Careers | Data Center, Energy, Sustainability |
| Microsoft | Careers | Azure, Energy, Data Center |
| Amazon AWS | Careers | Energy, Industrial, Data Center |
| Meta | Careers | Data Center, Infrastructure |
| Anthropic | Greenhouse | Infrastructure, Data Center |
| OpenAI | Greenhouse | Infrastructure |
| Crusoe Energy | Greenhouse | All roles (AI + Energy) |
| Anduril | Greenhouse | Simulation, Digital Twin |

## Target Roles

**High Priority:**
- Solutions Architect (Energy/Industrial)
- Technical Program Manager (Infrastructure)
- Director of Data/AI/Analytics
- Principal Architect
- Customer Engineer (Industrial)

**Medium Priority:**
- Product Manager (Industrial IoT)
- Program Manager
- Pre-Sales Engineer
- Field Engineer

## Configuration

Edit `config.yaml` to customize:

```yaml
# Add/remove companies
companies:
  - name: NewCompany
    greenhouse_id: newcompany
    keywords_boost: ["energy", "industrial"]

# Adjust keywords
required_keywords:
  - energy
  - data center
  - industrial
  # Add more...

# Change locations
locations:
  preferred:
    - remote
    - bay area
  exclude:
    - india
```

## How It Works

1. **Scrapes** job boards (Greenhouse API, Lever API, careers pages)
2. **Filters** by title patterns and keywords
3. **Scores** relevance (0-100)
4. **Tracks** seen jobs to only show new ones
5. **Outputs** Markdown results + optional email

### Relevance Scoring

| Factor | Points |
|--------|--------|
| High-priority title match | +50 |
| Medium-priority title match | +30 |
| Each keyword found | +10 |
| Preferred location | +10 |
| Excluded keyword | -100 (skip) |

## Files

```
job-monitor/
├── .github/workflows/
│   └── daily_scan.yml      # GitHub Actions (daily 8am)
├── config.yaml              # Companies, keywords, settings
├── scraper.py               # Main scraper logic
├── run_local.sh             # One-click local run
├── requirements.txt         # Python dependencies
├── seen_jobs.json           # Tracking (auto-updated)
├── output/
│   └── new_jobs.md          # Results
└── README.md                # This file
```

## Email Setup (Optional)

To receive email notifications:

1. Go to repo **Settings** → **Secrets and variables** → **Actions**
2. Add these secrets:
   - `EMAIL_USERNAME`: Your Gmail address
   - `EMAIL_PASSWORD`: Gmail App Password (not regular password)

To create Gmail App Password:
1. Go to Google Account → Security
2. Enable 2-Factor Authentication
3. Go to App Passwords
4. Create new app password for "Mail"

**Alternative:** The workflow also creates GitHub Issues for new jobs, which will email you if you have GitHub notifications enabled.

## Manual Trigger

To run the scraper manually:

1. Go to **Actions** tab in GitHub
2. Select **Daily Job Scan**
3. Click **Run workflow**
4. Optionally check "Show all matching jobs"

## Troubleshooting

**No jobs found?**
- Check if company Greenhouse IDs are correct
- Expand `required_keywords` in config
- Try `python scraper.py --all` to see all matching jobs

**GitHub Actions failing?**
- Check Actions logs for errors
- Ensure `seen_jobs.json` exists
- Verify workflow permissions

**Email not sending?**
- Verify EMAIL_USERNAME and EMAIL_PASSWORD secrets
- Check GitHub Issues as backup notification

## License

MIT - Use freely for your job search!

---

*Built to find the perfect role at the intersection of AI and Energy/Industrial domains.*
