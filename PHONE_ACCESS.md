# 📱 Access PropStats Mission Control on Your Phone

## Quick Start - 3 Steps

### 1️⃣ Start the App
```bash
streamlit run app.py
```

### 2️⃣ Generate QR Code
```bash
python generate_qr.py
```

Choose option **1** for local WiFi access.

### 3️⃣ Scan & Access
- Open your phone camera
- Point at `propstats_qr.png`
- Tap the notification to open

---

## 🌐 Access Methods

### Method A: Local WiFi (Fast & Private)
**Best for**: Testing, personal use, no internet needed

✅ **Pros**:
- Instant access
- No deployment needed
- Works offline
- Free

⚠️ **Requirements**:
- Phone and computer on same WiFi
- Streamlit running on your computer
- Port 8501 not blocked by firewall

**Setup**:
```bash
# 1. Run the app
streamlit run app.py

# 2. Generate QR code
python generate_qr.py
# Choose option 1

# 3. Scan QR code with phone
```

---

### Method B: Streamlit Cloud (Public Access)
**Best for**: Sharing with others, permanent deployment

✅ **Pros**:
- Access from anywhere
- No need to keep computer running
- Free tier available
- Custom subdomain

**Setup**:
1. Go to https://share.streamlit.io
2. Sign in with GitHub
3. Click "New app"
4. Configure:
   - **Repository**: `PrimeCapz/propstats`
   - **Branch**: `claude/nba-stats-dashboard-xIcAi`
   - **Main file path**: `app.py`
5. Click "Deploy"
6. Wait 2-3 minutes
7. Copy your app URL (e.g., `https://propstats-xyz.streamlit.app`)
8. Run: `python generate_qr.py`
9. Choose option 2 and paste your URL

---

## 🔧 Troubleshooting

### QR Code Not Working?

**Check 1: Is Streamlit running?**
```bash
streamlit run app.py
```
You should see: `You can now view your Streamlit app in your browser.`

**Check 2: Same WiFi network?**
- Phone WiFi: Settings → WiFi → Check network name
- Computer WiFi: Must match phone's network

**Check 3: Firewall blocking?**
```bash
# Windows
netsh advfirewall firewall add rule name="Streamlit" dir=in action=allow protocol=TCP localport=8501

# Mac
# System Preferences → Security & Privacy → Firewall → Firewall Options
# Allow Streamlit
```

**Check 4: Wrong IP address?**
```bash
# Find your local IP
# Windows
ipconfig
# Look for "IPv4 Address" under your WiFi adapter

# Mac/Linux
ifconfig
# Look for "inet" under en0 or wlan0
```

Then regenerate QR code with option 3 (custom URL):
```
http://YOUR_IP_ADDRESS:8501
```

---

## 🎯 Best Practices

### For Development/Testing
1. Use **Method A** (Local WiFi)
2. Keep Streamlit running in terminal
3. Make changes, Streamlit auto-reloads
4. Test on phone immediately

### For Production/Sharing
1. Use **Method B** (Streamlit Cloud)
2. Push changes to GitHub
3. Streamlit Cloud auto-deploys
4. Share QR code or URL with others

---

## 🚀 Mobile Optimization Tips

The app is already mobile-responsive, but for best experience:

1. **Use in landscape mode** for player deep dive
2. **Tap the logo** to return to slate view
3. **Swipe gestures** work on charts
4. **Pinch to zoom** on stats grids

---

## 📊 What You'll See

### Mission Control Interface:
- ✨ Animated holographic header
- 🎮 Liquid glass cards with shimmer effects
- 📡 HUD-style tactical displays
- 🌈 Neon glow effects throughout
- 📱 Touch-optimized buttons

### Three Navigation Layers:
1. **Today's Slate** → View all 8 games
2. **Matchup Board** → Team comparison + player selection
3. **Player Deep Dive** → Full analytics with PropScore

---

## 🔐 Security Note

**Local WiFi Access** (Method A):
- Only accessible on your local network
- Cannot be accessed from internet
- Safe for testing

**Streamlit Cloud** (Method B):
- Publicly accessible URL
- Anyone with link can access
- Free tier has usage limits
- No sensitive data in this app

---

## 💡 Pro Tips

1. **Bookmark on phone**: After opening, add to home screen for app-like experience
2. **Dark mode friendly**: App already uses dark theme, perfect for night viewing
3. **Offline mode**: Local WiFi works without internet
4. **Multiple devices**: Generate one QR code, share with whole household

---

## 📸 Sample QR Code

Your QR code (`propstats_qr.png`) has:
- ✅ Neon green color (#00FFA3)
- ✅ Black background
- ✅ High contrast for easy scanning
- ✅ Optimized for phone cameras

---

**Need help?** Check the terminal output when running `generate_qr.py` for your specific local IP and port.
