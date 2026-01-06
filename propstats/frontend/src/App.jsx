import React, { useState, useEffect, useCallback } from 'react';
import { Search, TrendingUp, TrendingDown, Minus, ChevronDown, X, Zap, Target, BarChart3, Clock, Star, Lock } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const STAT_OPTIONS = [
  { value: 'points', label: 'Points', icon: '🎯' },
  { value: 'rebounds', label: 'Rebounds', icon: '🏀' },
  { value: 'assists', label: 'Assists', icon: '🎁' },
  { value: 'threes', label: '3PM', icon: '🔥' },
  { value: 'steals', label: 'Steals', icon: '🖐️' },
  { value: 'blocks', label: 'Blocks', icon: '🚫' },
  { value: 'pra', label: 'PRA', icon: '📊' },
];

const COMMON_LINES = {
  points: [15.5, 19.5, 24.5, 29.5],
  rebounds: [4.5, 6.5, 8.5, 10.5],
  assists: [4.5, 6.5, 8.5, 10.5],
  threes: [1.5, 2.5, 3.5, 4.5],
  steals: [0.5, 1.5, 2.5],
  blocks: [0.5, 1.5, 2.5],
  pra: [25.5, 30.5, 35.5, 40.5],
};

function getHitRateColor(pct) {
  if (pct >= 70) return { bg: 'bg-emerald-500/20', text: 'text-emerald-400', border: 'border-emerald-500/30' };
  if (pct >= 50) return { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/30' };
  return { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30' };
}

function TrendIndicator({ current, average }) {
  const diff = current - average;
  const pct = average > 0 ? ((diff / average) * 100).toFixed(0) : 0;
  
  if (Math.abs(diff) < 0.5) {
    return <span className="text-zinc-500 text-xs flex items-center gap-1"><Minus size={12} /> Avg</span>;
  }
  
  if (diff > 0) {
    return <span className="text-emerald-400 text-xs flex items-center gap-1"><TrendingUp size={12} /> +{pct}%</span>;
  }
  
  return <span className="text-red-400 text-xs flex items-center gap-1"><TrendingDown size={12} /> {pct}%</span>;
}

function HitRateCard({ label, data, highlight = false }) {
  const colors = getHitRateColor(data.pct);
  
  return (
    <div className={`relative overflow-hidden rounded-xl p-4 transition-all duration-300 ${
      highlight 
        ? 'bg-gradient-to-br from-violet-600/20 to-fuchsia-600/20 border border-violet-500/30 shadow-lg shadow-violet-500/10' 
        : `${colors.bg} border ${colors.border}`
    }`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider">{label}</span>
        {highlight && <Star size={14} className="text-violet-400" />}
      </div>
      <div className={`text-3xl font-bold ${highlight ? 'text-white' : colors.text}`}>
        {data.pct}%
      </div>
      <div className="text-xs text-zinc-500 mt-1">
        {data.hits}/{data.total} games
      </div>
    </div>
  );
}

function GameLogRow({ game, index }) {
  const colors = game.hit ? getHitRateColor(100) : getHitRateColor(0);
  
  return (
    <div className={`flex items-center gap-4 p-3 rounded-lg transition-all duration-200 hover:bg-white/5 ${
      index === 0 ? 'bg-white/5' : ''
    }`}>
      <div className="w-20 text-xs text-zinc-500">
        {new Date(game.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
      </div>
      <div className="w-16 text-sm">
        <span className={game.is_home ? 'text-emerald-400' : 'text-zinc-400'}>
          {game.is_home ? 'vs' : '@'}
        </span>{' '}
        <span className="text-white font-medium">{game.opponent}</span>
      </div>
      <div className="flex-1 flex items-center gap-3">
        <div className={`text-2xl font-bold ${colors.text}`}>
          {game.value}
        </div>
        <div className={`px-2 py-0.5 rounded text-xs font-medium ${colors.bg} ${colors.text} border ${colors.border}`}>
          {game.hit ? 'HIT' : 'MISS'}
        </div>
      </div>
    </div>
  );
}

function PlayerSearch({ onSelect }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [focused, setFocused] = useState(false);

  const searchPlayers = useCallback(async (q) => {
    if (q.length < 2) {
      setResults([]);
      return;
    }
    
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/players/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      setResults(data.players || []);
    } catch (err) {
      console.error('Search error:', err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => searchPlayers(query), 300);
    return () => clearTimeout(timer);
  }, [query, searchPlayers]);

  return (
    <div className="relative">
      <div className={`relative transition-all duration-300 ${focused ? 'scale-[1.02]' : ''}`}>
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500" size={20} />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 200)}
          placeholder="Search any NBA player..."
          className="w-full pl-12 pr-4 py-4 bg-zinc-900/80 border border-zinc-800 rounded-2xl text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 transition-all duration-300"
        />
        {loading && (
          <div className="absolute right-4 top-1/2 -translate-y-1/2">
            <div className="w-5 h-5 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
      </div>
      
      {results.length > 0 && focused && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden shadow-2xl shadow-black/50 z-50">
          {results.map((player) => (
            <button
              key={player.id}
              onClick={() => {
                onSelect(player);
                setQuery('');
                setResults([]);
              }}
              className="w-full px-4 py-3 flex items-center gap-3 hover:bg-zinc-800 transition-colors text-left"
            >
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-600 flex items-center justify-center text-white font-bold">
                {player.name.charAt(0)}
              </div>
              <div className="flex-1">
                <div className="text-white font-medium">{player.name}</div>
                <div className="text-xs text-zinc-500">{player.team} • {player.position}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function StatSelector({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const selected = STAT_OPTIONS.find(s => s.value === value);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-4 py-3 bg-zinc-900 border border-zinc-800 rounded-xl text-white hover:border-zinc-700 transition-colors"
      >
        <span>{selected?.icon}</span>
        <span>{selected?.label}</span>
        <ChevronDown size={16} className={`text-zinc-500 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      
      {open && (
        <div className="absolute top-full left-0 mt-2 bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-xl z-40 min-w-[140px]">
          {STAT_OPTIONS.map((stat) => (
            <button
              key={stat.value}
              onClick={() => {
                onChange(stat.value);
                setOpen(false);
              }}
              className={`w-full px-4 py-3 flex items-center gap-2 hover:bg-zinc-800 transition-colors text-left ${
                stat.value === value ? 'bg-violet-600/20 text-violet-400' : 'text-white'
              }`}
            >
              <span>{stat.icon}</span>
              <span>{stat.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function LineInput({ value, onChange, stat }) {
  const commonLines = COMMON_LINES[stat] || [];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          step="0.5"
          className="w-24 px-4 py-3 bg-zinc-900 border border-zinc-800 rounded-xl text-white text-center focus:outline-none focus:border-violet-500/50 transition-colors"
        />
        <span className="text-zinc-500 text-sm">line</span>
      </div>
      <div className="flex gap-2 flex-wrap">
        {commonLines.map((line) => (
          <button
            key={line}
            onClick={() => onChange(line)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              value === line 
                ? 'bg-violet-600 text-white' 
                : 'bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700'
            }`}
          >
            {line}
          </button>
        ))}
      </div>
    </div>
  );
}

function UsageTracker({ used, limit }) {
  const pct = Math.min((used / limit) * 100, 100);
  const remaining = Math.max(0, limit - used);
  
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-zinc-500 uppercase tracking-wider">Free Tier Usage</span>
        <span className="text-sm text-zinc-400">{used}/{limit} lookups</span>
      </div>
      <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
        <div 
          className={`h-full transition-all duration-500 ${
            pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-amber-500' : 'bg-emerald-500'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {remaining <= 10 && remaining > 0 && (
        <p className="text-xs text-amber-400 mt-2 flex items-center gap-1">
          <Clock size={12} /> {remaining} lookups remaining today
        </p>
      )}
      {remaining === 0 && (
        <button className="mt-3 w-full py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-lg text-white text-sm font-medium flex items-center justify-center gap-2 hover:opacity-90 transition-opacity">
          <Lock size={14} /> Upgrade to Premium
        </button>
      )}
    </div>
  );
}

export default function App() {
  const [selectedPlayer, setSelectedPlayer] = useState(null);
  const [stat, setStat] = useState('points');
  const [line, setLine] = useState(19.5);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [usage, setUsage] = useState({ used: 0, limit: 50 });

  useEffect(() => {
    if (!selectedPlayer) return;

    const fetchAnalysis = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const res = await fetch(
          `${API_URL}/players/${selectedPlayer.id}/analysis?stat=${stat}&line=${line}`
        );
        
        if (!res.ok) {
          throw new Error('Failed to fetch analysis');
        }
        
        const data = await res.json();
        setAnalysis(data);
        setUsage(prev => ({ ...prev, used: prev.used + 1 }));
      } catch (err) {
        console.error('Analysis error:', err);
        setError('Failed to load player data. The player may not have games this season.');
      } finally {
        setLoading(false);
      }
    };

    const timer = setTimeout(fetchAnalysis, 500);
    return () => clearTimeout(timer);
  }, [selectedPlayer, stat, line]);

  return (
    <div className="min-h-screen bg-black text-white">
      <div className="fixed inset-0 bg-gradient-to-br from-violet-950/30 via-black to-fuchsia-950/20 pointer-events-none" />
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-violet-600/10 blur-[120px] rounded-full pointer-events-none" />
      
      <div className="relative max-w-6xl mx-auto px-4 py-8">
        <header className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-violet-600/20 border border-violet-500/30 rounded-full text-violet-400 text-sm mb-4">
            <Zap size={14} /> 2025-26 NBA Season • Live Data
          </div>
          <h1 className="text-5xl font-bold mb-3 bg-gradient-to-r from-white via-violet-200 to-fuchsia-200 bg-clip-text text-transparent">
            PropStats
          </h1>
          <p className="text-zinc-500 max-w-md mx-auto">
            Research player props with historical hit rates, game logs, and trend analysis
          </p>
        </header>

        <div className="max-w-xl mx-auto mb-8">
          <PlayerSearch onSelect={setSelectedPlayer} />
        </div>

        {selectedPlayer && (
          <div className="mb-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6">
              <div className="flex items-start justify-between mb-6">
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-600 to-fuchsia-600 flex items-center justify-center text-2xl font-bold">
                    {selectedPlayer.name.charAt(0)}
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-white">{selectedPlayer.name}</h2>
                    <p className="text-zinc-500">{selectedPlayer.team} • {selectedPlayer.position}</p>
                  </div>
                </div>
                <button 
                  onClick={() => {
                    setSelectedPlayer(null);
                    setAnalysis(null);
                  }}
                  className="p-2 text-zinc-500 hover:text-white transition-colors"
                >
                  <X size={20} />
                </button>
              </div>

              <div className="flex flex-wrap gap-6 items-start">
                <div>
                  <label className="text-xs text-zinc-500 uppercase tracking-wider mb-2 block">Stat</label>
                  <StatSelector value={stat} onChange={setStat} />
                </div>
                <div>
                  <label className="text-xs text-zinc-500 uppercase tracking-wider mb-2 block">Line</label>
                  <LineInput value={line} onChange={setLine} stat={stat} />
                </div>
              </div>
            </div>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="text-center">
              <div className="w-12 h-12 border-4 border-violet-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-zinc-500">Loading analysis...</p>
            </div>
          </div>
        )}

        {error && !loading && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 text-center">
            {error}
          </div>
        )}

        {analysis && !loading && !error && (
          <div className="grid lg:grid-cols-3 gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="lg:col-span-1 space-y-4">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <Target size={18} className="text-violet-400" /> Hit Rates
              </h3>
              
              <div className="space-y-3">
                <HitRateCard label="Season" data={analysis.hit_rates.season} />
                <HitRateCard label="Last 5" data={analysis.hit_rates.l5} highlight />
                <HitRateCard label="Last 10" data={analysis.hit_rates.l10} />
                <HitRateCard label="Last 20" data={analysis.hit_rates.l20} />
              </div>

              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
                <div className="flex items-center justify-between">
                  <span className="text-zinc-500">Season Average</span>
                  <span className="text-xl font-bold text-white">{analysis.averages?.season || 0}</span>
                </div>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-zinc-500">vs Line ({line})</span>
                  <TrendIndicator current={analysis.averages?.season || 0} average={line} />
                </div>
              </div>

              <UsageTracker used={usage.used} limit={usage.limit} />
            </div>

            <div className="lg:col-span-2">
              <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
                <BarChart3 size={18} className="text-violet-400" /> Game Log
              </h3>
              
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl overflow-hidden">
                <div className="px-4 py-3 border-b border-zinc-800 bg-zinc-900/50">
                  <div className="flex items-center gap-4 text-xs text-zinc-500 uppercase tracking-wider">
                    <span className="w-20">Date</span>
                    <span className="w-16">Opp</span>
                    <span>Result</span>
                  </div>
                </div>
                
                <div className="divide-y divide-zinc-800/50 max-h-[500px] overflow-y-auto">
                  {analysis.games.map((game, i) => (
                    <GameLogRow key={i} game={game} index={i} />
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {!selectedPlayer && (
          <div className="text-center py-20">
            <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center">
              <Search size={32} className="text-zinc-600" />
            </div>
            <h3 className="text-xl font-semibold text-zinc-400 mb-2">Search for a player</h3>
            <p className="text-zinc-600">Enter any NBA player name to see their prop analysis</p>
          </div>
        )}

        <footer className="mt-16 pt-8 border-t border-zinc-800 text-center text-zinc-600 text-sm">
          <p>PropStats © 2026 • 2025-26 NBA Season Data</p>
        </footer>
      </div>
    </div>
  );
}
