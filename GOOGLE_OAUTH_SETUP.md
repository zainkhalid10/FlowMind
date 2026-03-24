# Google OAuth Setup Guide for FlowMind

## Overview
FlowMind now supports Google OAuth authentication, allowing users to sign in with their Google accounts. This guide walks you through the setup process.

## Prerequisites
- A Google Cloud Platform (GCP) account
- Access to the FlowMind codebase with the OAuth dependencies installed

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown at the top
3. Click "NEW PROJECT"
4. Enter project name: "FlowMind" (or your preferred name)
5. Click "CREATE"

## Step 2: Enable Google+ API

1. In the Cloud Console, navigate to "APIs & Services" → "Library"
2. Search for "Google+ API"
3. Click on it and then click "ENABLE"

## Step 3: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "CREATE CREDENTIALS"
3. Choose "OAuth client ID"
4. If prompted, configure the OAuth Consent Screen first:
   - Choose "External" user type
   - Fill in the required fields (app name, user support email, etc.)
   - Add scopes: `email`, `profile`, `openid`
   - Complete the configuration
5. Back to credentials, click "CREATE CREDENTIALS" again and choose "OAuth client ID"
6. Select "Web application"
7. Add authorized redirect URIs:
   - For **development**: `http://localhost:8000/auth/google/callback`
   - For **production**: `https://yourdomain.com/auth/google/callback`
8. Click "CREATE"
9. You should see a popup with your Client ID and Client Secret. Save these!

## Step 4: Configure FlowMind Environment

1. In the FlowMind root directory, check for `.env` file. If it doesn't exist, create one:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your OAuth credentials:
   ```env
   GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your_client_secret_here
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
   ```

3. Save the file and restart your FlowMind server:
   ```bash
   # Kill any running instance (or use Ctrl+C if running in terminal)
   # Then restart:
   python -m uvicorn flowmind:app --host 0.0.0.0 --port 8000
   ```

## Step 5: Test Google OAuth

1. Open your browser and navigate to `http://localhost:8000` (or your FlowMind instance)
2. You should see the landing page with "Continue with Google" button
3. Click the button and you should be redirected to Google's login page
4. Sign in with your Google account
5. Grant permission for FlowMind to access your email and profile
6. You should be redirected back to FlowMind dashboard and automatically signed in!

## How It Works

### Login with Google
- Click "Continue with Google" on the Sign In tab
- You'll be redirected to Google's authorization server
- After authenticating, Google redirects back to `/auth/google/callback` with an authorization code
- FlowMind exchanges the code for tokens and creates/logs in your user account
- Your JWT token is stored in localStorage and you're redirected to the dashboard

### Sign Up with Google
- Click "Sign up with Google" on the Sign Up tab
- Similar flow as login
- When signing up, you must select a role (Manager, Team Head, or Member)
- A new account is created with that role, linked to your Google identity
- You're automatically logged in and redirected to the dashboard

### Account Linking
- If you have an existing FlowMind account with the same email, clicking Google OAuth will link your Google ID to that account
- The hashed password is preserved but not used when signed in via OAuth

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_CLIENT_ID` | Yes | OAuth 2.0 Client ID from GCP |
| `GOOGLE_CLIENT_SECRET` | Yes | OAuth 2.0 Client Secret from GCP |
| `GOOGLE_REDIRECT_URI` | Yes | Callback URL (must match GCP configuration) |
| `SECRET_KEY` | Yes | JWT signing key (auto-generated if not provided) |

## Troubleshooting

### "Google OAuth not configured" error
- Check that `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set in your `.env` file
- Make sure the `.env` file is in the FlowMind root directory
- Restart the server after updating `.env`

### Redirect URI mismatch error
- Verify that `GOOGLE_REDIRECT_URI` in `.env` exactly matches:
  1. The URL in your GCP credentials configuration
  2. Your current deployment URL (localhost for dev, domain for prod)
- Remember that `http://` and `https://` are different URIs

### "Invalid token" errors
- Ensure `SECRET_KEY` is set in `.env`
- Check that your Google credentials are still valid
- Try clearing Browser localStorage and logging in again

### User creation fails
- Check that there's a default Team in the database (usually created on first setup)
- Verify that the username generated from your email doesn't already exist
- Check server logs for more detailed error messages

## Security Notes

1. **Never commit `.env` to version control** - Git ignores it by default
2. **Rotate credentials regularly** - Especially if you suspect compromise
3. **Use HTTPS in production** - Google OAuth requires secure HTTPS for production
4. **Use strong `SECRET_KEY`** - Generate using: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
5. **Limit OAuth scopes** - FlowMind currently requests only `email`, `profile`, and `openid`

## Production Deployment

For production deployment:

1. Update `GOOGLE_REDIRECT_URI` to your production domain:
   ```env
   GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/google/callback
   ```

2. Update the authorized redirect URI in GCP console to match

3. Ensure HTTPS is enabled on your server

4. Use environment variables from your deployment platform (e.g., AWS Secrets Manager, Heroku Config Vars, etc.)

## Support

If you encounter issues:
1. Check the server logs for detailed error messages
2. Verify your GCP credentials are correct
3. Ensure all required environment variables are set
4. Clear browser cache/localStorage and try again
5. Refer to [Google OAuth Documentation](https://developers.google.com/identity/protocols/oauth2)

---

**Last Updated**: March 2026
