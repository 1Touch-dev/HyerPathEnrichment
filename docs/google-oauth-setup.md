# Google OAuth Setup Guide

This guide walks you through setting up Google OAuth authentication for Hyrepath Enrichment.

## Prerequisites

- Google Cloud account
- Access to Google Cloud Console

## Step 1: Create a Google Cloud Project

1. Navigate to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown in the top navigation bar
3. Click "New Project"
4. Enter project name: "Hyrepath Enrichment" (or your preferred name)
5. Click "Create"

## Step 2: Enable Google OAuth API

1. In your project, go to "APIs & Services" > "Library"
2. Search for "Google+ API" or "Google Identity"
3. Click "Enable"

## Step 3: Configure OAuth Consent Screen

1. Go to "APIs & Services" > "OAuth consent screen"
2. Choose "External" user type (unless you have a Google Workspace)
3. Click "Create"
4. Fill in the required fields:
   - **App name**: Hyrepath Enrichment
   - **User support email**: your email
   - **Developer contact email**: your email
5. Click "Save and Continue"
6. **Scopes**: Click "Add or Remove Scopes"
   - Add: `.../auth/userinfo.email`
   - Add: `.../auth/userinfo.profile`
   - Add: `openid`
7. Click "Save and Continue"
8. **Test users** (for development):
   - Add your email and any team members' emails
9. Click "Save and Continue"
10. Review and click "Back to Dashboard"

## Step 4: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Application type: **Web application**
4. Name: "Hyrepath Enrichment Web Client"
5. **Authorized JavaScript origins**:
   - Development: `http://localhost:3000`
   - Production: `https://yourdomain.com`
6. **Authorized redirect URIs**:
   - Development: `http://localhost:3000/callback/google`
   - Production: `https://yourdomain.com/callback/google`
7. Click "Create"
8. **Save your credentials**:
   - Client ID: `xxxxx.apps.googleusercontent.com`
   - Client secret: `GOCSPX-xxxxx`

## Step 5: Configure Backend Environment

Add to `backend/.env`:

```bash
# Google OAuth
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-your-secret
GOOGLE_OAUTH_REDIRECT_URL=http://localhost:3000/callback/google

# Frontend URL
FRONTEND_URL=http://localhost:3000
```

## Step 6: Configure Frontend Environment

Add to `frontend/.env.local`:

```bash
BACKEND_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## Step 7: Test OAuth Flow

1. Start backend:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. Start frontend:
   ```bash
   cd frontend
   npm run dev
   ```

3. Navigate to `http://localhost:3000/login`
4. Click "Sign in with Google"
5. Authorize the app
6. You should be redirected back to the app and logged in

## Production Deployment

### Update OAuth Redirect URIs

1. Go back to Google Cloud Console > Credentials
2. Edit your OAuth 2.0 Client ID
3. Add production URLs:
   - **Authorized JavaScript origins**: `https://yourdomain.com`
   - **Authorized redirect URIs**: `https://yourdomain.com/callback/google`
4. Update environment variables:
   ```bash
   GOOGLE_OAUTH_REDIRECT_URL=https://yourdomain.com/callback/google
   FRONTEND_URL=https://yourdomain.com
   COOKIE_SECURE=true
   COOKIE_DOMAIN=.yourdomain.com
   ```

### Enable HTTPS

- Set `COOKIE_SECURE=true` to ensure cookies are only sent over HTTPS
- Configure your reverse proxy (Nginx, Caddy, etc.) for SSL/TLS

## Troubleshooting

### "Redirect URI mismatch" error

- Ensure redirect URI in Google Console exactly matches the one in your request
- Check for trailing slashes (Google is strict about this)
- Verify protocol (http vs https)

### "Access blocked: This app's request is invalid"

- Verify OAuth consent screen is configured
- Check that all required scopes are added
- Ensure the app is not in "Testing" mode or add yourself as a test user

### "Invalid client" error

- Double-check `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`
- Ensure no extra spaces or newlines in environment variables

### Users can't sign in after first attempt

- Check that email verification is working
- Verify frontend can reach backend API
- Check browser console for CORS errors

## Security Best Practices

1. **Never commit OAuth secrets** to version control
2. Use environment variables for all sensitive data
3. Rotate OAuth secrets periodically
4. Enable "OAuth consent screen verification" for production (if serving >100 users)
5. Monitor OAuth usage in Google Cloud Console
6. Set up alerts for unusual activity

## Rate Limits

Google OAuth has the following rate limits:

- 10,000 requests per day (default)
- 100 requests per 100 seconds per user

For higher limits, request a quota increase in Google Cloud Console.

## References

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Google Cloud Console](https://console.cloud.google.com/)
- [OAuth 2.0 Scopes](https://developers.google.com/identity/protocols/oauth2/scopes)
