# PropStats Frontend - Next.js

Modern NBA props research application built with Next.js, Tailwind CSS, and Supabase.

## Features

- 🔍 **Player Search** - Search any active NBA player with autocomplete
- 📊 **Hit Rate Analysis** - L5, L10, L20, Season splits with over/under tracking
- 📈 **Game Logs** - Detailed game-by-game breakdown with visual indicators
- 🎯 **Smart Recommendations** - AI-powered over/under suggestions
- 💳 **Monetization Ready** - Stripe integration placeholder for subscriptions
- 🎨 **Modern UI** - Dark theme with glassmorphism and gradient accents

## Tech Stack

- **Framework:** Next.js 15 with App Router
- **Styling:** Tailwind CSS
- **Icons:** Lucide React
- **Database:** Supabase (optional, for user auth & subscriptions)
- **Backend:** FastAPI (in `/backend` directory)

## Getting Started

### Prerequisites

- Node.js 18+ installed
- Backend API running (see `/backend` README)

### Installation

1. Install dependencies:
```bash
npm install
```

2. Create `.env.local` file:
```bash
cp .env.local.example .env.local
```

3. Update environment variables:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=your-project-url.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

### Development

Run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production Build

```bash
npm run build
npm start
```

## Deployment

### Vercel (Recommended)

1. Push your code to GitHub
2. Go to [Vercel](https://vercel.com) and import your repo
3. Set the root directory to `frontend`
4. Add environment variables
5. Deploy!

### Netlify

1. Go to [Netlify](https://netlify.com)
2. Import your repo, set base directory to `frontend`
3. Build command: `npm run build`
4. Publish directory: `.next`
5. Add environment variables

## Monetization Setup

### Stripe Integration

1. Install Stripe:
```bash
npm install @stripe/stripe-js stripe
```

2. Add Stripe keys to `.env.local`
3. Create API routes for checkout and webhooks

### Ad Integration (Alternative)

For ad-based monetization, integrate Google AdSense or Carbon Ads.

## License

MIT License - feel free to use for personal or commercial projects.

---

Built with ⚡ by leveraging the vibecoding wave
