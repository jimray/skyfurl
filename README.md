# SKYFURL

A Slack app that automatically unfurls links from Bluesky (and related) with rich content.

## Features

* **Automatic unfurls**: Paste a link from Bluesky (or Blacksky) and it automatically expands with rich content
* **Video embeds**: Play videos natively right in Slack

## Installation and Setup

### Prerequisites

* [Slack CLI](https://docs.slack.dev/tools/slack-cli/)

```bash
curl -fsSL https://downloads.slack-edge.com/slack-cli/install.sh | bash
```

* Python 3.8+

### Install

Use the Slack CLI to install the app as a template

```bash
slack create --template https://tangled.org/jimray/skyfurl.git
```

Setup Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

TODO: make this work with `uv`

### Configuration

#### Adding more domains

By default, SKYFURL will unfurl links from Bluesky and Blacksky. To add other microblogging services (e.g. Eurosky or Northsky), include the domains in the `manifest.yaml` file under the `unfurl_domains` param.

## Deployment to Railway

This guide walks you through deploying SKYFURL to Railway.

### Prerequisites

- A Railway account (https://railway.app)
- Your Slack app configured at https://api.slack.com/apps
- Git repository connected to Railway

### Step 1: Create a New Project on Railway

1. Go to https://railway.app/new
2. Select "Deploy from GitHub repo"
3. Choose this repository
4. Railway will automatically detect it as a Python app

### Step 2: Configure Environment Variables

In your Railway project settings, add these environment variables:

#### Required Variables:

```
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here
APP_URL=https://your-app.up.railway.app
PORT=3000
```

#### Where to find these values:

1. **SLACK_BOT_TOKEN**:
   - Go to https://api.slack.com/apps → Your App
   - Navigate to "OAuth & Permissions"
   - Copy "Bot User OAuth Token" (starts with `xoxb-`)

2. **SLACK_SIGNING_SECRET**:
   - Go to https://api.slack.com/apps → Your App
   - Navigate to "Basic Information" → "App Credentials"
   - Copy "Signing Secret"

3. **APP_URL**:
   - After Railway generates your deployment URL (e.g., `your-app.up.railway.app`)
   - Set this to `https://your-app.up.railway.app` (include https://)
   - You can update this after the first deployment

4. **PORT**:
   - Set to `3000` (or leave unset to use Railway's default)

### Step 3: Update Slack App Configuration

After your Railway app is deployed, update your Slack app settings:

#### 3.1 Add Request URL

1. Go to https://api.slack.com/apps → Your App
2. Navigate to "Event Subscriptions"
3. Set Request URL to: `https://your-app.up.railway.app/slack/events`
4. Wait for Slack to verify the URL (should show green checkmark)

#### 3.2 Add Unfurl Domain

For video embeds to work in Slack:

1. Go to "App Manifest" in your Slack app settings
2. Add your Railway domain to `unfurl_domains`:
   ```json
   "unfurl_domains": [
     "bsky.app",
     "blacksky.community",
     "your-app.up.railway.app"
   ]
   ```
3. Save the manifest

#### 3.3 Disable Socket Mode

Since you're deploying with HTTP endpoints:

1. Navigate to "Socket Mode" in your Slack app settings
2. Toggle it OFF (it's only for local development)

### Step 4: Install the App

1. Go to "Install App" in your Slack app settings
2. Click "Reinstall to Workspace" (or "Install to Workspace" if first time)
3. Authorize the app

### Step 5: Test the Deployment

1. Post a Bluesky link in any Slack channel where the app is installed
   - Example: https://bsky.app/profile/bsky.app/post/3l47mye63hc2v
2. The app should unfurl the link with author information and text
3. If the post has a video, it will show "🎬 Processing video... ⏳" initially
4. After processing completes (may take 30-60 seconds), the video player should appear

### Troubleshooting

#### Check Logs

View Railway logs to debug issues:
```bash
railway logs
```

#### Common Issues

1. **"Event not verified"**:
   - Check that `SLACK_SIGNING_SECRET` is correct
   - Ensure Request URL is set correctly

2. **Videos not processing**:
   - Verify `APP_URL` is set correctly with https://
   - Check Railway logs for ffmpeg errors
   - Ensure your Railway domain is in `unfurl_domains`

3. **App not responding**:
   - Check that PORT is set (or unset to use Railway's default)
   - Verify `SLACK_BOT_TOKEN` is valid
   - Check Railway deployment status

#### Redeploy

If you make changes:
```bash
git push
```

Railway will automatically redeploy on push to main branch.

### Monitoring

- **Railway Dashboard**: Monitor deployment status, logs, and metrics
- **Slack App Dashboard**: View event delivery and errors at https://api.slack.com/apps → Your App → Event Subscriptions

### Costs

- Railway offers a free tier with 500 hours/month
- Video processing and storage may require upgrading for heavy usage
- Monitor your usage in the Railway dashboard

### Next Steps

- Consider adding persistent storage for processed videos (Railway Volumes)
- Set up a custom domain instead of Railway's default
- Add error monitoring (Sentry, etc.)
- Implement video cleanup/expiry for old videos
