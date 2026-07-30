# HyerEnrichment User Guide

**For recruiters, sales teams, HR professionals, and researchers**

---

## 1. What is HyerEnrichment?

HyerEnrichment helps you discover public information about people and companies — all from a single search.

**In plain English:** Think of it as your research assistant that finds publicly available professional information across the internet. Give it a LinkedIn URL, email address, username, or company name, and it returns a unified report (we call it a "dossier") with everything it can find.

### What Data Can You Discover?

- **LinkedIn profile photos** — captured and cached for your records
- **Social media handles** — Twitter/X, GitHub, Instagram, Reddit, TikTok, and hundreds more
- **Email addresses** — both discovered and verified for deliverability
- **Professional information** — GitHub activity, coworkers at the same company
- **Job listings** — open positions across 5+ major job boards
- **Business intelligence** — Google Maps listings, ratings, contact info

### Privacy-First Design

- **Opt-out honored**: Anyone can request suppression via our `/opt-out` page
- **No bulk scraping**: We only enrich identifiers you explicitly provide
- **Customer-supplied only**: We don't build databases — you bring the identifiers
- **GDPR & CCPA compliant**: Full data subject access and deletion procedures
- **Public data only**: We surface information that's already publicly available

---

## 2. Your First Enrichment

Follow this step-by-step tutorial to run your first enrichment.

### Step 1: Open the Console

Navigate to `/app/enrich` in your browser. You'll see the enrichment console with an intake form.

<!-- Screenshot: Console landing page with intake form -->

### Step 2: Choose Your Mode

You have two options:

**Full Async Mode** (recommended for most cases)
- Enrichment runs in the background
- Watch live progress updates
- Best for deep research that takes 1-3 minutes
- You can navigate away and come back later

**Quick Sync Mode**
- Gets results immediately (under 30 seconds)
- Good for single-tier quick lookups
- No job tracking overhead

<!-- Screenshot: Mode selector radio buttons -->

### Step 3: Select Enrichment Tiers

Check the boxes next to the tiers you want to run. Each tier finds different types of information:

- ☑ **Tier 1**: LinkedIn Profile Photo
- ☑ **Tier 2**: Social Media Discovery
- ☑ **Tier 3**: Deep OSINT (emails, GitHub, coworkers)
- ☑ **Tier 4**: Jobs & Local Business

**Tip for beginners**: Start with Tier 2 and Tier 3 — they work well together and don't have rate limits.

<!-- Screenshot: Tier checkboxes with descriptions -->

### Step 4: Enter Identifiers

Fill in the fields that match what you know about your target:

| Field | What to Enter | Example |
|-------|---------------|---------|
| **LinkedIn URL** | Full profile URL | `https://linkedin.com/in/johndoe` |
| **Username** | Social media handle (no @) | `johndoe` |
| **Email** | Personal or work email | `john@example.com` |
| **Name** | Full name (optional context) | `John Doe` |
| **Company** | Company name for coworker search | `Acme Corp` |
| **Job Title** | For job search (Tier 4) | `Software Engineer` |
| **Location** | City/region for job search | `San Francisco` |
| **Business Query** | Business name + location | `Coffee Shop Seattle` |

**You don't need all fields** — just provide what you have. The system will find as much as it can from your inputs.

<!-- Screenshot: Filled intake form with sample data -->

### Step 5: Submit and Watch Live Progress

Click **"Enrich"** to start the job.

In async mode, you'll see:
- A live progress bar
- Which tier is currently running
- How many enrichers have completed
- Real-time log messages

<!-- Screenshot: Live progress view with status updates -->

### Step 6: View Your Dossier

When enrichment completes, you'll see your results organized into tabs:

- **Overview**: Quick summary with counts
- **Handles**: All discovered social media profiles
- **Emails**: Found and verified email addresses
- **Professional**: GitHub, coworkers, job listings
- **Raw JSON**: Complete technical output

<!-- Screenshot: Completed dossier with tabbed results -->

**Congratulations!** You've completed your first enrichment.

---

## 3. Understanding Enrichment Tiers

Each tier specializes in different types of data. You can run any combination — they work independently.

### Tier 1: LinkedIn Profile Photo

**What it does**: Captures high-resolution profile photos from LinkedIn using browser automation.

**When to use**:
- **Recruiting**: Visual verification before interviews
- **Due diligence**: Identity confirmation for investments or partnerships
- **Fraud prevention**: Matching photos across platforms
- **Record keeping**: Archiving candidate profiles

**What you need**: LinkedIn profile URL (e.g., `https://linkedin.com/in/username`)

**Important limits**:
- **20-25 profiles per day** per profile pool (LinkedIn's anti-scraping protection)
- Photos are cached in Cloudflare R2 for future retrieval
- Respects LinkedIn's robots.txt and rate limits

**How it works**: We use Multilogin browser profiles with residential proxies to fetch photos ethically, then store them with metadata (dimensions, timestamp, confidence score).

**Sample output**:
```
Photo URL: https://your-r2-bucket.cloudflare.com/photos/abc123.jpg
Dimensions: 800x800px
Captured: 2026-07-30 11:23 UTC
Confidence: HIGH
```

---

### Tier 2: Social Media Discovery

**What it does**: Finds usernames and profile links across hundreds of social platforms.

**When to use**:
- **Background research**: Understanding someone's public presence
- **Contact discovery**: Finding alternative channels (Twitter DMs, GitHub issues)
- **Influencer verification**: Checking follower counts and activity
- **Reputation checks**: Reviewing public posts and contributions

**What you need**: A username (e.g., `johndoe` — no @ symbol needed)

**Platforms searched** (partial list):
- Professional: GitHub, LinkedIn, AngelList, Kaggle
- Social: Twitter/X, Instagram, TikTok, Reddit, Mastodon
- Creative: Dribbble, Behance, DeviantArt, Medium
- Gaming: Twitch, Steam, Xbox, PlayStation
- Hundreds more via Sherlock integration

**Confidence scoring**:
- **HIGH**: Profile exists, username matches, activity detected
- **MEDIUM**: Profile found but limited verification
- **LOW**: Possible match, needs manual review

**Sample output**:
```
GitHub: github.com/johndoe (HIGH)
Twitter: twitter.com/johndoe (MEDIUM)
Reddit: reddit.com/user/johndoe (HIGH)
Instagram: instagram.com/johndoe (LOW - private account)
```

---

### Tier 3: Deep OSINT

**What it does**: Discovers and verifies email addresses, GitHub activity, coworkers, and organizational relationships.

**When to use**:
- **Sales outreach**: Finding verified work emails for cold outreach
- **Competitive intelligence**: Mapping company org charts via GitHub
- **Recruitment**: Discovering GitHub projects and code samples
- **Verification**: SMTP-checking email deliverability before sending

**What you need**: Email, username, or company name

**What you'll get**:

**Email Discovery**:
- Personal emails (from GitHub commits, public profiles)
- Work emails (guessed patterns like `first.last@company.com`)
- **Email verification status**:
  - ✅ **Deliverable**: SMTP server confirms this inbox exists
  - ⚠️ **Catch-all**: Domain accepts all addresses (less reliable)
  - ❌ **Undeliverable**: Bounced or invalid
  - ❓ **Unknown**: Could not verify (server offline or blocking)

**GitHub Intelligence**:
- Public repositories and contributions
- Commit emails (if publicly visible)
- Programming languages used
- Recent activity timeline

**Coworker Discovery**:
- Other employees at the same company (via GitHub org membership)
- Helps map team structures
- Useful for multi-person outreach campaigns

**Sample output**:
```
Emails Found:
 - john.doe@example.com (Deliverable - Work)
 - johndoe@gmail.com (Deliverable - Personal)
 - john@oldstartup.com (Undeliverable - Previous employer)

GitHub:
 - github.com/johndoe
 - 42 repositories, 1,203 contributions
 - Top languages: Python, TypeScript, Go
 - Last commit: 2 days ago

Coworkers at Acme Corp:
 - Jane Smith (github.com/janesmith)
 - Bob Wilson (github.com/bobwilson)
```

---

### Tier 4: Jobs & Local Business

**What it does**: Aggregates job listings across multiple boards and fetches business information from Google Maps.

**When to use**:

**Job Search**:
- **Recruiting**: Finding all open positions at a target company
- **Market research**: Understanding hiring trends in your industry
- **Competitive analysis**: Seeing what roles competitors are hiring for
- **Career planning**: Discovering opportunities across multiple platforms

**Business Intelligence**:
- **Lead generation**: Finding local businesses with contact info
- **Market sizing**: Counting businesses in a category + region
- **Due diligence**: Checking ratings, reviews, and legitimacy
- **Competitive mapping**: Identifying similar businesses nearby

**What you need**:
- **For jobs**: Job title + location (e.g., "Software Engineer" + "Remote" or "San Francisco")
- **For business**: Business name + location (e.g., "Starbucks Seattle")

**Job boards searched**:
1. Indeed
2. LinkedIn Jobs
3. Glassdoor
4. ZipRecruiter
5. Google Jobs (aggregator)

**Sample job output**:
```
Found 17 jobs for "Data Analyst" in "New York":

[Indeed] Senior Data Analyst - Acme Corp
 Location: New York, NY (Hybrid)
 Salary: $90k - $120k
 Posted: 3 days ago
 Link: indeed.com/viewjob?jk=abc123

[LinkedIn] Data Analyst II - Tech Startup
 Location: Remote (US-based)
 Salary: Not disclosed
 Posted: 1 week ago
 Link: linkedin.com/jobs/view/xyz789
```

**Sample business output**:
```
Starbucks Reserve Roastery - Seattle
 Address: 1124 Pike St, Seattle, WA 98101
 Phone: (206) 624-0173
 Rating: 4.5 stars (2,341 reviews)
 Hours: Mon-Sun 7am-9pm
 Website: starbucksreserve.com
 Business Type: Coffee Shop, Roastery
```

---

## 4. Reading Your Dossier

After enrichment completes, your results are organized into tabs for easy navigation.

<!-- Screenshot: Full dossier view with all tabs -->

### Overview Tab

**Your starting point** — shows high-level counts and what was found.

**What you'll see**:
- Total handles discovered
- Number of emails found
- Email verification summary
- Job listing count
- Business results count
- Confidence breakdown (HIGH/MEDIUM/LOW signals)

**Use this tab to**: Quickly assess whether the enrichment was successful before diving into details.

<!-- Screenshot: Overview tab with summary cards -->

---

### Handles Tab

**Social media profiles** organized by platform and confidence level.

**Layout**:
- **Platform logo** + **Username** + **Confidence badge**
- Click any handle to open the profile in a new tab
- Filter by confidence level (HIGH/MEDIUM/LOW)
- Sort alphabetically or by confidence

**Confidence colors**:
- 🟢 **GREEN (HIGH)**: Verified, active profile
- 🟡 **YELLOW (MEDIUM)**: Probable match, limited verification
- 🔴 **RED (LOW)**: Possible match, needs manual review

**Pro tip**: Focus on HIGH confidence handles first. MEDIUM and LOW may require manual confirmation.

<!-- Screenshot: Handles tab with confidence badges -->

---

### Emails Tab

**Discovered and verified email addresses** with deliverability status.

**What you'll see**:

**Email Address** | **Status** | **Type** | **Source**
---|---|---|---
john.doe@acme.com | ✅ Deliverable | Work | Email pattern guess
johndoe@gmail.com | ✅ Deliverable | Personal | GitHub commit
john@oldco.com | ❌ Undeliverable | Work | LinkedIn (historical)
info@acme.com | ⚠️ Catch-all | Work | Pattern guess

**Status meanings**:
- ✅ **Deliverable**: SMTP server confirmed this inbox exists — safe to email
- ⚠️ **Catch-all**: Domain accepts all emails (might still work, but less reliable)
- ❌ **Undeliverable**: Bounced or invalid — don't email this address
- ❓ **Unknown**: Could not verify (server offline or blocking verification)

**Type meanings**:
- **Work**: Corporate email at a company domain
- **Personal**: Gmail, Outlook, Yahoo, etc.
- **Disposable**: Temporary email service (10minutemail, etc.)

**Sources**:
- GitHub commit email
- Email pattern guess (first.last@company.com)
- LinkedIn profile (if public)
- Public directories

**Best practices**:
1. **Prioritize Deliverable work emails** for B2B outreach
2. **Avoid Undeliverable emails** — they'll hurt your sender reputation
3. **Test Catch-all emails** in small batches before bulk sending
4. **Respect personal emails** — use work addresses for business outreach

<!-- Screenshot: Emails tab with status badges -->

---

### Professional Tab

**GitHub activity, coworkers, and job listings** for career and company intelligence.

**GitHub Section**:
- Profile link
- Repository count and contribution stats
- Top programming languages
- Recent commit activity
- Public projects (with descriptions)

**Coworkers Section**:
- Names and GitHub profiles
- Discovered via GitHub org membership
- Useful for mapping team structures
- Can enrich coworkers individually for contact info

**Job Listings Section** (Tier 4 only):
- Job title and company
- Location and remote status
- Salary range (if disclosed)
- Post date
- Source board (Indeed, LinkedIn, etc.)
- Direct application link

<!-- Screenshot: Professional tab showing GitHub and jobs -->

---

### Raw JSON Tab

**Complete technical output** for developers and advanced users.

**What you'll see**:
- Full API response in JSON format
- All metadata and timestamps
- Source attribution for every data point
- Confidence scores and enricher details

**When to use**:
- Integrating with your own systems (CRM, ATS, etc.)
- Debugging unexpected results
- Auditing data sources
- Exporting to other tools

**Copy buttons** let you grab the entire JSON or specific sections.

<!-- Screenshot: Raw JSON tab with formatted JSON -->

---

## 5. Common Questions

### Q: How long does enrichment take?

**A:** Depends on which tiers you select:

| Tier(s) Selected | Expected Time |
|------------------|---------------|
| Single tier (2, 3, or 4) | 30 seconds - 1 minute |
| Two tiers | 1 - 2 minutes |
| Three tiers | 2 - 3 minutes |
| All four tiers | 3 - 4 minutes |

**Tier 1** (LinkedIn photo) adds 30-60 seconds due to browser automation.

**Tier 4** (jobs) can take 2+ minutes if searching across all boards.

**Pro tip**: Use **async mode** for multi-tier enrichment so you can continue working while it runs in the background.

---

### Q: Why are some fields empty?

**A:** Empty fields mean one of these things:

1. **Data not publicly available**: The person hasn't shared that info publicly
2. **Privacy settings**: Account is private or restricted
3. **Opt-out protected**: Target has requested suppression
4. **Platform doesn't exist**: Person doesn't have an account on that platform
5. **Rate limit reached**: LinkedIn photo temporarily unavailable (Tier 1 only)

**This is normal!** Not everyone has a GitHub, not everyone posts their email publicly. Empty fields just mean we couldn't find public data.

---

### Q: Can I upload a CSV for bulk enrichment?

**A:** Currently, HyerEnrichment processes **one entity at a time** through the web console.

**Coming soon**: Batch CSV upload for multiple profiles

**Workaround for now**:
- Use the **Async mode** to queue multiple enrichments
- Keep the tab open and submit one after another
- Each job tracks independently

For **bulk processing** (100+ profiles), contact your administrator about the API endpoint or a custom integration.

---

### Q: Is this legal? Where does the data come from?

**A:** Yes, HyerEnrichment is legal and compliant:

**Data sources**:
- **Public web pages** (LinkedIn, GitHub, Twitter, etc.)
- **Public APIs** (GitHub API, job board APIs, Google Maps API)
- **Open-source intelligence (OSINT) techniques**
- **DNS/SMTP verification** for email checking

**What we DON'T do**:
- ❌ Hack or break into systems
- ❌ Buy data from shady data brokers
- ❌ Ignore robots.txt or rate limits
- ❌ Scrape private/password-protected content
- ❌ Build or sell databases

**Compliance framework**:
- ✅ **GDPR compliant** (EU General Data Protection Regulation)
- ✅ **CCPA compliant** (California Consumer Privacy Act)
- ✅ **Opt-out honored** within 48 hours
- ✅ **Data subject access rights** (DSAR)
- ✅ **Audit trail** for all enrichments

**Legal basis**: Public data aggregation and "legitimate interest" under GDPR Article 6(1)(f) for recruiting, sales, and research purposes. Data subjects can object via `/opt-out`.

---

### Q: How do I export my results?

**A:** You have several export options:

1. **Copy Raw JSON**: Use the "Copy JSON" button in the Raw JSON tab
2. **Screenshot**: Capture specific tabs for your records
3. **Manual copy/paste**: Copy handles, emails, or job listings from the UI

**Coming soon**:
- CSV export button
- PDF dossier generation
- Direct CRM integration

**For developers**: Access the API directly at `GET /api/jobs/{job_id}` to retrieve JSON programmatically.

---

### Q: What if I find incorrect information?

**A:** Data quality depends on public sources — sometimes they're outdated or wrong.

**If you find errors**:
1. **Check the source**: Click through to the original profile (GitHub, LinkedIn, etc.)
2. **Verify confidence level**: LOW confidence signals often need manual review
3. **Cross-reference**: Use multiple identifiers (email + username) for better accuracy

**Remember**: We surface data as-is from public sources. We don't edit or "clean" it — you get the raw intelligence.

**Report issues**: If you believe a technical error occurred (not just outdated public data), contact your administrator with the Job ID.

---

### Q: Can I enrich the same person multiple times?

**A:** Yes! Enrichment is always fresh.

**Why re-enrich**:
- **Job changes**: Their LinkedIn/GitHub updated
- **New social profiles**: They joined new platforms
- **Email changes**: New work email after switching jobs
- **More context**: You have additional identifiers now (e.g., found their GitHub username)

**Cache behavior**:
- **Tier 1 photos**: Cached in R2 (won't re-fetch if recent)
- **All other tiers**: Always fetch fresh data

**Best practice**: Re-enrich quarterly for active candidates/leads to keep data current.

---

### Q: What's the difference between async and sync mode?

**A:**

| Feature | **Async Mode** | **Sync Mode** |
|---------|----------------|---------------|
| **Speed** | 1-4 minutes | Under 30 seconds |
| **Best for** | Multi-tier deep research | Single-tier quick lookups |
| **Progress tracking** | ✅ Live updates | ❌ Wait for response |
| **Can navigate away** | ✅ Yes, come back later | ❌ No, must stay on page |
| **Job history** | ✅ Saved and retrievable | ❌ No history |
| **Tier limit** | All 4 tiers | Best with 1-2 tiers |

**Recommendation**: Use **async** for most enrichments. Use **sync** only when you need a single tier result immediately and don't care about tracking.

---

### Q: What do confidence scores mean?

**A:** Confidence indicates how certain we are that a discovered handle/email belongs to your target.

**HIGH confidence** (🟢 GREEN):
- Multiple signals confirm the match
- Active account with recent activity
- Username exactly matches input
- Cross-verified across platforms

**Example**: Username `johndoe` → found GitHub `github.com/johndoe` with 500+ commits and bio mentioning "Acme Corp"

**MEDIUM confidence** (🟡 YELLOW):
- Partial match or single signal
- Account exists but limited verification
- Username similar but not exact match

**Example**: Email `john.doe@company.com` guessed from pattern, but SMTP verification says "catch-all domain"

**LOW confidence** (🔴 RED):
- Weak signal or possible false positive
- Private account with no visible activity
- Common username that could belong to many people

**Example**: Instagram `instagram.com/john` found, but account is private and username is very common

**Best practice**:
- ✅ Trust HIGH confidence results
- ⚠️ Manually verify MEDIUM confidence before taking action
- 🔍 Investigate LOW confidence — often false positives

---

## 6. Privacy & Opt-Out

HyerEnrichment respects individual privacy rights and complies with global data protection regulations.

### How to Request Suppression

If you are an individual who wishes to opt out of enrichment:

1. **Visit** `/opt-out` on the HyerEnrichment domain
2. **Provide identifying information**:
   - Email address(es)
   - LinkedIn URL
   - Any usernames used across platforms
3. **Submit request**
4. **Confirmation**: You'll receive confirmation within 24 hours
5. **Effective immediately**: Your identifiers are suppressed within 48 hours

**What happens after opt-out**:
- ✅ Future enrichments return empty results for your identifiers
- ✅ Existing cached data is purged (photos, handles, emails)
- ✅ Your identifiers are added to a suppression list (hashed, not stored plaintext)
- ✅ Audit trail created for compliance

**Note**: Opt-out applies to **this specific HyerEnrichment instance**. If you've been enriched by other services or data brokers, you must opt out with each separately.

---

### GDPR & CCPA Compliance

**Your rights under GDPR (EU residents)**:
- **Right to access**: Request a copy of all data we hold about you
- **Right to erasure**: Request deletion of your data ("right to be forgotten")
- **Right to rectification**: Request correction of inaccurate data
- **Right to object**: Object to processing of your data
- **Right to data portability**: Receive your data in a machine-readable format

**Your rights under CCPA (California residents)**:
- **Right to know**: What personal information we collect and how we use it
- **Right to delete**: Request deletion of your personal information
- **Right to opt-out**: Opt out of "sale" of personal information (we don't sell data)
- **Right to non-discrimination**: We won't discriminate against you for exercising your rights

**How to exercise these rights**: Visit `/dsar` (Data Subject Access Request) or email the administrator.

---

### Data Deletion Procedures

**When data is deleted**:
1. **Immediate opt-out**: `/opt-out` submission
2. **DSAR deletion request**: `/dsar` with "delete" action
3. **Automatic purge**: Jobs older than retention period (configurable)
4. **Compliance sweep**: Periodic automated cleanup

**What gets deleted**:
- ✅ Job records and enrichment results
- ✅ Cached photos (R2 and local storage)
- ✅ Associated metadata and timestamps
- ✅ Intermediate processing data

**What is retained** (for compliance):
- ✅ Suppression list entries (hashed identifiers)
- ✅ Audit logs (5-year retention for legal compliance)
- ✅ Anonymized usage metrics

**Deletion timeline**: Most data is purged within 48 hours. Distributed caches (CDN, R2) may take up to 72 hours.

---

### How We Protect Your Privacy

**For end users being enriched**:
- ✅ Public data only — no private/protected content
- ✅ Opt-out honored immediately
- ✅ No data sales or third-party sharing
- ✅ Encrypted storage (at rest and in transit)
- ✅ Rate limits respect platform ToS
- ✅ Audit trail for all enrichments

**For HyerEnrichment customers**:
- ✅ Your enrichment history is private
- ✅ Results not shared with other customers
- ✅ Bearer token authentication required
- ✅ IP rate limiting for abuse prevention
- ✅ Self-hosted option for full data control

---

### Contact & Questions

**For data subject requests (opt-out, access, deletion)**:
- Web form: `/opt-out` or `/dsar`
- Response time: 24-48 hours

**For technical support**:
- Contact your HyerEnrichment administrator
- Include Job ID for troubleshooting

**For privacy policy & legal**:
- Review `/legal` for full terms and privacy policy

---

## Appendix: Quick Reference

### Input Field Cheat Sheet

| You have... | Fill in these fields | Use these tiers |
|-------------|----------------------|-----------------|
| LinkedIn URL | `linkedin_url` | Tier 1, 2, 3 |
| Email address | `email` | Tier 3 |
| Social username | `username` | Tier 2, 3 |
| Company name + person name | `company`, `name` | Tier 3 (coworkers) |
| Job title + location | `job_title`, `location` | Tier 4 |
| Business name + city | `business_query` | Tier 4 |

### Tier Selection Guide

| Your goal | Select these tiers |
|-----------|-------------------|
| Recruit candidates | Tier 1 + 2 + 3 |
| Sales outreach | Tier 3 |
| Investor due diligence | All tiers |
| Background check | Tier 2 + 3 |
| Job search | Tier 4 |
| Market research | Tier 4 |

### Time Estimates

| Tier combination | Duration |
|------------------|----------|
| Tier 2 only | 30 seconds |
| Tier 3 only | 45 seconds |
| Tier 2 + 3 | 1 minute |
| Tier 1 + 2 + 3 | 2-3 minutes |
| All tiers | 3-4 minutes |

### Confidence Score Guide

| Score | Icon | Meaning | Action |
|-------|------|---------|--------|
| HIGH | 🟢 | Verified match | Trust and use |
| MEDIUM | 🟡 | Probable match | Verify manually |
| LOW | 🔴 | Possible match | Investigate before use |

### Email Status Guide

| Status | Icon | Meaning | Safe to email? |
|--------|------|---------|----------------|
| Deliverable | ✅ | SMTP verified | Yes |
| Catch-all | ⚠️ | Domain accepts all | Maybe |
| Undeliverable | ❌ | Bounced/invalid | No |
| Unknown | ❓ | Could not verify | Uncertain |

---

**Last updated**: July 30, 2026
**Version**: 1.0
**For technical documentation**, see `backend/docs/ARCHITECTURE.md`
