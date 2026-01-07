# 🏀 NBA Props Research - Streamlit MVP Deployment Guide

## 📋 Quick Start

Your NBA Player Prop Research tool is ready to deploy! This guide will help you launch your app on **Streamlit Community Cloud (100% FREE)**.

---

## 🚀 Deployment Steps

### Option 1: Streamlit Community Cloud (Recommended - FREE)

#### 1. Prepare Your Repository

Make sure your GitHub repository contains:
```
/propstats/
├── app.py                    # Main Streamlit application
├── requirements.txt          # Python dependencies
└── STREAMLIT_DEPLOYMENT.md   # This file
```

#### 2. Deploy to Streamlit Cloud

1. **Visit Streamlit Cloud**
   - Go to https://share.streamlit.io/
   - Click "Sign in with GitHub"

2. **Create New App**
   - Click "New app" button
   - Select your repository: `YourUsername/propstats`
   - Branch: `main` (or your working branch)
   - Main file path: `app.py`
   - App URL: Choose a custom URL (e.g., `nba-props-research`)

3. **Advanced Settings (Optional)**
   - Python version: 3.11
   - No secrets needed for basic version

4. **Deploy!**
   - Click "Deploy"
   - Wait 2-3 minutes for initial deployment
   - Your app will be live at: `https://nba-props-research.streamlit.app`

#### 3. Share Your App

Once deployed:
- Share the URL with users
- App auto-updates when you push to GitHub
- Free tier includes unlimited visitors!

---

## 💳 Adding Stripe Payments

### Step 1: Create Stripe Account

1. Go to https://stripe.com
2. Create a free account
3. Complete basic verification

### Step 2: Create Payment Link

1. In Stripe Dashboard:
   - Products → Create Product
   - Name: "NBA Props Premium Access"
   - Price: $5/month (recurring)
   - Click "Save"

2. Create Payment Link:
   - Click "Create payment link"
   - Choose "Subscription"
   - Copy the generated URL

### Step 3: Update Code

In `app.py`, find line ~380 and replace the button:

```python
# Replace this:
if st.button("💳 Unlock Premium Access - $5", ...):
    st.info("...")

# With this:
st.link_button(
    "💳 Unlock Premium Access - $5",
    "https://buy.stripe.com/YOUR_PAYMENT_LINK_ID",
    use_container_width=True,
    type="primary"
)
```

### Step 4: Manage Access Codes

For MVP, manually generate access codes:
1. After user pays, send them a unique code
2. Store codes in Streamlit secrets (see below)
3. Users enter code in sidebar to unlock

**For Production:** Use Stripe webhooks + database for automation

---

## 🔐 Managing Access Codes with Secrets

### Add Secrets to Streamlit Cloud

1. Go to your app settings on Streamlit Cloud
2. Click "Advanced settings"
3. Add secrets in TOML format:

```toml
# .streamlit/secrets.toml
[access_codes]
code1 = "BETS2024"
code2 = "PREMIUM2024"
code3 = "PROPS999"

[stripe]
webhook_secret = "your_stripe_webhook_secret"
```

### Update Code to Use Secrets

```python
import streamlit as st

# In your access code check:
valid_codes = st.secrets["access_codes"].values()
is_premium = access_code in valid_codes
```

---

## 🔌 Upgrading to Real NBA Data

### Option 1: BallDontLie API (Free)

Add to `requirements.txt`:
```
requests>=2.31.0
```

Update `app.py`:
```python
import requests

def fetch_player_stats(player_name, num_games=10):
    # Search player
    search_url = "https://www.balldontlie.io/api/v1/players"
    response = requests.get(search_url, params={"search": player_name})
    player_data = response.json()["data"][0]
    player_id = player_data["id"]

    # Get stats
    stats_url = "https://www.balldontlie.io/api/v1/stats"
    stats_response = requests.get(stats_url, params={
        "player_ids[]": player_id,
        "per_page": num_games,
        "seasons[]": "2024"  # Current season
    })

    return stats_response.json()["data"]
```

**Rate Limits:** 60 requests/minute (free tier)

### Option 2: NBA API (Your Existing Backend)

If you want to use your existing FastAPI backend:

1. Deploy backend to Railway/Render (see main README)
2. Get backend URL: `https://your-backend.railway.app`
3. Update Streamlit app:

```python
import requests

API_URL = "https://your-backend.railway.app"

def fetch_player_analysis(player_id, stat, line):
    response = requests.get(
        f"{API_URL}/players/{player_id}/analysis",
        params={"stat": stat, "line": line}
    )
    return response.json()
```

---

## 📊 Features Overview

### Free Tier
- ✅ Player selection (15+ popular players)
- ✅ Last 5/10/15 game stats
- ✅ Professional bar charts
- ✅ Basic averages and metrics
- ✅ Game-by-game logs

### Premium Tier ($5)
- ✅ Hit rate analysis (multiple lines)
- ✅ Over/Under recommendations
- ✅ Matchup difficulty ratings
- ✅ Advanced metrics (consistency, trends)
- ✅ Defense vs position analysis

---

## 🛠️ Troubleshooting

### App Won't Deploy

**Error: Module not found**
- Check `requirements.txt` has all dependencies
- Make sure file is in root directory

**Error: File not found**
- Verify `app.py` is in root or specify correct path
- Check branch name matches

### App Runs Slow

**Solutions:**
- Use `@st.cache_data` decorator for data loading
- Limit API calls with caching
- Optimize DataFrame operations

Example:
```python
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_player_data(player_name):
    # Your data loading logic
    return data
```

### Premium Access Not Working

- Verify access code matches exactly (case-sensitive)
- Check secrets are properly formatted in Streamlit Cloud
- Clear browser cache and try again

---

## 📈 Usage Analytics

Track your app performance:

1. Go to Streamlit Cloud dashboard
2. Select your app
3. View metrics:
   - Total visitors
   - Active users
   - Resource usage

---

## 🎨 Customization Ideas

### Add More Players
Update `MOCK_PLAYERS` dict in `app.py`:
```python
MOCK_PLAYERS = {
    "Your Player": {"team": "ABC", "position": "G"},
    # ... more players
}
```

### Change Color Scheme
Modify CSS in the `st.markdown()` section:
```css
background: linear-gradient(90deg, #YOUR_COLOR_1, #YOUR_COLOR_2);
```

### Add More Stats
Add to stat_type selectbox:
```python
stat_type = st.sidebar.selectbox(
    "Stat Type",
    options=["Points", "Rebounds", "Assists", "Threes",
             "Blocks", "Steals", "Minutes", "FG%"]  # Add more
)
```

---

## 💰 Monetization Tips

1. **Start Free, Convert Later**
   - Offer 3 free searches per day
   - Show premium value with locked features
   - Clear upgrade CTA

2. **Tiered Pricing**
   - Basic: $5/month (current features)
   - Pro: $15/month (API data, more players)
   - Elite: $30/month (live odds, alerts)

3. **Affiliate Links**
   - Partner with sportsbooks
   - Earn commission on sign-ups
   - Disclose partnerships clearly

---

## 📱 Mobile Optimization

Streamlit is mobile-responsive by default! Test on:
- iPhone Safari
- Android Chrome
- iPad

Looks great on all devices ✅

---

## 🔒 Security Best Practices

1. **Never commit secrets**
   - Use Streamlit Secrets
   - Add `.streamlit/` to `.gitignore`

2. **Validate user inputs**
   - Already handled in selectboxes
   - Sanitize any text inputs

3. **Rate limit API calls**
   - Use caching
   - Implement usage limits

---

## 📞 Support

**Issues with deployment?**
- Streamlit Docs: https://docs.streamlit.io/
- Community Forum: https://discuss.streamlit.io/
- GitHub Issues: https://github.com/streamlit/streamlit/issues

**Issues with Stripe?**
- Stripe Docs: https://stripe.com/docs
- Support: https://support.stripe.com/

---

## 🎉 Next Steps

1. ✅ Deploy to Streamlit Cloud
2. ✅ Test all features
3. ✅ Set up Stripe payments
4. ✅ Share with friends for feedback
5. ✅ Add real NBA data (optional)
6. ✅ Market your app!

---

## 🚀 Launch Checklist

- [ ] App deployed to Streamlit Cloud
- [ ] All features working correctly
- [ ] Mobile view tested
- [ ] Stripe payment link added
- [ ] Access code system working
- [ ] Privacy/disclaimer text added
- [ ] Social media posts prepared
- [ ] Landing page/blog post written

---

**Built with ❤️ | Ship fast, iterate faster!**

*Need help? Open an issue or contact support.*
