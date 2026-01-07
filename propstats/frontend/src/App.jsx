import React, { useState, useEffect, useRef } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const generateMockGames = (stat, line) => {
  const bases = { points: 24, rebounds: 7, assists: 6, threes: 2.5, steals: 1.2, blocks: 0.8, pra: 37 };
  const variance = { points: 10, rebounds: 4, assists: 4, threes: 2, steals: 1, blocks: 1, pra: 12 };
  const base = bases[stat] || 24;
  const v = variance[stat] || 8;
  const teams = ['BOS','MIA','LAL','GSW','PHX','DEN','MIL','PHI','DAL','NYK','BKN','ATL','CLE','SAC','MIN'];
  const games = [];
  for (let i = 0; i < 20; i++) {
    const d = new Date(); d.setDate(d.getDate() - (i * 2 + Math.floor(Math.random() * 2)));
    const value = Math.max(0, Math.round(base + (Math.random() - 0.5) * v * 2));
    games.push({ date: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }), opponent: teams[Math.floor(Math.random() * teams.length)], value, is_home: Math.random() > 0.5, minutes: Math.round(28 + Math.random() * 12), hit: value > line });
  }
  return games;
};

const STAT_OPTIONS = [
  { value: 'points', label: 'PTS' }, { value: 'rebounds', label: 'REB' }, { value: 'assists', label: 'AST' },
  { value: 'threes', label: '3PM' }, { value: 'pra', label: 'PRA' }, { value: 'steals', label: 'STL' }, { value: 'blocks', label: 'BLK' }
];

const COMMON_LINES = { points: [15.5, 19.5, 24.5, 29.5], rebounds: [4.5, 6.5, 8.5, 10.5], assists: [4.5, 6.5, 8.5], threes: [1.5, 2.5, 3.5], steals: [0.5, 1.5], blocks: [0.5, 1.5], pra: [25.5, 30.5, 35.5, 40.5] };

const TRENDING_PLAYERS = [
  { id: '1629029', name: 'Luka Doncic', team: 'DAL', position: 'G' },
  { id: '203507', name: 'Giannis Antetokounmpo', team: 'MIL', position: 'F' },
  { id: '1628983', name: 'Shai Gilgeous-Alexander', team: 'OKC', position: 'G' },
  { id: '203999', name: 'Nikola Jokic', team: 'DEN', position: 'C' },
  { id: '1628369', name: 'Jayson Tatum', team: 'BOS', position: 'F' },
  { id: '201142', name: 'Kevin Durant', team: 'PHX', position: 'F' },
  { id: '203954', name: 'Joel Embiid', team: 'PHI', position: 'C' },
  { id: '1630162', name: 'Anthony Edwards', team: 'MIN', position: 'G' }
];

const getHeadshot = (id) => `https://cdn.nba.com/headshots/nba/latest/1040x760/${id}.png`;
const TEAM_COLORS = { ATL:'#E03A3E',BOS:'#007A33',BKN:'#000',CHA:'#1D1160',CHI:'#CE1141',CLE:'#860038',DAL:'#00538C',DEN:'#0E2240',DET:'#C8102E',GSW:'#1D428A',HOU:'#CE1141',IND:'#002D62',LAC:'#C8102E',LAL:'#552583',MEM:'#5D76A9',MIA:'#98002E',MIL:'#00471B',MIN:'#0C2340',NOP:'#0C2340',NYK:'#006BB6',OKC:'#007AC1',ORL:'#0077C0',PHI:'#006BB6',PHX:'#1D1160',POR:'#E03A3E',SAC:'#5A2D81',SAS:'#C4CED4',TOR:'#CE1141',UTA:'#002B5C',WAS:'#002B5C',FA:'#666' };

function BarChart({ games, line, stat }) {
  if (!games.length) return null;
  const maxValue = Math.max(...games.map(g => g.value), line * 1.3);
  const linePercent = (line / maxValue) * 100;
  return (
    <div className="relative">
      <div className="absolute left-0 right-0 border-t-2 border-dashed border-yellow-400/70 z-10" style={{ bottom: `${linePercent}%` }}>
        <span className="absolute right-0 -top-5 text-xs text-yellow-400 font-bold bg-zinc-900 px-1 rounded">{line}</span>
      </div>
      <div className="flex items-end gap-1 h-36">
        {games.slice(0, 15).reverse().map((game, i) => {
          const height = Math.max((game.value / maxValue) * 100, 3);
          return (
            <div key={i} className="flex-1 group relative">
              <div className="absolute bottom-full mb-2 hidden group-hover:block z-20">
                <div className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs whitespace-nowrap">
                  <div className="font-bold">{game.value} {STAT_OPTIONS.find(s => s.value === stat)?.label}</div>
                  <div className="text-zinc-400">{game.is_home ? 'vs' : '@'} {game.opponent}</div>
                </div>
              </div>
              <div className={`w-full rounded-t ${game.hit ? 'bg-gradient-to-t from-emerald-600 to-emerald-400' : 'bg-gradient-to-t from-red-600 to-red-400'}`} style={{ height: `${height}%` }} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function HitRateBox({ label, hits, total, highlight }) {
  const pct = total > 0 ? Math.round((hits / total) * 100) : 0;
  const color = pct >= 70 ? 'emerald' : pct >= 50 ? 'yellow' : 'red';
  return (
    <div className={`rounded-xl p-4 bg-gradient-to-br from-${color}-500/20 to-${color}-600/5 border border-${color}-500/40 ${highlight ? 'ring-2 ring-white/20' : ''}`}>
      <div className="text-[10px] uppercase tracking-widest text-zinc-500">{label}</div>
      <div className={`text-3xl font-black text-${color}-400`}>{pct}%</div>
      <div className="text-xs text-zinc-500">{hits}/{total}</div>
    </div>
  );
}

function PlayerSearch({ onSelect, onClose }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  useEffect(() => { inputRef.current?.focus(); }, []);
  useEffect(() => {
    if (query.length < 2) { setResults([]); return; }
    const t = setTimeout(async () => {
      setLoading(true);
      try { const r = await fetch(`${API_URL}/players/search?q=${encodeURIComponent(query)}`); const d = await r.json(); setResults(d.players || []); }
      catch { setResults(TRENDING_PLAYERS.filter(p => p.name.toLowerCase().includes(query.toLowerCase()))); }
      finally { setLoading(false); }
    }, 300);
    return () => clearTimeout(t);
  }, [query]);
  return (
    <div className="fixed inset-0 bg-black/90 z-50 flex items-start justify-center pt-20 px-4" onClick={onClose}>
      <div className="w-full max-w-xl" onClick={e => e.stopPropagation()}>
        <input ref={inputRef} type="text" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search player..." className="w-full px-5 py-4 bg-zinc-900 border border-zinc-700 rounded-2xl text-white text-lg focus:outline-none" />
        {results.length > 0 && (
          <div className="mt-2 bg-zinc-900 border border-zinc-800 rounded-2xl max-h-80 overflow-y-auto">
            {results.map(p => (
              <button key={p.id} onClick={() => onSelect(p)} className="w-full px-4 py-3 flex items-center gap-3 hover:bg-zinc-800 text-left border-b border-zinc-800 last:border-0">
                <img src={getHeadshot(p.id)} className="w-10 h-10 rounded-full bg-zinc-800" onError={e => e.target.style.display='none'} />
                <div><div className="font-semibold">{p.name}</div><div className="text-sm text-zinc-500">{p.team}</div></div>
              </button>
            ))}
          </div>
        )}
        {query.length < 2 && (
          <div className="mt-4 grid grid-cols-2 gap-2">
            {TRENDING_PLAYERS.slice(0, 6).map(p => (
              <button key={p.id} onClick={() => onSelect(p)} className="flex items-center gap-2 p-3 bg-zinc-900 border border-zinc-800 rounded-xl hover:bg-zinc-800 text-left">
                <img src={getHeadshot(p.id)} className="w-8 h-8 rounded-full bg-zinc-700" onError={e => e.target.style.display='none'} />
                <span className="text-sm font-medium">{p.name.split(' ').pop()}</span>
              </button>
            ))}
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
    setLoading(true);
    fetch(`${API_URL}/players/${player.id}/analysis?stat=${stat}&line=${line}`)
      .then(r => r.json()).then(d => { if (d.games?.length) { setGames(d.games.map(g => ({...g, hit: g.value > line}))); setUseMock(false); } else throw 0; })
      .catch(() => { setGames(generateMockGames(stat, line)); setUseMock(true); })
      .finally(() => setLoading(false));
  }, [player, stat]);

  useEffect(() => { if (games.length) setGames(g => g.map(x => ({...x, hit: x.value > line}))); }, [line]);

  const calc = list => { const h = list.filter(g => g.hit).length; return { hits: h, total: list.length, pct: list.length ? Math.round(h/list.length*100) : 0 }; };
  const l5 = calc(games.slice(0,5)), l10 = calc(games.slice(0,10)), l20 = calc(games.slice(0,20));
  const avg = games.length ? (games.reduce((a,g) => a+g.value, 0)/games.length).toFixed(1) : 0;

  // Calculate verdict based on L10 hit rate and average performance vs line
  const calculateVerdict = (hitRate, average, targetLine) => {
    // Strong confidence thresholds: 70%+ over or 30%- under
    if (hitRate >= 70 && average > targetLine) {
      return { t: 'STRONG OVER', c: 'emerald' };
    }
    if (hitRate <= 30 && average < targetLine) {
      return { t: 'STRONG UNDER', c: 'red' };
    }

    // Moderate confidence thresholds: 55%+ over or 45%- under
    if (hitRate >= 55 && average > targetLine) {
      return { t: 'LEAN OVER', c: 'emerald' };
    }
    if (hitRate <= 45 && average < targetLine) {
      return { t: 'LEAN UNDER', c: 'red' };
    }

    // No clear trend
    return { t: 'TOSS UP', c: 'zinc' };
  };

  const verdict = calculateVerdict(l10.pct, avg, line);
  const teamColor = player ? TEAM_COLORS[player.team] || '#666' : '#666';

  return (
    <div className="min-h-screen bg-[#09090b] text-white">
      <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 py-3 flex justify-between items-center">
          <div className="flex items-center gap-2"><div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center font-black">P</div><span className="font-bold">PropStats</span></div>
          <button onClick={() => setShowSearch(true)} className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-xl text-sm">🔍 Search</button>
        </div>
      </header>
      {showSearch && <PlayerSearch onSelect={p => { setPlayer(p); setShowSearch(false); setLine(COMMON_LINES[stat]?.[1] || 19.5); }} onClose={() => setShowSearch(false)} />}
      <main className="max-w-6xl mx-auto px-4 py-6">
        {!player ? (
          <div className="text-center py-20">
            <h2 className="text-2xl font-bold mb-4">Search any NBA player</h2>
            <div className="flex flex-wrap justify-center gap-2">
              {TRENDING_PLAYERS.slice(0,4).map(p => (
                <button key={p.id} onClick={() => { setPlayer(p); setLine(COMMON_LINES[stat]?.[1] || 19.5); }} className="flex items-center gap-2 px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-xl hover:border-zinc-600">
                  <img src={getHeadshot(p.id)} className="w-8 h-8 rounded-full bg-zinc-700" onError={e => e.target.style.display='none'} />
                  <span>{p.name}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="rounded-2xl p-5" style={{background:`linear-gradient(135deg,${teamColor}15,transparent)`}}>
              <div className="flex flex-col sm:flex-row items-center gap-4">
                <img src={getHeadshot(player.id)} className="w-20 h-20 rounded-xl bg-zinc-800" onError={e => e.target.style.display='none'} />
                <div className="flex-1 text-center sm:text-left">
                  <h1 className="text-2xl font-black">{player.name}</h1>
                  <p className="text-zinc-400">{player.team} • {player.position}</p>
                </div>
                <div className={`bg-${verdict.c}-500/20 text-${verdict.c}-400 px-4 py-2 rounded-xl text-center`}>
                  <div className="text-xs opacity-70">Verdict</div>
                  <div className="font-black">{verdict.t}</div>
                </div>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex gap-1 bg-zinc-900 p-1 rounded-xl">
                {STAT_OPTIONS.map(s => <button key={s.value} onClick={() => { setStat(s.value); setLine(COMMON_LINES[s.value]?.[1] || 19.5); }} className={`px-3 py-2 rounded-lg text-sm font-semibold ${stat===s.value?'bg-emerald-500':'text-zinc-400 hover:text-white'}`}>{s.label}</button>)}
              </div>
              <div className="flex items-center gap-2 ml-auto">
                <button onClick={() => setLine(l => Math.max(0.5,l-0.5))} className="w-8 h-8 bg-zinc-800 rounded-lg">−</button>
                <input type="number" value={line} onChange={e => setLine(parseFloat(e.target.value)||0)} step="0.5" className="w-16 bg-zinc-900 border border-zinc-700 rounded-lg text-center font-bold py-1" />
                <button onClick={() => setLine(l => l+0.5)} className="w-8 h-8 bg-zinc-800 rounded-lg">+</button>
              </div>
            </div>
            <div className="flex gap-2">{(COMMON_LINES[stat]||[]).map(l => <button key={l} onClick={() => setLine(l)} className={`px-3 py-1 rounded-lg text-sm ${line===l?'bg-yellow-500/20 text-yellow-400':'bg-zinc-800 text-zinc-500'}`}>{l}</button>)}</div>
            {loading ? <div className="text-center py-20"><div className="w-10 h-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto" /></div> : (
              <div className="grid lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 space-y-6">
                  <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-5">
                    <div className="flex justify-between mb-4"><h3 className="font-semibold">Last 15 Games</h3><div className="flex gap-3 text-xs"><span className="flex items-center gap-1"><span className="w-3 h-3 bg-emerald-500 rounded" />Over</span><span className="flex items-center gap-1"><span className="w-3 h-3 bg-red-500 rounded" />Under</span></div></div>
                    <BarChart games={games} line={line} stat={stat} />
                    <div className="mt-4 pt-4 border-t border-zinc-800 flex justify-between">
                      <div><span className="text-zinc-500 text-xs">Avg</span><div className="text-2xl font-bold">{avg}</div></div>
                      <div className="text-right"><span className="text-zinc-500 text-xs">vs Line</span><div className={`text-2xl font-bold ${avg>line?'text-emerald-400':'text-red-400'}`}>{avg>line?'+':''}{(avg-line).toFixed(1)}</div></div>
                    </div>
                  </div>
                  <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl overflow-hidden">
                    <div className="px-5 py-3 border-b border-zinc-800 flex justify-between"><h3 className="font-semibold">Game Log</h3>{useMock && <span className="text-xs text-yellow-500">Demo</span>}</div>
                    <table className="w-full text-sm"><thead><tr className="text-zinc-500 text-xs bg-zinc-900/50"><th className="px-4 py-2 text-left">Date</th><th className="px-3 py-2 text-left">Opp</th><th className="px-3 py-2 text-center">{STAT_OPTIONS.find(s=>s.value===stat)?.label}</th><th className="px-3 py-2 text-center">+/-</th></tr></thead>
                    <tbody>{games.slice(0,10).map((g,i) => <tr key={i} className="border-t border-zinc-800/50"><td className="px-4 py-2 text-zinc-400">{g.date}</td><td className="px-3 py-2">{g.is_home?'vs':'@'} {g.opponent}</td><td className="px-3 py-2 text-center"><span className={`font-bold ${g.hit?'text-emerald-400':'text-red-400'}`}>{g.value}</span></td><td className="px-3 py-2 text-center"><span className={`px-2 py-0.5 rounded text-xs ${g.hit?'bg-emerald-500/20 text-emerald-400':'bg-red-500/20 text-red-400'}`}>{g.hit?'+':''}{(g.value-line).toFixed(1)}</span></td></tr>)}</tbody></table>
                  </div>
                </div>
                <div className="space-y-4">
                  <h3 className="font-semibold">Hit Rates</h3>
                  <HitRateBox label="Last 5" hits={l5.hits} total={l5.total} highlight />
                  <HitRateBox label="Last 10" hits={l10.hits} total={l10.total} />
                  <HitRateBox label="Last 20" hits={l20.hits} total={l20.total} />
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-3"><div className="text-[10px] text-zinc-500">HOME</div><div className="text-xl font-bold">{calc(games.filter(g=>g.is_home)).pct}%</div></div>
                    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-3"><div className="text-[10px] text-zinc-500">AWAY</div><div className="text-xl font-bold">{calc(games.filter(g=>!g.is_home)).pct}%</div></div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
      <footer className="border-t border-zinc-800 mt-12 py-6 text-center text-zinc-600 text-sm">PropStats © 2025</footer>
    </div>
  );
}
