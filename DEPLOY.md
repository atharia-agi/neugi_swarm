# Deploy to Vercel

## Quick Deploy

### Option 1: Using Vercel CLI (Recommended)

```bash
# Install Vercel CLI
npm i -g vercel

# Login (will open browser)
vercel login

# Deploy
vercel --prod
```

### Option 2: Using Token (Environment Variable)

```bash
# Set token (don't share!)
export VERCEL_TOKEN="your_new_token_here"

# Deploy
vercel --prod
```

### Option 3: Connect GitHub to Vercel

1. Go to https://vercel.com
2. Sign in / Sign up
3. Click "Add New..." → Project
4. Import your GitHub repository: atharia-agi/neugi_swarm
5. Configure:
   - Framework Preset: Other
   - Build Command: (empty)
   - Output Directory: .
6. Click Deploy!

## After Deploy

- Your site will be at: `https://your-project.vercel.app`
- Connect custom domain (neugi.com) in Vercel Dashboard

## Files for Deployment

- `index.html` - Main landing page
- `vercel.json` - Vercel configuration
