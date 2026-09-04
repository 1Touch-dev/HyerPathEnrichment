# Job Location Filtering Feature - Implementation Guide

## Overview

This document describes the implementation of location-based job search filtering in the Hyrepath Enrichment system. This feature allows enrichment requests to find jobs specific to geographic regions instead of defaulting to US results.

## Problem Statement

Previously, when using Tier 4 job search with just a job title, the system would return predominantly US-based results because:
1. The `job_search` field combined title and location into a single string
2. The JobSpy enricher wasn't using the `location` and `country_indeed` parameters
3. JobSpy defaults to `country_indeed="usa"` when no country is specified

## Solution Architecture

The solution adds explicit location and country filtering at three layers:

### 1. Backend Domain Model
**File: `backend/app/domain/enrichment.py`**

Added three new optional fields to `EnrichmentRequest`:
```python
class EnrichmentRequest(BaseModel):
    # ... existing fields ...
    job_title: str | None = None       # Separate job title
    job_location: str | None = None    # City, state, or region
    job_country: str | None = None     # Country for Indeed/Glassdoor filtering
```

### 2. JobSpy Enricher
**File: `backend/app/enrichers/jobspy.py`**

Updated the enricher to use location parameters with enhanced compatibility:

```python
def _scrape(self, search_term, location, country, company, limit):
    kwargs = {
        "site_name": list(JOBSPY_SITES),
        "search_term": search_term,
        "results_wanted": limit,
    }

    # Format location for better Glassdoor/Indeed compatibility
    formatted_location = self._format_location(location, country)

    if formatted_location:
        kwargs["location"] = formatted_location  # Used by all job boards

    if country:
        kwargs["country_indeed"] = country.lower()  # Used by Indeed & Glassdoor

    # Google Jobs uses natural language queries
    if location and search_term:
        kwargs["google_search_term"] = f"{search_term} jobs in {formatted_location}"

    frame = scrape_jobs(**kwargs)
```

**Key improvements:**
- **Location formatting**: Automatically formats locations as "City, Country" for better parsing
- **Google Jobs support**: Uses `google_search_term` parameter with natural language query
- **Enhanced logging**: Tracks which job boards succeed/fail and result counts
- **Better error handling**: Catches and logs specific failures per job board

**How it works:**
- `location`: City, state, or region (e.g., "Berlin", "San Francisco, CA")
  - Used by: LinkedIn, Indeed, Glassdoor, ZipRecruiter
  - Automatically formatted for compatibility
- `country_indeed`: Country name for regional Indeed/Glassdoor sites
  - Used by: Indeed, Glassdoor
  - Must match exact country names from JobSpy's supported list
  - LinkedIn searches globally, ignores this parameter
- `google_search_term`: Natural language query for Google Jobs
  - Format: "{job_title} jobs in {location}"
  - Example: "Software Engineer jobs in Berlin, Germany"

### 3. Frontend Integration
**Files: `frontend/src/lib/types.ts`, `frontend/src/lib/api-adapter.ts`, `frontend/components/console/IntakeForm.tsx`**

Added UI fields and API mapping:
```typescript
export type EnrichmentInput = {
  // ... existing fields ...
  jobTitle?: string;      // Separate job title field
  jobLocation?: string;   // City/region field
  jobCountry?: string;    // Country field (e.g., "USA", "Germany")
}
```

The form now has three separate fields:
- **Job Title**: e.g., "Senior Backend Engineer"
- **Job Location**: e.g., "Remote, San Francisco, Berlin"
- **Job Country**: e.g., "USA", "Germany", "Canada"

### 4. Metadata Tracking
**File: `backend/app/enrichers/merge.py`**

Updated `base_dossier()` to capture location context:
```python
if request.job_title:
    metadata["job_title"] = request.job_title
if request.job_location:
    metadata["job_location"] = request.job_location
if request.job_country:
    metadata["job_country"] = request.job_country
```

## JobSpy Country Support

JobSpy supports 60+ countries for Indeed and Glassdoor. Key examples:

### Commonly Used Countries
- **North America**: USA, Canada, Mexico
- **Europe**: Germany, UK, France, Spain, Italy, Netherlands, Switzerland, Austria, Belgium
- **Asia Pacific**: India, Singapore, Hong Kong, Japan, Australia, New Zealand
- **Middle East**: UAE, Saudi Arabia, Kuwait, Qatar, Bahrain

### Important Notes
1. Use lowercase country names (e.g., "germany" not "Germany")
2. LinkedIn ignores `country_indeed` and relies solely on `location`
3. ZipRecruiter only searches US and Canada
4. Google Jobs uses `google_search_term` (not affected by these changes)

Full list: https://mintlify.wiki/speedyapply/JobSpy/guides/supported-countries

## Usage Examples

### Example 1: US-based Job Search
```json
POST /api/enrich
{
  "job_title": "Software Engineer",
  "job_location": "San Francisco, CA",
  "job_country": "USA",
  "requested_tiers": ["tier4"]
}
```

### Example 2: Germany-based Job Search
```json
POST /api/enrich
{
  "job_title": "Backend Developer",
  "job_location": "Berlin",
  "job_country": "Germany",
  "requested_tiers": ["tier4"]
}
```

### Example 3: Remote + Global Search
```json
POST /api/enrich
{
  "job_title": "Remote DevOps Engineer",
  "job_location": "Remote",
  "requested_tiers": ["tier4"]
}
```

### Example 4: Mixed Usage (Backward Compatible)
```json
POST /api/enrich
{
  "job_search": "Data Scientist London",
  "requested_tiers": ["tier4"]
}
```
**Note**: The legacy `job_search` field still works, but doesn't provide location filtering.

## Testing

### Manual Testing via UI
1. As a staff user, navigate to `/osint` in the frontend
2. Fill in the job fields:
   - Job Title: "Software Engineer"
   - Job Location: "Berlin"
   - Job Country: "Germany"
3. Select Tier 4
4. Submit the enrichment request
5. Verify that returned jobs are predominantly from Germany/Berlin

### Automated Testing
Run the test script:
```bash
cd backend
python test_job_location_filtering.py
```

This will test:
- US-specific job search (San Francisco, USA)
- Germany-specific job search (Berlin, Germany)
- Baseline search without location

### API Testing with curl
```bash
# Test with location filtering
curl -X POST http://localhost:8000/api/enrich \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "job_title": "Backend Engineer",
    "job_location": "Berlin",
    "job_country": "Germany",
    "requested_tiers": ["tier4"]
  }'

# Poll for results
curl http://localhost:8000/api/enrich/JOB_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Migration Notes

### Backward Compatibility
- The `job_search` field is still supported for backward compatibility
- Existing API clients will continue to work without changes
- New clients should use the separate `job_title`, `job_location`, and `job_country` fields for better filtering

### Frontend Updates
The frontend automatically:
1. Combines `jobTitle` and `jobLocation` into `jobSearch` for display purposes
2. Sends separate `job_title`, `job_location`, and `job_country` fields to the backend
3. Falls back to `jobSearch` if the separate fields aren't provided

### Database Schema
No database migrations required. The new fields are:
- Stored in the `request_payload` JSONB column of the `jobs` table
- Captured in the dossier `metadata` JSONB column

## Performance Considerations

1. **Job Board Specificity**:
   - Indeed & Glassdoor: Filter by country AND location
   - LinkedIn: Filters by location globally
   - ZipRecruiter: US/Canada only (ignores country)

2. **Search Speed**:
   - No performance impact; parameters are passed directly to JobSpy
   - JobSpy handles multi-board scraping with ThreadPoolExecutor

3. **Result Quality**:
   - More relevant results due to geographic filtering
   - Reduces noise from irrelevant locations

## Files Changed

### Backend
- `backend/app/domain/enrichment.py` - Added location fields to EnrichmentRequest
- `backend/app/enrichers/jobspy.py` - Updated to use location & country parameters
- `backend/app/enrichers/merge.py` - Added location metadata tracking

### Frontend
- `frontend/src/lib/types.ts` - Added jobCountry to EnrichmentInput
- `frontend/src/lib/api-adapter.ts` - Updated mapping functions
- `frontend/components/console/IntakeForm.tsx` - Added jobCountry input field

### Testing
- `backend/test_job_location_filtering.py` - New test script

## Future Enhancements

1. **Country Autocomplete**: Add a dropdown for country selection in the UI
2. **Location Validation**: Validate location strings against known cities/regions
3. **Distance Filtering**: Expose JobSpy's `distance` parameter (radius in miles)
4. **Job Type Filtering**: Add `job_type` field (fulltime, parttime, contract, internship)
5. **Remote-Only Filter**: Add `is_remote` boolean field

## References

- JobSpy Documentation: https://mintlify.wiki/speedyapply/JobSpy/
- Supported Countries: https://mintlify.wiki/speedyapply/JobSpy/guides/supported-countries
- Filtering Guide: https://mintlify.wiki/speedyapply/JobSpy/guides/filtering-results
- Indeed Parameters: https://mintlify.wiki/speedyapply/JobSpy/job-boards/indeed

## 🔧 Troubleshooting

### Job Board Issues

**Glassdoor: "location not parsed" error**
- **Cause**: Glassdoor requires precise location matching
- **Fix**: Use "City, State" format (e.g., "San Francisco, CA" not "San Fransico")
- **Also works**: Just state name ("California") or country ("Germany")

**ZipRecruiter: 403 Forbidden error**
- **Cause**: Bot detection / rate limiting
- **Fix**: Use proxy rotation (`PROXY_MODE=paid` with Oxylabs or similar)
- **Note**: ZipRecruiter is US/Canada only

**Indeed: Silent failures**
- **Cause**: Missing or incorrect `country_indeed` parameter
- **Fix**: Ensure `job_country` field is set correctly
- **Example**: "USA", "Germany", "UK" (case-insensitive)

**Google Jobs: No results**
- **Cause**: Uses different search mechanism
- **How it works**: Uses natural language `google_search_term`
- **Automatically generated**: "{job_title} jobs in {location}"

### Check Worker Logs

View real-time job board errors:
```bash
docker logs docker-worker-tier234-1 --follow | grep -i "jobspy\|indeed\|glassdoor"
```

Common error patterns:
- `ERROR - JobSpy:Glassdoor - location not parsed` → Location format issue
- `ERROR - JobSpy:ZipRecruiter - response status code 403` → Bot detection
- `INFO - JobSpy:Linkedin - finished scraping` → Success

### Verify Request Data

Check what was actually sent to the enricher:
```bash
docker exec docker-postgres-1 psql -U hyrepath -d hyrepath \
  -c "SELECT request_payload FROM jobs WHERE id='JOB_ID' \G"
```

Ensure it includes:
```json
{
  "job_title": "Backend Developer",
  "job_location": "Berlin",
  "job_country": "Germany"
}
```

## Support

For issues or questions about job location filtering:
1. Check JobSpy's supported countries list
2. Verify country names are lowercase (e.g., "germany" not "Germany")
3. Test with the provided test script
4. Check logs for JobSpy errors in the worker service
