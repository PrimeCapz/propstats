# Quick Start Guide

## 1. Install Dependencies
```bash
npm install
```

## 2. Configure Environment
```bash
cp .env.local.example .env.local
```

Edit `.env.local` and set:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 3. Start Backend (in another terminal)
```bash
cd ../backend
python main.py
```

## 4. Start Frontend
```bash
npm run dev
```

## 5. Open Browser
Visit [http://localhost:3000](http://localhost:3000)

## Features to Try

1. **Search Players**: Type "lebron" or "curry" in the search box
2. **View Stats**: Select a stat type (Points, Rebounds, Assists, etc.)
3. **Set Line**: Enter a betting line to see hit rates
4. **Check Hit Rates**: See L5, L10, L20, Season performance
5. **View Game Logs**: Scroll down to see recent games
6. **Upgrade Modal**: Click "Upgrade to Pro" to see monetization UI

## Troubleshooting

**"Error searching players"**
- Make sure backend is running on port 8000
- Check NEXT_PUBLIC_API_URL in .env.local

**"Module not found"**
- Run `npm install` again
- Delete `node_modules` and `.next`, then reinstall

**Backend not starting**
- Run `pip install -r requirements.txt` in backend folder
- Make sure Python 3.8+ is installed

## Next Steps

- Set up Supabase for user authentication
- Add Stripe for payment processing
- Deploy to Vercel
- Customize the UI colors and branding

Enjoy building! 🚀
