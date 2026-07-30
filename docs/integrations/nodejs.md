# Node.js/TypeScript Client Examples

Complete Node.js and TypeScript integration examples for the Hyrepath Enrichment API.

## Installation

```bash
npm install axios
# For TypeScript
npm install --save-dev @types/node typescript
```

## Authentication

All API requests require an API token in the `Authorization` header:

```typescript
const API_TOKEN = "your-api-token-here";
const BASE_URL = "https://enrich.hyrepath.io";  // or "http://localhost:8000" for dev

const headers = {
  Authorization: `Bearer ${API_TOKEN}`,
  "Content-Type": "application/json",
};
```

---

## 1. TypeScript Types from OpenAPI

Type definitions derived from the OpenAPI specification.

```typescript
// types.ts

export type JobStatus =
  | "queued"
  | "running"
  | "completed"
  | "completed_no_data"
  | "failed"
  | "suppressed"
  | "purged";

export type RequestedTier = "tier1" | "tier2" | "tier3" | "tier4";

export interface EnrichmentRequest {
  email?: string | null;
  linkedin_url?: string | null;
  username?: string | null;
  company?: string | null;
  business?: string | null;
  job_search?: string | null;
  requested_tiers?: RequestedTier[];
}

export interface SocialHandle {
  platform: string;
  username: string;
  profile_url: string;
  confidence: number;
  metadata?: Record<string, any>;
}

export interface VerifiedEmail {
  value: string;
  status: string;
  confidence: number;
  source: string;
}

export interface PhotoAsset {
  source: string;
  asset_url: string;
  captured_at: string;
  confidence: number;
}

export interface JobListing {
  title: string;
  company: string;
  location: string;
  remote: boolean;
  source: string;
}

export interface BusinessProfile {
  name: string;
  address: string;
  website: string;
  rating: number;
  phone: string;
  metadata?: Record<string, any>;
}

export interface ConfidenceBreakdown {
  label: string;
  score: number;
  evidence: string[];
}

export interface Dossier {
  emails?: string[];
  verified_emails?: VerifiedEmail[];
  handles?: SocialHandle[];
  photo?: PhotoAsset | null;
  coworkers?: string[];
  jobs?: JobListing[];
  business?: BusinessProfile | null;
  github?: Record<string, any>;
  confidence?: ConfidenceBreakdown[];
  sources?: string[];
  metadata?: Record<string, any>;
}

export interface EnrichmentJobResponse {
  id: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  dossier: Dossier;
}

export interface EnrichmentJobListItem {
  id: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  identifier_summary?: string;
  request_payload?: Record<string, any>;
}

export interface EnrichmentJobListResponse {
  jobs: EnrichmentJobListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface SuccessResponse<T> {
  success: true;
  data: T;
  message?: string | null;
  meta?: Record<string, any> | null;
}

export interface ErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    status_code: number;
    details?: any;
  };
  meta?: Record<string, any> | null;
}
```

---

## 2. Async Enrichment with Promises

Submit an enrichment job and poll until completion.

```typescript
// enrichment-client.ts
import axios, { AxiosInstance } from "axios";
import {
  EnrichmentRequest,
  EnrichmentJobResponse,
  SuccessResponse,
  JobStatus,
} from "./types";

const API_TOKEN = "your-api-token-here";
const BASE_URL = "https://enrich.hyrepath.io";

export class EnrichmentClient {
  private client: AxiosInstance;

  constructor(apiToken: string, baseUrl: string = BASE_URL) {
    this.client = axios.create({
      baseURL: baseUrl,
      headers: {
        Authorization: `Bearer ${apiToken}`,
        "Content-Type": "application/json",
      },
    });
  }

  /**
   * Create an async enrichment job
   */
  async createJob(request: EnrichmentRequest): Promise<string> {
    const response = await this.client.post<
      SuccessResponse<EnrichmentJobResponse>
    >("/enrich", request);

    const jobId = response.data.data.id;
    console.log(`✓ Job created: ${jobId}`);
    return jobId;
  }

  /**
   * Get job status and results
   */
  async getJob(jobId: string): Promise<EnrichmentJobResponse> {
    const response = await this.client.get<
      SuccessResponse<EnrichmentJobResponse>
    >(`/enrich/${jobId}`);

    return response.data.data;
  }

  /**
   * Poll job until completion
   */
  async pollUntilComplete(
    jobId: string,
    options: {
      pollInterval?: number; // milliseconds
      timeout?: number; // milliseconds
    } = {}
  ): Promise<EnrichmentJobResponse> {
    const { pollInterval = 2000, timeout = 300000 } = options;
    const startTime = Date.now();

    while (true) {
      const elapsed = Date.now() - startTime;

      if (elapsed > timeout) {
        throw new Error(
          `Job ${jobId} did not complete within ${timeout / 1000}s`
        );
      }

      const job = await this.getJob(jobId);
      const status = job.status;

      console.log(`  Status: ${status} (elapsed: ${(elapsed / 1000).toFixed(1)}s)`);

      // Terminal states
      const terminalStates: JobStatus[] = [
        "completed",
        "completed_no_data",
        "failed",
        "suppressed",
      ];

      if (terminalStates.includes(status)) {
        if (status === "completed") {
          console.log("✓ Job completed successfully");
        } else if (status === "completed_no_data") {
          console.log("⚠ Job completed but no data found");
        } else if (status === "failed") {
          console.log("✗ Job failed");
        } else if (status === "suppressed") {
          console.log("⚠ Job suppressed (opt-out)");
        }
        return job;
      }

      // Wait before next poll
      await new Promise((resolve) => setTimeout(resolve, pollInterval));
    }
  }

  /**
   * Synchronous enrichment (blocks until complete)
   */
  async enrichSync(request: EnrichmentRequest): Promise<EnrichmentJobResponse> {
    console.log("⏳ Waiting for enrichment (this may take 30-120s)...");

    const response = await this.client.post<
      SuccessResponse<EnrichmentJobResponse>
    >("/enrich/sync", request, {
      timeout: 180000, // 3 minute timeout
    });

    const jobData = response.data.data;
    console.log(`✓ Job ${jobData.id} completed`);
    return jobData;
  }
}

// Example usage
async function main() {
  const client = new EnrichmentClient(API_TOKEN);

  // Example 1: Async with polling
  console.log("\n--- Example 1: Async enrichment ---");
  const jobId = await client.createJob({
    email: "john.doe@example.com",
    requested_tiers: ["tier1", "tier2", "tier3"],
  });

  const result = await client.pollUntilComplete(jobId);

  const dossier = result.dossier;
  console.log(`\nEnriched emails: ${dossier.emails?.length || 0}`);
  console.log(`Social handles: ${dossier.handles?.length || 0}`);

  // Example 2: Sync enrichment
  console.log("\n--- Example 2: Sync enrichment ---");
  const syncResult = await client.enrichSync({
    linkedin_url: "https://www.linkedin.com/in/johndoe",
    requested_tiers: ["tier1"],
  });

  console.log(`Job ID: ${syncResult.id}`);
}

main().catch(console.error);
```

---

## 3. Axios Interceptors for Rate Limits

Automatically retry on rate limit errors with exponential backoff.

```typescript
// rate-limit-client.ts
import axios, { AxiosInstance, AxiosError } from "axios";

const API_TOKEN = "your-api-token-here";
const BASE_URL = "https://enrich.hyrepath.io";

export class RateLimitClient {
  private client: AxiosInstance;
  private maxRetries: number;
  private initialBackoff: number;

  constructor(
    apiToken: string,
    baseUrl: string = BASE_URL,
    options: {
      maxRetries?: number;
      initialBackoff?: number; // milliseconds
    } = {}
  ) {
    this.maxRetries = options.maxRetries || 5;
    this.initialBackoff = options.initialBackoff || 2000;

    this.client = axios.create({
      baseURL: baseUrl,
      headers: {
        Authorization: `Bearer ${apiToken}`,
        "Content-Type": "application/json",
      },
    });

    // Add response interceptor for rate limit handling
    this.setupInterceptors();
  }

  private setupInterceptors() {
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const config = error.config as any;

        // Initialize retry count
        if (!config._retryCount) {
          config._retryCount = 0;
        }

        // Check if this is a rate limit error and we have retries left
        if (
          error.response?.status === 429 &&
          config._retryCount < this.maxRetries
        ) {
          config._retryCount++;

          // Calculate backoff time
          let waitTime: number;
          const retryAfter = error.response.headers["retry-after"];

          if (retryAfter) {
            waitTime = parseFloat(retryAfter) * 1000;
            console.log(
              `⏳ Rate limited. Retry-After: ${retryAfter}s (attempt ${config._retryCount}/${this.maxRetries})`
            );
          } else {
            // Exponential backoff: 2s, 4s, 8s, 16s, 32s
            waitTime = this.initialBackoff * Math.pow(2, config._retryCount - 1);
            console.log(
              `⏳ Rate limited. Backing off for ${(waitTime / 1000).toFixed(1)}s (attempt ${config._retryCount}/${this.maxRetries})`
            );
          }

          // Wait before retrying
          await new Promise((resolve) => setTimeout(resolve, waitTime));

          // Retry the request
          return this.client.request(config);
        }

        // For 503 errors (service unavailable), also retry
        if (
          error.response?.status === 503 &&
          config._retryCount < this.maxRetries
        ) {
          config._retryCount++;
          const waitTime =
            this.initialBackoff * Math.pow(2, config._retryCount - 1);

          console.log(
            `⏳ Service unavailable. Retrying in ${(waitTime / 1000).toFixed(1)}s (attempt ${config._retryCount}/${this.maxRetries})`
          );

          await new Promise((resolve) => setTimeout(resolve, waitTime));
          return this.client.request(config);
        }

        // No more retries or different error
        return Promise.reject(error);
      }
    );
  }

  /**
   * Make POST request with automatic rate limit handling
   */
  async post<T = any>(url: string, data?: any): Promise<T> {
    const response = await this.client.post<T>(url, data);
    return response.data;
  }

  /**
   * Make GET request with automatic rate limit handling
   */
  async get<T = any>(url: string, params?: any): Promise<T> {
    const response = await this.client.get<T>(url, { params });
    return response.data;
  }
}

// Example usage
async function testRateLimits() {
  const client = new RateLimitClient(API_TOKEN, BASE_URL, {
    maxRetries: 5,
    initialBackoff: 2000,
  });

  const emails = [
    "user1@example.com",
    "user2@example.com",
    "user3@example.com",
    "user4@example.com",
    "user5@example.com",
  ];

  for (const email of emails) {
    try {
      const response = await client.post("/enrich", {
        email,
        requested_tiers: ["tier1"],
      });

      console.log(`✓ Created job for ${email}: ${response.data.id}\n`);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        console.error(`✗ Failed for ${email}: ${error.response?.status} ${error.message}\n`);
      } else {
        console.error(`✗ Failed for ${email}: ${error}\n`);
      }
    }
  }
}

testRateLimits().catch(console.error);
```

---

## 4. Error Handling

Comprehensive error handling for all API responses.

```typescript
// error-handling.ts
import axios, { AxiosError } from "axios";

const API_TOKEN = "your-api-token-here";
const BASE_URL = "https://enrich.hyrepath.io";

interface APIError {
  code: string;
  message: string;
  status_code: number;
  details?: any;
}

class EnrichmentAPIError extends Error {
  public statusCode: number;
  public code: string;
  public details?: any;

  constructor(statusCode: number, code: string, message: string, details?: any) {
    super(message);
    this.name = "EnrichmentAPIError";
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
  }
}

function handleAPIError(error: AxiosError): never {
  if (error.response) {
    const status = error.response.status;
    const data = error.response.data as any;
    const apiError: APIError = data?.error;

    if (status === 401) {
      console.error("✗ Authentication failed");
      console.error("  → Check your API_TOKEN");
    } else if (status === 422) {
      console.error("✗ Validation error");
      console.error("  → Check request payload for missing/invalid fields");
      if (apiError?.details) {
        console.error(`  → Details:`, apiError.details);
      }
    } else if (status === 429) {
      console.error("✗ Rate limit exceeded");
      console.error("  → Implement exponential backoff (see common-errors.md)");
      const retryAfter = error.response.headers["retry-after"];
      if (retryAfter) {
        console.error(`  → Retry after: ${retryAfter}s`);
      }
    } else if (status === 503) {
      console.error("✗ Service unavailable");
      console.error("  → Redis may be down, retry with exponential backoff");
    }

    throw new EnrichmentAPIError(
      status,
      apiError?.code || "unknown",
      apiError?.message || error.message,
      apiError?.details
    );
  } else if (error.request) {
    console.error("✗ No response received from server");
    console.error("  → Check network connectivity or BASE_URL");
    throw new Error("No response from server");
  } else {
    console.error("✗ Request setup error:", error.message);
    throw error;
  }
}

async function safeEnrichmentRequest(
  email: string,
  tiers: string[] = ["tier1"]
): Promise<string> {
  try {
    const response = await axios.post(
      `${BASE_URL}/enrich`,
      {
        email,
        requested_tiers: tiers,
      },
      {
        headers: {
          Authorization: `Bearer ${API_TOKEN}`,
          "Content-Type": "application/json",
        },
        timeout: 30000,
      }
    );

    const jobId = response.data.data.id;
    console.log(`✓ Job created: ${jobId}`);
    return jobId;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      handleAPIError(error);
    }
    throw error;
  }
}

// Example usage
async function main() {
  try {
    const jobId = await safeEnrichmentRequest("test@example.com", [
      "tier1",
      "tier2",
    ]);
    console.log(`Success! Job ID: ${jobId}`);
  } catch (error) {
    if (error instanceof EnrichmentAPIError) {
      console.log("\nCaught API error:");
      console.log(`  Status: ${error.statusCode}`);
      console.log(`  Code: ${error.code}`);
      console.log(`  Message: ${error.message}`);
      if (error.details) {
        console.log(`  Details:`, error.details);
      }
    }
  }
}

main().catch(console.error);
```

---

## 5. List Jobs with Pagination

Retrieve paginated list of enrichment jobs.

```typescript
// list-jobs.ts
import axios from "axios";
import {
  EnrichmentJobListResponse,
  EnrichmentJobListItem,
  SuccessResponse,
} from "./types";

const API_TOKEN = "your-api-token-here";
const BASE_URL = "https://enrich.hyrepath.io";

const client = axios.create({
  baseURL: BASE_URL,
  headers: {
    Authorization: `Bearer ${API_TOKEN}`,
    "Content-Type": "application/json",
  },
});

/**
 * List enrichment jobs with pagination
 */
async function listJobs(
  limit: number = 20,
  offset: number = 0
): Promise<EnrichmentJobListResponse> {
  const response = await client.get<SuccessResponse<EnrichmentJobListResponse>>(
    "/enrich",
    {
      params: { limit, offset },
    }
  );

  return response.data.data;
}

/**
 * Retrieve all jobs by paginating through results
 */
async function listAllJobs(): Promise<EnrichmentJobListItem[]> {
  const allJobs: EnrichmentJobListItem[] = [];
  let offset = 0;
  const limit = 100; // Max page size

  while (true) {
    const page = await listJobs(limit, offset);
    allJobs.push(...page.jobs);

    console.log(`  Fetched ${allJobs.length} / ${page.total} jobs`);

    // Check if we've fetched everything
    if (allJobs.length >= page.total) {
      break;
    }

    offset += limit;
  }

  return allJobs;
}

// Example usage
async function main() {
  // List first page
  console.log("--- First page of jobs ---");
  const page = await listJobs(10, 0);

  console.log(`Total jobs: ${page.total}`);
  console.log(`Showing: ${page.jobs.length} jobs\n`);

  for (const job of page.jobs) {
    console.log(`Job ${job.id}`);
    console.log(`  Status: ${job.status}`);
    console.log(`  Created: ${job.created_at}`);
    console.log(`  Summary: ${job.identifier_summary || "N/A"}\n`);
  }

  // Fetch all jobs
  console.log("\n--- Fetching all jobs ---");
  const allJobs = await listAllJobs();
  console.log(`✓ Retrieved ${allJobs.length} total jobs`);
}

main().catch(console.error);
```

---

## 6. Complete Example: Production-Ready Client

Full-featured client with all functionality.

```typescript
// production-client.ts
import axios, { AxiosInstance, AxiosError } from "axios";
import {
  EnrichmentRequest,
  EnrichmentJobResponse,
  EnrichmentJobListResponse,
  SuccessResponse,
  JobStatus,
} from "./types";

export interface ClientOptions {
  apiToken: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
  initialBackoff?: number;
}

export class ProductionEnrichmentClient {
  private client: AxiosInstance;
  private maxRetries: number;
  private initialBackoff: number;

  constructor(options: ClientOptions) {
    const {
      apiToken,
      baseUrl = "https://enrich.hyrepath.io",
      timeout = 30000,
      maxRetries = 5,
      initialBackoff = 2000,
    } = options;

    this.maxRetries = maxRetries;
    this.initialBackoff = initialBackoff;

    this.client = axios.create({
      baseURL: baseUrl,
      timeout,
      headers: {
        Authorization: `Bearer ${apiToken}`,
        "Content-Type": "application/json",
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Rate limit handling
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const config = error.config as any;

        if (!config._retryCount) {
          config._retryCount = 0;
        }

        // Retry on 429 (rate limit) or 503 (service unavailable)
        const shouldRetry =
          (error.response?.status === 429 || error.response?.status === 503) &&
          config._retryCount < this.maxRetries;

        if (shouldRetry) {
          config._retryCount++;

          let waitTime: number;
          const retryAfter = error.response?.headers["retry-after"];

          if (retryAfter) {
            waitTime = parseFloat(retryAfter) * 1000;
          } else {
            waitTime =
              this.initialBackoff * Math.pow(2, config._retryCount - 1);
          }

          await new Promise((resolve) => setTimeout(resolve, waitTime));
          return this.client.request(config);
        }

        return Promise.reject(error);
      }
    );
  }

  /**
   * Create async enrichment job
   */
  async createJob(request: EnrichmentRequest): Promise<string> {
    const response = await this.client.post<
      SuccessResponse<EnrichmentJobResponse>
    >("/enrich", request);

    return response.data.data.id;
  }

  /**
   * Get job status and results
   */
  async getJob(jobId: string): Promise<EnrichmentJobResponse> {
    const response = await this.client.get<
      SuccessResponse<EnrichmentJobResponse>
    >(`/enrich/${jobId}`);

    return response.data.data;
  }

  /**
   * Poll job until completion
   */
  async pollUntilComplete(
    jobId: string,
    options: { pollInterval?: number; timeout?: number } = {}
  ): Promise<EnrichmentJobResponse> {
    const { pollInterval = 2000, timeout = 300000 } = options;
    const startTime = Date.now();

    while (true) {
      if (Date.now() - startTime > timeout) {
        throw new Error(`Job ${jobId} timeout after ${timeout / 1000}s`);
      }

      const job = await this.getJob(jobId);
      const terminalStates: JobStatus[] = [
        "completed",
        "completed_no_data",
        "failed",
        "suppressed",
      ];

      if (terminalStates.includes(job.status)) {
        return job;
      }

      await new Promise((resolve) => setTimeout(resolve, pollInterval));
    }
  }

  /**
   * Synchronous enrichment
   */
  async enrichSync(request: EnrichmentRequest): Promise<EnrichmentJobResponse> {
    const response = await this.client.post<
      SuccessResponse<EnrichmentJobResponse>
    >("/enrich/sync", request, {
      timeout: 180000, // 3 minutes
    });

    return response.data.data;
  }

  /**
   * List jobs with pagination
   */
  async listJobs(
    limit: number = 20,
    offset: number = 0
  ): Promise<EnrichmentJobListResponse> {
    const response = await this.client.get<
      SuccessResponse<EnrichmentJobListResponse>
    >("/enrich", {
      params: { limit, offset },
    });

    return response.data.data;
  }

  /**
   * Convenience method: enrich and wait for results
   */
  async enrichAndWait(
    request: EnrichmentRequest,
    options?: { pollInterval?: number; timeout?: number }
  ): Promise<EnrichmentJobResponse> {
    const jobId = await this.createJob(request);
    return this.pollUntilComplete(jobId, options);
  }
}

// Example usage
async function main() {
  const client = new ProductionEnrichmentClient({
    apiToken: "your-api-token-here",
    baseUrl: "https://enrich.hyrepath.io",
    maxRetries: 5,
    initialBackoff: 2000,
  });

  // Enrich and wait
  const result = await client.enrichAndWait({
    email: "john@example.com",
    requested_tiers: ["tier1", "tier2"],
  });

  console.log(`Job: ${result.id}`);
  console.log(`Status: ${result.status}`);
  console.log(`Emails: ${result.dossier.emails?.length || 0}`);
  console.log(`Handles: ${result.dossier.handles?.length || 0}`);
}

main().catch(console.error);
```

---

## Next Steps

- See [`bulk-processing.md`](./bulk-processing.md) for CSV batch processing patterns
- See [`common-errors.md`](./common-errors.md) for error handling reference
- See [`webhooks.md`](./webhooks.md) for webhook integration (future feature)
