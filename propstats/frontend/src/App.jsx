import React, { useState, useEffect, useRef } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Fallback mock data when API is loading
const generateMockGames = (stat, line) => {
  const bases = { points: 24, rebounds: 7, assists: 6, threes: 2.5, steals: 1.2, blocks: 0.8, pra: 37 };
  const variance = { points: 10, rebounds: 4, assists: 4, threes: 2, steals: 1, blocks: 1, pra: 12 };
  const base = bases[stat] || 24;
  const v = variance[stat] || 8;
  const teams = ['BOS','MIA','LAL','GSW','PHX','DEN','MIL','PHI','DAL','NYK','BKN','ATL','CLE','SAC','MIN'];
  const games = [];
  const today = new Date();
  
  for (let i = 0; i < 20; i++) {
    const d = new Date(today);
    d.setDate(d.getDate() - (i * 2 + Math.floor(Math.random() * 2)));
    const value = Math.max(0, Math.round(base + (Math.random() - 0.5) * v * 2));
    games.push({
      date: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      opponent: teams[Math.floor(Math.random() * teams.length)],
      value,
      is_home: Math.random() > 0.5,
      result: Math.random() > 0.45 ? 'W' : 'L',
      minutes: Math.round(28 + Math.random() * 12),
      hit: value > line
    });
  }
  return games;
};

const STAT_OPTIONS = [
  { value: 'points', label: 'PTS', full: 'Points' },
  { value: 'rebounds', label: 'REB', full: 'Rebounds' },
  { value: 'assists', label: 'AST', full: 'Assists' },
  { value: 'threes', label: '3PM', full: '3-Pointers Made' },
  { value: 'pra', label: 'P+R+A', full: 'Pts + Reb + Ast' },
  { value: 'steals', label: 'STL', full: 'Steals' },
  { value: 'blocks', label: 'BLK', full: 'Blocks' },
];

const COMMON_LINES = {
  points: [15.5, 19.5, 24.5, 29.5, 34.5],
  rebounds: [4.5, 6.5, 8.5, 10.5, 12.5],
  assists: [4.5, 6.5, 8.5, 10.5],
  threes: [1.5, 2.5, 3.5, 4.5, 5.5],
  steals: [0.5, 1.5, 2.5],
  blocks: [0.5, 1.5, 2.5],
  pra: [25.5, 30.5, 35.5, 40.5, 45.5],
};

const TRENDING_PLAYERS = [
  { id: '1629029', name: 'Luka Doncic', team: 'DAL', position: 'G' },
  { id: '203507', name: 'Giannis Antetokounmpo', team: 'MIL', position: 'F' },
  { id: '1628983', name: 'Shai Gilgeous-Alexander', team: 'OKC', position: 'G' },
  { id: '203999', name: 'Nikola Jokic', team: 'DEN', position: 'C' },
  { id: '1628369', name: 'Jayson Tatum', team: 'BOS', position: 'F' },
  { id: '201142', name: 'Kevin Durant', team: 'PHX', position: 'F' },
];

const getHeadshot = (playerId) => 
  `https://cdn.nba.com/headshots/nba/latest/1040x760/${playerId}.png`;

const TEAM_COLORS = {
  ATL: '#E03A3E', BOS: '#007A33', BKN: '#000000', CHA: '#1D1160',
  CHI: '#CE1141', CLE: '#860038', DAL: '#00538C', DEN: '#0E2240',
  DET: '#C8102E', GSW: '#1D428A', HOU: '#CE1141', IND: '#002D62',
  LAC: '#C8102E', LAL: '#552583', MEM: '#5D76A9', MIA: '#98002E',
  MIL: '#00471B', MIN: '#0C2340', NOP: '#0C2340', NYK: '#006BB6',
  OKC: '#007AC1', ORL: '#0077C0', PHI: '#006BB6', PHX: '#1D1160',
  POR: '#E03A3E', SAC: '#5A2D81', SAS: '#C4CED4', TOR: '#CE1141',
  UTA: '#002B5C', WAS: '#002B5C', FA: '#666666'
};

function BarChart({ games, line, stat }) {
  const maxValue = Math.max(...games.map(g => g.value), line * 1.3);
  const linePercent = (line / maxValue) * 100;
  
  return (
    <div className="relative">
      <div 
        className="absolute left-0 right-0 border-t-2 border-dashed border-yellow-400/60 z-10"
        style={{ bottom: `${linePercent}%` }}
      >
        <span className="absolute -right-1 -top-3 text-[10px] text-yellow-400 font-bold bg-zinc-900 px-1 rounded">
          {line}
        </span>
      </div>
      
      <div className="flex items-end gap-[3px] h-32">
        {games.slice(0, 15).reverse().map((game, i) => {
          const height = (game.value / maxValue) * 100;
          const hit = game.value > line;
          
          return (
            <div key={i} className="flex-1 flex flex-col items-center group relative">
              <div className="absolute bottom-full mb-2 hidden group-hover:block z-20">
                <div className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-xl">
                  <div className="font-bold text-white">{game.value} {STAT_OPTIONS.find(s => s.value === stat)?.label}</div>
                  <div className="text-zinc-400">{game.is_home ? 'vs' : '@'} {game.opponent}</div>
                  <div className="text-zinc-500">{game.date}</div>
                </div>
              </div>
              
              <div 
                className={`w-full rounded-t transition-all duration-200 group-hover:opacity-80 ${
                  hit ? 'bg-gradient-to-t from-emerald-600 to-emerald-400' : 'bg-gradient-to-t from-red-600 to-red-400'
                }`}
                style={{ height: `${height}%`, minHeight: '4px' }}
              />
              
              {i % 3 === 0 && (
                <span className="text-[8px] text-zinc-600 mt-1">
                  {game.date.split(' ')[0]}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function HitRateBox({ label, hits, total, highlight }) {
  const pct = total > 0 ? Math.round((hits / total) * 100) : 0;
  const getColor = () => {
    if (pct >= 70) return 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 text-emerald-400';
    if (pct >= 50) return 'from-yellow-500/20 to-yellow-600/10 border-yellow-500/30 text-yellow-400';
    return 'from-red-500/20 to-red-600/10 border-red-500/30 text-red-400';
  };
  
  return (
    <div className={`relative rounded-xl p-4 bg-gradient-to-br border ${getColor()} ${highlight ? 'ring-2 ring-white/20' : ''}`}>
      <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">{label}</div>
      <div className="text-3xl font-black">{pct}%</div>
      <div className="text-xs text-zinc-500">{hits}/{total}</div>
      {highlight && <div className="absolute top-2 right-2 text-[10px] bg-white/10 px-2 py-0.5 rounded-full">KEY</div>}
    </div>
  );
}

function PlayerSearch({ onSelect, onClose }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (query.length < 2) {
      setResults([]);
      return;
    }
    
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_URL}/players/search?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        setResults(data.players || []);
      } catch (err) {
        console.error('Search error:', err);
      } finally {
        setLoading(false);
      }
    }, 300);
    
    return () => clearTimeout(timer);
  }, [query]);

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-start justify-center pt-20 px-4">
      <div className="w-full max-w-xl">
        <div className="relative">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search any NBA player..."
            className="w-full px-6 py-5 bg-zinc-900 border border-zinc-700 rounded-2xl text-white text-xl placeholder-zinc-600 focus:outline-none focus:border-emerald-500/50"
          />
          <button 
            onClick={onClose}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white p-2 text-2xl"
          >
            ×
          </button>
          {loading && (
            <div className="absolute right-14 top-1/2 -translate-y-1/2">
              <div className="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
        </div>
        
        {results.length > 0 && (
          <div className="mt-2 bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden max-h-96 overflow-y-auto">
            {results.map((player) => (
              <button
                key={player.id}
                onClick={() => onSelect(player)}
                className="w-full px-4 py-3 flex items-center gap-4 hover:bg-zinc-800 transition-colors text-left border-b border-zinc-800/50 last:border-0"
              >
                <img 
                  src={getHeadshot(player.id)} 
                  alt={player.name}
                  className="w-12 h-12 rounded-full object-cover bg-zinc-800"
                  onError={(e) => { e.target.style.display = 'none'; }}
                />
                <div className="flex-1">
                  <div className="text-white font-semibold">{player.name}</div>
                  <div className="text-sm text-zinc-500">{player.team} • {player.position}</div>
                </div>
              </button>
            ))}
          </div>
        )}
        
        {query.length < 2 && (
          <div className="mt-4">
            <div className="text-xs text-zinc-600 uppercase tracking-widest mb-3">Trending Players</div>
            <div className="grid grid-cols-2 gap-2">
              {TRENDING_PLAYERS.map((player) => (
                <button
                  key={player.id}
                  onClick={() => onSelect(player)}
                  className="flex items-center gap-3 px-4 py-3 bg-zinc-900/50 border border-zinc-800 rounded-xl hover:bg-zinc-800 transition-colors text-left"
                >
                  <img 
                    src={getHeadshot(player.id)} 
                    alt={player.name}
                    className="w-10 h-10 rounded-full object-cover bg-zinc-800"
                    onError={(e) => { e.target.style.display = 'none'; }}
                  />
                  <div>
                    <div className="text-white font-medium text-sm">{player.name.split(' ').pop()}</div>
                    <div className="text-xs text-zinc-500">{player.team}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [showSearch, setShowSearch] = useState(false);
  const [player, setPlayer] = useState(null);
  const [stat, setStat] = useState('points');
  const [line, setLine] = useState(24.5);
  const [games, setGames] = useState([]);
  const [loading, setLoading] = useState(false);
  const [useMock, setUseMock] = useState(false);

  useEffect(() => {
    if (!player) return;
    
    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await fetch(
          `${API_URL}/players/${player.id}/analysis?stat=${stat}&line=${line}`
        );
        const data = await res.json();
        
        if (data.games && data.games.length > 0) {
          setGames(data.games.map(g => ({
            ...g,
            hit: g.value > line
          })));
          setUseMock(false);
        } else {
          setGames(generateMockGames(stat, line));
          setUseMock(true);
        }
      } catch (err) {
        console.error('Analysis error:', err);
        setGames(generateMockGames(stat, line));
        setUseMock(true);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, [player, stat]);

  useEffect(() => {
    if (games.length > 0) {
      setGames(prev => prev.map(g => ({ ...g, hit: g.value > line })));
    }
  }, [line]);

  const selectPlayer = (p) => {
    setPlayer(p);
    setShowSearch(false);
    setLine(COMMON_LINES[stat]?.[1] || 19.5);
  };

  const calcHitRate = (gamesList) => {
    if (!gamesList.length) return { hits: 0, total: 0, pct: 0 };
    const hits = gamesList.filter(g => g.hit).length;
    return { hits, total: gamesList.length, pct: Math.round((hits / gamesList.length) * 100) };
  };

  const l5 = calcHitRate(games.slice(0, 5));
  const l10 = calcHitRate(games.slice(0, 10));
  const l20 = calcHitRate(games.slice(0, 20));
  const seasonAvg = games.length > 0 
    ? (games.reduce((a, g) => a + g.value, 0) / games.length).toFixed(1)
    : 0;

  const getVerdict = () => {
    if (l10.pct >= 70 && parseFloat(seasonAvg) > line) return { text: 'STRONG OVER', color: 'text-emerald-400', bg: 'bg-emerald-500/20' };
    if (l10.pct >= 55 && parseFloat(seasonAvg) > line) return { text: 'LEAN OVER', color: 'text-emerald-300', bg: 'bg-emerald-500/10' };
    if (l10.pct <= 30 && parseFloat(seasonAvg) < line) return { text: 'STRONG UNDER', color: 'text-red-400', bg: 'bg-red-500/20' };
    if (l10.pct <= 45 && parseFloat(seasonAvg) < line) return { text: 'LEAN UNDER', color: 'text-red-300', bg: 'bg-red-500/10' };
    return { text: 'TOSS UP', color: 'text-zinc-400', bg: 'bg-zinc-500/20' };
  };

  const verdict = getVerdict();
  const teamColor = player ? (TEAM_COLORS[player.team] || '#666') : '#666';

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <header className="border-b border-zinc-800/50 bg-zinc-900/30 backdrop-blur sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center font-black text-sm">P</div>
            <span className="font-bold text-lg hidden sm:block">PropStats</span>
            <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full font-semibold">BETA</span>
          </div>
          <button 
            onClick={() => setShowSearch(true)}
            className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-xl transition-colors"
          >
            <svg className="w-4 h-4 text-zinc-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <span className="text-zinc-400 text-sm hidden sm:block">Search player...</span>
          </button>
        </div>
      </header>

      {showSearch && (
        <PlayerSearch 
          onSelect={selectPlayer} 
          onClose={() => setShowSearch(false)} 
        />
      )}

      <main className="max-w-6xl mx-auto px-4 py-6">
        {!player ? (
          <div className="text-center py-20">
            <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center">
              <svg className="w-8 h-8 text-zinc-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-zinc-300 mb-2">Search for a player</h2>
            <p className="text-zinc-600 mb-8">Research any NBA player's prop history</p>
            
            <div className="flex flex-wrap justify-center gap-3">
              {TRENDING_PLAYERS.slice(0, 4).map((p) => (
                <button
                  key={p.id}
                  onClick={() => selectPlayer(p)}
                  className="flex items-center gap-3 px-5 py-3 bg-zinc-900 border border-zinc-800 rounded-xl hover:border-zinc-600 transition-all"
                >
                  <img 
                    src={getHeadshot(p.id)} 
                    alt={p.name}
                    className="w-10 h-10 rounded-full bg-zinc-800 object-cover"
                    onError={(e) => { e.target.style.display = 'none'; }}
                  />
                  <div className="text-left">
                    <div className="font-semibold">{p.name}</div>
                    <div className="text-xs text-zinc-500">{p.team}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Player Header */}
            <div 
              className="relative rounded-2xl overflow-hidden"
              style={{ background: `linear-gradient(135deg, ${teamColor}22, transparent)` }}
            >
              <div className="absolute inset-0 bg-gradient-to-r from-black/60 to-transparent" />
              <div className="relative flex flex-col sm:flex-row items-center gap-4 sm:gap-6 p-6">
                <img 
                  src={getHeadshot(player.id)} 
                  alt={player.name}
                  className="w-20 h-20 sm:w-24 sm:h-24 rounded-xl object-cover bg-zinc-800 border-2 border-white/10"
                  onError={(e) => { e.target.style.display = 'none'; }}
                />
                <div className="flex-1 text-center sm:text-left">
                  <div className="flex items-center justify-center sm:justify-start gap-3 mb-1">
                    <h1 className="text-2xl sm:text-3xl font-black">{player.name}</h1>
                    <button 
                      onClick={() => setShowSearch(true)}
                      className="text-zinc-500 hover:text-white transition-colors"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                      </svg>
                    </button>
                  </div>
                  <div className="flex items-center justify-center sm:justify-start gap-4 text-zinc-400">
                    <span className="font-semibold" style={{ color: teamColor }}>{player.team}</span>
                    <span>•</span>
                    <span>{player.position || 'N/A'}</span>
                  </div>
                </div>
                
                <div className={`${verdict.bg} ${verdict.color} px-6 py-3 rounded-xl text-center`}>
                  <div className="text-xs opacity-70 mb-1">VERDICT</div>
                  <div className="text-xl font-black">{verdict.text}</div>
                </div>
              </div>
            </div>

            {/* Stat Tabs + Line Selector */}
            <div className="flex flex-col sm:flex-row sm:items-center gap-4">
              <div className="flex gap-1 bg-zinc-900 p-1 rounded-xl overflow-x-auto">
                {STAT_OPTIONS.map((s) => (
                  <button
                    key={s.value}
                    onClick={() => {
                      setStat(s.value);
                      setLine(COMMON_LINES[s.value]?.[1] || 19.5);
                    }}
                    className={`px-3 sm:px-4 py-2 rounded-lg text-sm font-semibold transition-all whitespace-nowrap ${
                      stat === s.value 
                        ? 'bg-emerald-500 text-white' 
                        : 'text-zinc-400 hover:text-white'
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-3 sm:ml-auto">
                <span className="text-xs text-zinc-500 uppercase tracking-wider">Line</span>
                <div className="flex items-center gap-1">
                  <button 
                    onClick={() => setLine(l => Math.max(0.5, l - 0.5))}
                    className="w-8 h-8 flex items-center justify-center bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors text-lg"
                  >
                    −
                  </button>
                  <input
                    type="number"
                    value={line}
                    onChange={(e) => setLine(parseFloat(e.target.value) || 0)}
                    step="0.5"
                    className="w-20 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-center text-xl font-bold focus:outline-none focus:border-emerald-500"
                  />
                  <button 
                    onClick={() => setLine(l => l + 0.5)}
                    className="w-8 h-8 flex items-center justify-center bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors text-lg"
                  >
                    +
                  </button>
                </div>
              </div>
            </div>

            {/* Quick Lines */}
            <div className="flex flex-wrap gap-2">
              {(COMMON_LINES[stat] || []).map((l) => (
                <button
                  key={l}
                  onClick={() => setLine(l)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    line === l 
                      ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' 
                      : 'bg-zinc-800/50 text-zinc-400 hover:bg-zinc-800'
                  }`}
                >
                  {l}
                </button>
              ))}
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-20">
                <div className="text-center">
                  <div className="w-10 h-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                  <p className="text-zinc-500 text-sm">Loading game data...</p>
                </div>
              </div>
            ) : (
              <div className="grid lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 space-y-6">
                  {/* Bar Chart */}
                  <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-semibold flex items-center gap-2">
                        <span className="text-emerald-400">▎</span>
                        Last 15 Games
                      </h3>
                      <div className="flex items-center gap-4 text-xs">
                        <span className="flex items-center gap-1">
                          <span className="w-3 h-3 bg-emerald-500 rounded-sm"></span> Over
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="w-3 h-3 bg-red-500 rounded-sm"></span> Under
                        </span>
                      </div>
                    </div>
                    <BarChart games={games} line={line} stat={stat} />
                    
                    <div className="mt-4 pt-4 border-t border-zinc-800 flex items-center justify-between">
                      <div>
                        <span className="text-zinc-500 text-sm">Season Average</span>
                        <div className="text-2xl font-bold">{seasonAvg}</div>
                      </div>
                      <div className="text-right">
                        <span className="text-zinc-500 text-sm">vs Line ({line})</span>
                        <div className={`text-lg font-bold ${parseFloat(seasonAvg) > line ? 'text-emerald-400' : 'text-red-400'}`}>
                          {parseFloat(seasonAvg) > line ? '+' : ''}{(parseFloat(seasonAvg) - line).toFixed(1)}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Game Log Table */}
                  <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl overflow-hidden">
                    <div className="px-6 py-4 border-b border-zinc-800">
                      <h3 className="font-semibold">Game Log</h3>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-zinc-500 text-xs uppercase tracking-wider">
                            <th className="px-4 sm:px-6 py-3 text-left">Date</th>
                            <th className="px-4 py-3 text-left">Opp</th>
                            <th className="px-4 py-3 text-center">{STAT_OPTIONS.find(s => s.value === stat)?.label}</th>
                            <th className="px-4 py-3 text-center">Result</th>
                            <th className="px-4 py-3 text-right hidden sm:table-cell">Min</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-800/50">
                          {games.slice(0, 10).map((game, i) => (
                            <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                              <td className="px-4 sm:px-6 py-3 text-zinc-400">{game.date}</td>
                              <td className="px-4 py-3">
                                <span className={game.is_home ? 'text-zinc-300' : 'text-zinc-500'}>
                                  {game.is_home ? 'vs' : '@'} {game.opponent}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-center">
                                <span className={`text-xl font-bold ${game.hit ? 'text-emerald-400' : 'text-red-400'}`}>
                                  {game.value}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-center">
                                <span className={`px-2 sm:px-3 py-1 rounded-full text-xs font-bold ${
                                  game.hit 
                                    ? 'bg-emerald-500/20 text-emerald-400' 
                                    : 'bg-red-500/20 text-red-400'
                                }`}>
                                  {game.hit ? '✓' : '✗'}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-right text-zinc-500 hidden sm:table-cell">{game.minutes}m</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                {/* Right Column - Hit Rates */}
                <div className="space-y-4">
                  <h3 className="font-semibold flex items-center gap-2">
                    <span className="text-emerald-400">▎</span>
                    Hit Rates
                  </h3>
                  
                  <HitRateBox label="Last 5 Games" hits={l5.hits} total={l5.total} highlight />
                  <HitRateBox label="Last 10 Games" hits={l10.hits} total={l10.total} />
                  <HitRateBox label="Last 20 Games" hits={l20.hits} total={l20.total} />
                  
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
                      <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">Home</div>
                      <div className="text-2xl font-bold text-emerald-400">
                        {calcHitRate(games.filter(g => g.is_home)).pct}%
                      </div>
                    </div>
                    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
                      <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">Away</div>
                      <div className="text-2xl font-bold text-zinc-300">
                        {calcHitRate(games.filter(g => !g.is_home)).pct}%
                      </div>
                    </div>
                  </div>

                  {useMock && (
                    <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-4 text-sm">
                      <div className="text-yellow-400 font-semibold mb-1">⚠️ Demo Data</div>
                      <div className="text-yellow-200/70 text-xs">
                        Showing simulated data while real stats load from NBA.com...
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      <footer className="border-t border-zinc-800/50 mt-12 py-6 text-center text-zinc-600 text-sm">
        PropStats © 2025 • Free NBA Props Research
      </footer>
    </div>
  );
}
