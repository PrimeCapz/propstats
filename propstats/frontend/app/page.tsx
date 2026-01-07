'use client';

import { useState } from 'react';
import { Search, TrendingUp, TrendingDown, BarChart3, DollarSign, Sparkles } from 'lucide-react';
import PlayerSearch from '@/components/PlayerSearch';
import StatsAnalysis from '@/components/StatsAnalysis';
import UpgradePrompt from '@/components/UpgradePrompt';

export default function Home() {
  const [selectedPlayer, setSelectedPlayer] = useState<any>(null);
  const [showUpgrade, setShowUpgrade] = useState(false);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-purple-950 to-slate-950">
      {/* Header */}
      <header className="border-b border-white/10 bg-black/20 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl">
                <BarChart3 className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">PropStats</h1>
                <p className="text-xs text-purple-300">NBA Props Research</p>
              </div>
            </div>

            <button
              onClick={() => setShowUpgrade(true)}
              className="px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg font-semibold hover:from-purple-700 hover:to-pink-700 transition-all flex items-center gap-2"
            >
              <Sparkles className="w-4 h-4" />
              Upgrade to Pro
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Hero Section */}
        <div className="text-center mb-12">
          <h2 className="text-4xl sm:text-5xl font-bold text-white mb-4">
            Research NBA Props with{' '}
            <span className="bg-gradient-to-r from-purple-400 to-pink-400 text-transparent bg-clip-text">
              Historical Data
            </span>
          </h2>
          <p className="text-lg text-slate-300 mb-8">
            Analyze player performance, hit rates, and trends to make smarter betting decisions
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-green-500/20 rounded-lg">
                <TrendingUp className="w-5 h-5 text-green-400" />
              </div>
              <h3 className="text-white font-semibold">Hit Rate Analysis</h3>
            </div>
            <p className="text-slate-400 text-sm">
              L5, L10, L20, Season splits with over/under tracking
            </p>
          </div>

          <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-blue-500/20 rounded-lg">
                <BarChart3 className="w-5 h-5 text-blue-400" />
              </div>
              <h3 className="text-white font-semibold">Game Logs</h3>
            </div>
            <p className="text-slate-400 text-sm">
              Detailed game-by-game performance breakdown
            </p>
          </div>

          <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-purple-500/20 rounded-lg">
                <DollarSign className="w-5 h-5 text-purple-400" />
              </div>
              <h3 className="text-white font-semibold">Line Comparison</h3>
            </div>
            <p className="text-slate-400 text-sm">
              Compare any betting line against historical performance
            </p>
          </div>
        </div>

        {/* Search Section */}
        <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl p-8 mb-8">
          <PlayerSearch onPlayerSelect={setSelectedPlayer} />
        </div>

        {/* Analysis Section */}
        {selectedPlayer && (
          <StatsAnalysis player={selectedPlayer} />
        )}
      </main>

      {/* Upgrade Modal */}
      {showUpgrade && (
        <UpgradePrompt onClose={() => setShowUpgrade(false)} />
      )}

      {/* Footer */}
      <footer className="border-t border-white/10 mt-16 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-slate-400 text-sm">
          <p>Built for the sports betting community 🏀</p>
          <p className="mt-2">Data sourced from NBA.com | Free tier: 10 searches/day</p>
        </div>
      </footer>
    </div>
  );
}
