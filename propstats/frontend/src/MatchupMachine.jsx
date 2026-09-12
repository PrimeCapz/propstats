import React, { useState, useEffect, useCallback } from 'react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ── Constants ──────────────────────────────────────────────────────────────────
const PITCH_COLORS = {
  FF:'#ef4444', SI:'#f97316', FC:'#f59e0b', SL:'#3b82f6',
  ST:'#8b5cf6', SV:'#8b5cf6', CU:'#06b6d4', KC:'#06b6d4',
  CH:'#10b981', FS:'#22d3ee', FO:'#22d3ee', KN:'#94a3b8',
};

const GRADE_STYLES = {
  'A+': { bg:'bg-yellow-500/20', border:'border-yellow-500', text:'text-yellow-400' },
  'A':  { bg:'bg-green-500/20',  border:'border-green-500',  text:'text-green-400'  },
  'A-': { bg:'bg-green-500/15',  border:'border-green-600',  text:'text-green-500'  },
  'B+': { bg:'bg-blue-500/20',   border:'border-blue-500',   text:'text-blue-400'   },
  'B':  { bg:'bg-blue-500/15',   border:'border-blue-600',   text:'text-blue-500'   },
  'C':  { bg:'bg-zinc-700/40',   border:'border-zinc-600',   text:'text-zinc-300'   },
  'D':  { bg:'bg-red-500/10',    border:'border-red-700',    text:'text-red-500'    },
  'F':  { bg:'bg-red-500/20',    border:'border-red-500',    text:'text-red-400'    },
};

// ── Small reusable components ──────────────────────────────────────────────────

function Spinner() {
  return (
    <div className="flex items-center justify-center gap-2 py-8 text-zinc-400">
      <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      <span className="text-sm">Loading Statcast data…</span>
    </div>
  );
}

function StatBadge({ label, value, sub, colorClass = 'text-white' }) {
  return (
    <div className="flex flex-col items-center bg-zinc-900/60 rounded-xl px-4 py-3 min-w-[80px]">
      <span className={`text-xl font-black ${colorClass}`}>{value ?? '—'}</span>
      <span className="text-[10px] text-zinc-500 uppercase tracking-wide mt-0.5">{label}</span>
      {sub && <span className="text-[9px] text-zinc-600 mt-0.5">{sub}</span>}
    </div>
  );
}

function UsageBar({ pct, color }) {
  return (
    <div className="w-full bg-zinc-800 rounded-full h-1.5 mt-1">
      <div className="h-1.5 rounded-full transition-all duration-500"
           style={{ width: `${Math.min(pct, 100)}%`, background: color }} />
    </div>
  );
}

function GradeBadge({ grade }) {
  const s = GRADE_STYLES[grade] || GRADE_STYLES['C'];
  return (
    <div className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border ${s.bg} ${s.border}`}>
      <span className={`text-2xl font-black ${s.text}`}>{grade}</span>
      <span className="text-xs text-zinc-400">Matchup<br/>Grade</span>
    </div>
  );
}

// ── Arsenal Table ─────────────────────────────────────────────────────────────

function ArsenalTable({ arsenal }) {
  if (!arsenal?.length) return <p className="text-zinc-500 text-sm">No arsenal data.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-zinc-500 border-b border-zinc-800">
            <th className="text-left py-2 pr-3">Pitch</th>
            <th className="text-right py-2 px-2">Usage</th>
            <th className="text-right py-2 px-2">Velo</th>
            <th className="text-right py-2 px-2">Spin</th>
            <th className="text-right py-2 px-2">Whiff%</th>
            <th className="text-right py-2 px-2">CSW%</th>
            <th className="text-right py-2 px-2">Zone%</th>
            <th className="text-right py-2 px-2">wOBA</th>
            <th className="text-right py-2 pl-2">Move</th>
          </tr>
        </thead>
        <tbody>
          {arsenal.map((a) => (
            <tr key={a.pitch_type} className="border-b border-zinc-800/40 hover:bg-zinc-800/20">
              <td className="py-2 pr-3">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ background: PITCH_COLORS[a.pitch_type] || '#94a3b8' }} />
                  <div>
                    <div className="font-semibold text-white">{a.pitch_name}</div>
                    <UsageBar pct={a.pct} color={PITCH_COLORS[a.pitch_type] || '#94a3b8'} />
                  </div>
                </div>
              </td>
              <td className="text-right py-2 px-2 font-bold text-zinc-200">{a.pct?.toFixed(1)}%</td>
              <td className="text-right py-2 px-2 text-zinc-300">{a.velo?.toFixed(1)}</td>
              <td className="text-right py-2 px-2 text-zinc-400">{a.spin ? a.spin.toLocaleString() : '—'}</td>
              <td className="text-right py-2 px-2">
                <span className={a.whiff_pct >= 30 ? 'text-green-400 font-bold' : a.whiff_pct >= 22 ? 'text-yellow-400' : 'text-zinc-300'}>
                  {a.whiff_pct?.toFixed(1)}%
                </span>
              </td>
              <td className="text-right py-2 px-2">
                <span className={a.csw_pct >= 32 ? 'text-green-400 font-bold' : 'text-zinc-300'}>
                  {a.csw_pct?.toFixed(1)}%
                </span>
              </td>
              <td className="text-right py-2 px-2 text-zinc-400">{a.zone_pct?.toFixed(1)}%</td>
              <td className="text-right py-2 px-2">
                {a.woba != null ? (
                  <span className={a.woba >= 0.38 ? 'text-red-400 font-bold' : a.woba <= 0.22 ? 'text-green-400 font-bold' : 'text-zinc-300'}>
                    .{String(Math.round(a.woba * 1000)).padStart(3, '0')}
                  </span>
                ) : '—'}
              </td>
              <td className="text-right py-2 pl-2 text-zinc-500 text-[10px]">
                {a.pfx_x != null ? `H:${a.pfx_x > 0 ? '+' : ''}${a.pfx_x?.toFixed(0)}" V:${a.pfx_z > 0 ? '+' : ''}${a.pfx_z?.toFixed(0)}"` : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Batter vs Pitch Table ─────────────────────────────────────────────────────

function BatterVsPitchTable({ data, batterName }) {
  if (!data?.length) return <p className="text-zinc-500 text-sm">No split data available.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-zinc-500 border-b border-zinc-800">
            <th className="text-left py-2 pr-3">Pitch</th>
            <th className="text-right py-2 px-2">Opp%</th>
            <th className="text-right py-2 px-2">PA</th>
            <th className="text-right py-2 px-2">BA</th>
            <th className="text-right py-2 px-2">wOBA</th>
            <th className="text-right py-2 px-2">Whiff%</th>
            <th className="text-right py-2 px-2">Chase%</th>
            <th className="text-left py-2 pl-2">Read</th>
          </tr>
        </thead>
        <tbody>
          {data.map((b) => {
            const read = !b.pa
              ? { label: 'No data', color: 'text-zinc-600' }
              : b.woba >= 0.400 ? { label: '🔥 Crushes it', color: 'text-red-400' }
              : b.woba >= 0.340 ? { label: '✅ Hits well', color: 'text-yellow-400' }
              : b.woba <= 0.200 ? { label: '❄️ Dominated', color: 'text-blue-400' }
              : b.woba <= 0.270 ? { label: '⬇️ Struggles', color: 'text-blue-300' }
              : { label: '🟡 Neutral', color: 'text-zinc-400' };
            return (
              <tr key={b.pitch_type} className="border-b border-zinc-800/40 hover:bg-zinc-800/20">
                <td className="py-2 pr-3">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ background: PITCH_COLORS[b.pitch_type] || '#94a3b8' }} />
                    <span className="font-medium text-white">{b.pitch_name}</span>
                  </div>
                </td>
                <td className="text-right py-2 px-2 text-zinc-400">{b.pct?.toFixed(0)}%</td>
                <td className="text-right py-2 px-2 text-zinc-400">{b.pa || '—'}</td>
                <td className="text-right py-2 px-2">
                  {b.ba != null ? (
                    <span className={b.ba >= 0.320 ? 'text-red-400 font-bold' : b.ba <= 0.180 ? 'text-green-400' : 'text-zinc-300'}>
                      .{String(Math.round(b.ba * 1000)).padStart(3, '0')}
                    </span>
                  ) : '—'}
                </td>
                <td className="text-right py-2 px-2">
                  {b.woba != null ? (
                    <span className={b.woba >= 0.380 ? 'text-red-400 font-bold' : b.woba <= 0.220 ? 'text-green-400 font-bold' : 'text-zinc-300'}>
                      .{String(Math.round(b.woba * 1000)).padStart(3, '0')}
                    </span>
                  ) : '—'}
                </td>
                <td className="text-right py-2 px-2">
                  {b.whiff_pct != null ? (
                    <span className={b.whiff_pct >= 38 ? 'text-green-400 font-bold' : b.whiff_pct <= 12 ? 'text-red-400' : 'text-zinc-300'}>
                      {b.whiff_pct?.toFixed(1)}%
                    </span>
                  ) : '—'}
                </td>
                <td className="text-right py-2 px-2">
                  {b.chase_pct != null ? (
                    <span className={b.chase_pct >= 36 ? 'text-green-400 font-bold' : 'text-zinc-300'}>
                      {b.chase_pct?.toFixed(1)}%
                    </span>
                  ) : '—'}
                </td>
                <td className={`text-left py-2 pl-2 font-medium ${read.color}`}>{read.label}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-[10px] text-zinc-600 mt-2">
        Based on {batterName}'s season Statcast data vs same pitch type.
        wOBA green = pitcher wins, red = batter wins.
      </p>
    </div>
  );
}

// ── Heatmap Panel ─────────────────────────────────────────────────────────────

function HeatmapPanel({ pitcherId, batterHand, title }) {
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(false);
  const src = `${API}/baseball/pitcher/${pitcherId}/zone-heatmap?batter_hand=${batterHand}&days_back=60`;

  return (
    <div>
      <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wide mb-2">{title}</h4>
      <div className="relative bg-zinc-900 rounded-xl overflow-hidden">
        {loading && !error && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
        {error && (
          <div className="h-40 flex items-center justify-center text-zinc-500 text-sm">
            Zone data unavailable
          </div>
        )}
        <img
          src={src}
          alt="Pitch zone heatmap"
          className={`w-full rounded-xl transition-opacity duration-300 ${loading ? 'opacity-0' : 'opacity-100'}`}
          style={{ minHeight: loading ? '160px' : 'auto' }}
          onLoad={() => setLoading(false)}
          onError={() => { setLoading(false); setError(true); }}
        />
      </div>
    </div>
  );
}

function BatterHotZonePanel({ batterId, pitcherHand }) {
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(false);
  const src = `${API}/baseball/batter/${batterId}/hot-zones?pitcher_hand=${pitcherHand}&days_back=60`;

  return (
    <div>
      <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wide mb-2">
        Batter Hot Zones vs {pitcherHand === 'L' ? 'LHP' : 'RHP'}
      </h4>
      <div className="relative bg-zinc-900 rounded-xl overflow-hidden">
        {loading && !error && (
          <div className="absolute inset-0 flex items-center justify-center h-40">
            <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
        {error && (
          <div className="h-40 flex items-center justify-center text-zinc-500 text-sm">
            Hot zone data unavailable
          </div>
        )}
        <img
          src={src}
          alt="Batter hot zones"
          className={`w-full rounded-xl transition-opacity duration-300 ${loading ? 'opacity-0' : 'opacity-100'}`}
          style={{ minHeight: loading ? '160px' : 'auto' }}
          onLoad={() => setLoading(false)}
          onError={() => { setLoading(false); setError(true); }}
        />
      </div>
    </div>
  );
}

// ── H2H History ───────────────────────────────────────────────────────────────

function H2HBadge({ h2h }) {
  if (!h2h || !h2h.pa) return null;
  return (
    <div className="bg-zinc-900/70 border border-zinc-700 rounded-xl px-4 py-3 flex items-center gap-6 text-sm">
      <div className="text-zinc-400 text-xs font-bold uppercase tracking-wide">H2H History</div>
      <div className="flex gap-4">
        <span className="text-zinc-300">{h2h.pa} PA</span>
        <span>{h2h.hits} H</span>
        <span className={h2h.hr > 0 ? 'text-red-400 font-bold' : 'text-zinc-500'}>{h2h.hr} HR</span>
        <span className={h2h.k > 0 ? 'text-blue-400' : 'text-zinc-500'}>{h2h.k} K</span>
        {h2h.ba != null && (
          <span className={h2h.ba >= 0.300 ? 'text-yellow-400 font-bold' : 'text-zinc-400'}>
            .{String(Math.round(h2h.ba * 1000)).padStart(3, '0')} AVG
          </span>
        )}
      </div>
      {h2h.pa < 10 && <span className="text-xs text-zinc-600 italic">(small sample)</span>}
    </div>
  );
}

// ── Pitcher Summary Stats Bar ─────────────────────────────────────────────────

function PitcherSummaryBar({ summary }) {
  if (!summary) return null;
  return (
    <div className="flex flex-wrap gap-2 mb-4">
      <StatBadge label="Pitches" value={summary.total_pitches} />
      <StatBadge label="Whiff%" value={`${summary.whiff_pct}%`}
        colorClass={summary.whiff_pct >= 28 ? 'text-green-400' : summary.whiff_pct <= 18 ? 'text-red-400' : 'text-white'} />
      <StatBadge label="CSW%" value={`${summary.csw_pct}%`}
        colorClass={summary.csw_pct >= 32 ? 'text-green-400' : 'text-white'} />
      <StatBadge label="Zone%" value={`${summary.zone_pct}%`} />
      <StatBadge label="HR Allow" value={summary.hr_allowed}
        colorClass={summary.hr_allowed >= 10 ? 'text-red-400' : 'text-white'} />
      {summary.woba_against != null && (
        <StatBadge label="wOBA vs"
          value={`.${String(Math.round(summary.woba_against * 1000)).padStart(3,'0')}`}
          colorClass={summary.woba_against >= 0.350 ? 'text-red-400' : summary.woba_against <= 0.270 ? 'text-green-400' : 'text-white'} />
      )}
      <StatBadge label="Top Pitch" value={summary.primary_pitch?.split(' ')[0]} sub={`${summary.fb_velo?.toFixed(0)} mph`} />
    </div>
  );
}

// ── Main MatchupMachine Component ─────────────────────────────────────────────

export default function MatchupMachine() {
  const [games,       setGames]       = useState([]);
  const [selectedPk,  setSelectedPk]  = useState(null);
  const [gameMeta,    setGameMeta]    = useState(null);
  const [selectedP,   setSelectedP]   = useState(null);   // {id, name, hand}
  const [selectedB,   setSelectedB]   = useState(null);   // {id, name, hand}
  const [matchup,     setMatchup]     = useState(null);
  const [loadingGame, setLoadingGame] = useState(false);
  const [loadingMU,   setLoadingMU]   = useState(false);
  const [activeTab,   setActiveTab]   = useState('arsenal'); // arsenal | zones | vs-pitch | h2h
  const [batterHand,  setBatterHand]  = useState('R');

  // Fetch today's games
  useEffect(() => {
    fetch(`${API}/baseball/games`)
      .then(r => r.json())
      .then(data => {
        const g = Array.isArray(data) ? data : (data.games || []);
        setGames(g);
        if (g.length) setSelectedPk(g[0].game_pk);
      })
      .catch(() => setGames([]));
  }, []);

  // Load game matchup meta when game changes
  useEffect(() => {
    if (!selectedPk) return;
    setLoadingGame(true);
    setGameMeta(null);
    setSelectedP(null);
    setSelectedB(null);
    setMatchup(null);
    fetch(`${API}/baseball/game/${selectedPk}/matchup-machine`)
      .then(r => r.json())
      .then(data => {
        setGameMeta(data);
        // Auto-select away pitcher vs home leadoff
        if (data.away_pitcher?.id) {
          setSelectedP(data.away_pitcher);
          setBatterHand(data.home_batters?.[0]?.hand || 'R');
        }
        if (data.home_batters?.[0]?.id) setSelectedB(data.home_batters[0]);
      })
      .catch(() => setGameMeta(null))
      .finally(() => setLoadingGame(false));
  }, [selectedPk]);

  // Load matchup data when pitcher + batter selected
  useEffect(() => {
    if (!selectedP?.id || !selectedB?.id) return;
    setLoadingMU(true);
    setMatchup(null);
    fetch(`${API}/baseball/matchup/${selectedP.id}/${selectedB.id}?days_back=60`)
      .then(r => r.json())
      .then(data => setMatchup(data))
      .catch(() => setMatchup(null))
      .finally(() => setLoadingMU(false));
  }, [selectedP, selectedB]);

  // Switch pitcher side
  const selectPitcher = (side) => {
    if (!gameMeta) return;
    const p = side === 'away' ? gameMeta.away_pitcher : gameMeta.home_pitcher;
    const batters = side === 'away' ? gameMeta.home_batters : gameMeta.away_batters;
    setSelectedP(p);
    setSelectedB(batters?.[0] || null);
    setBatterHand(batters?.[0]?.hand || 'R');
  };

  const currentBatters = gameMeta
    ? (selectedP?.id === gameMeta.away_pitcher?.id ? gameMeta.home_batters : gameMeta.away_batters)
    : [];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-black text-white tracking-tight">⚾ Matchup Machine</h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            Statcast pitch analysis — zone heatmaps, arsenal breakdown, batter vs pitch type
          </p>
        </div>
      </div>

      {/* Game Picker */}
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-2xl p-4">
        <label className="block text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-2">
          Select Game
        </label>
        <div className="flex flex-wrap gap-2">
          {games.map(g => {
            const label = `${g.away?.team_abbr || g.away_abbr || '?'} @ ${g.home?.team_abbr || g.home_abbr || '?'}`;
            return (
              <button
                key={g.game_pk}
                onClick={() => setSelectedPk(g.game_pk)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                  selectedPk === g.game_pk
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                    : 'bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700'
                }`}
              >
                {label}
              </button>
            );
          })}
          {!games.length && (
            <p className="text-zinc-600 text-sm">No games loaded. Check API connection.</p>
          )}
        </div>
      </div>

      {loadingGame && <Spinner />}

      {gameMeta && !loadingGame && (
        <>
          {/* Pitcher + Batter selectors */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Pitcher panel */}
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-2xl p-4">
              <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-3">
                Select Pitcher
              </div>
              <div className="flex gap-2 mb-4">
                {['away','home'].map(side => {
                  const p = side === 'away' ? gameMeta.away_pitcher : gameMeta.home_pitcher;
                  const t = side === 'away' ? gameMeta.away_team : gameMeta.home_team;
                  const active = selectedP?.id === p?.id;
                  return (
                    <button
                      key={side}
                      onClick={() => selectPitcher(side)}
                      disabled={!p?.id}
                      className={`flex-1 flex flex-col items-start px-4 py-3 rounded-xl border transition-all ${
                        active
                          ? 'bg-blue-600/20 border-blue-500 text-white'
                          : 'bg-zinc-800/50 border-zinc-700 text-zinc-400 hover:border-zinc-500'
                      } ${!p?.id ? 'opacity-40 cursor-not-allowed' : ''}`}
                    >
                      <span className="text-[10px] text-zinc-500 uppercase">{side} — {t?.abbr || ''}</span>
                      <span className="font-bold text-sm mt-0.5">{p?.name || 'TBD'}</span>
                      <div className="flex gap-2 mt-1 text-[10px]">
                        <span className="text-zinc-500">ERA {p?.era}</span>
                        <span className="text-zinc-500">HR/9 {p?.hr9}</span>
                        <span className={`font-bold ${p?.hand === 'L' ? 'text-blue-400' : 'text-orange-400'}`}>
                          {p?.hand === 'L' ? 'LHP' : 'RHP'}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Batter lineup */}
              <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-2">
                Select Batter ({currentBatters?.length || 0} in lineup)
              </div>
              <div className="grid grid-cols-3 gap-1.5 max-h-52 overflow-y-auto pr-1">
                {currentBatters?.map((b, i) => {
                  const active = selectedB?.id === b.id;
                  const gradeColor = { 'A+':'text-yellow-400','A':'text-green-400','A-':'text-green-500','B+':'text-blue-400','B':'text-blue-500' }[b.grade] || 'text-zinc-500';
                  return (
                    <button
                      key={b.id || i}
                      onClick={() => { setSelectedB(b); setBatterHand(b.hand || 'R'); }}
                      disabled={!b.id}
                      className={`flex flex-col items-start px-2.5 py-2 rounded-lg border text-left transition-all ${
                        active
                          ? 'bg-purple-600/20 border-purple-500'
                          : 'bg-zinc-800/40 border-zinc-700/50 hover:border-zinc-600'
                      }`}
                    >
                      <span className="text-[9px] text-zinc-500">#{i+1} · {b.hand || 'R'}</span>
                      <span className="text-[11px] font-semibold text-white leading-tight mt-0.5">
                        {b.name?.split(' ').slice(-1)[0]}
                      </span>
                      <span className={`text-[9px] font-bold mt-0.5 ${gradeColor}`}>{b.grade}</span>
                    </button>
                  );
                })}
              </div>

              {gameMeta.lineup_status === 'projected' && (
                <p className="text-[10px] text-yellow-500/70 mt-2 italic">
                  ⚠ Projected lineup (last game proxy — not confirmed)
                </p>
              )}
            </div>

            {/* Matchup summary card */}
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-2xl p-4 flex flex-col">
              <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-3">
                Matchup Overview
              </div>
              {!selectedP || !selectedB ? (
                <div className="flex-1 flex items-center justify-center text-zinc-600 text-sm">
                  Select a pitcher and batter to see the breakdown
                </div>
              ) : loadingMU ? (
                <Spinner />
              ) : matchup ? (
                <div className="flex flex-col gap-4 flex-1">
                  {/* Names */}
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs text-zinc-500">Pitcher</div>
                      <div className="font-bold text-white">{selectedP.name}</div>
                      <div className="text-[10px] text-zinc-500">
                        {selectedP.hand === 'L' ? 'LHP' : 'RHP'} · {matchup.pitcher_pitches} pitches sampled
                      </div>
                    </div>
                    <div className="text-2xl text-zinc-600 font-black">vs</div>
                    <div className="text-right">
                      <div className="text-xs text-zinc-500">Batter</div>
                      <div className="font-bold text-white">{selectedB.name}</div>
                      <div className="text-[10px] text-zinc-500">
                        {selectedB.hand || 'R'}HB · {matchup.batter_pitches} pitches sampled
                      </div>
                    </div>
                  </div>

                  {/* Grade + edge note */}
                  <div className="flex items-center gap-4">
                    <GradeBadge grade={matchup.grade} />
                    <div className="text-sm text-zinc-300 leading-snug flex-1">
                      {matchup.edge_note}
                    </div>
                  </div>

                  {/* H2H */}
                  <H2HBadge h2h={matchup.h2h} />

                  {/* Quick wOBA insight */}
                  {matchup.batter_vs_pitch?.[0] && (
                    <div className="bg-zinc-800/60 rounded-xl p-3 text-xs text-zinc-400">
                      <span className="font-bold text-white">{selectedB.name?.split(' ').slice(-1)[0]}</span>
                      {' '}primary weakness:{' '}
                      {matchup.batter_vs_pitch.filter(b => b.whiff_pct >= 30 && b.pa >= 8).map(b =>
                        <span key={b.pitch_type} className="text-blue-400 font-bold"> {b.pitch_name} ({b.whiff_pct?.toFixed(0)}% K)</span>
                      )}
                      {matchup.batter_vs_pitch.filter(b => b.whiff_pct >= 30 && b.pa >= 8).length === 0 &&
                        <span className="text-zinc-600"> no clear weakness found in sample</span>}
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center text-zinc-600 text-sm">
                  Could not load matchup data
                </div>
              )}
            </div>
          </div>

          {/* Detail tabs */}
          {matchup && (
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-2xl overflow-hidden">
              {/* Tab bar */}
              <div className="flex border-b border-zinc-800">
                {[
                  { id: 'arsenal',   label: '📊 Arsenal' },
                  { id: 'zones',     label: '🎯 Zone Heatmaps' },
                  { id: 'vs-pitch',  label: '🏏 Batter vs Pitch' },
                  { id: 'h2h',       label: '📋 Full Summary' },
                ].map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex-1 px-3 py-3 text-xs font-semibold transition-all border-b-2 ${
                      activeTab === tab.id
                        ? 'border-blue-500 text-blue-400 bg-blue-500/5'
                        : 'border-transparent text-zinc-500 hover:text-zinc-300'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              <div className="p-5">
                {/* Arsenal tab */}
                {activeTab === 'arsenal' && (
                  <div className="space-y-4">
                    <PitcherSummaryBar summary={matchup.pitcher_summary} />
                    <h3 className="text-sm font-bold text-zinc-300">
                      {selectedP?.name} — Pitch Arsenal
                      <span className="ml-2 text-xs font-normal text-zinc-500">
                        (last 60 days · {matchup.pitcher_pitches} pitches)
                      </span>
                    </h3>
                    <ArsenalTable arsenal={matchup.arsenal} />
                  </div>
                )}

                {/* Zone heatmaps tab */}
                {activeTab === 'zones' && (
                  <div className="space-y-4">
                    <div className="flex items-center gap-3 mb-4">
                      <span className="text-xs text-zinc-500">Show vs:</span>
                      {['R','L'].map(h => (
                        <button key={h} onClick={() => setBatterHand(h)}
                          className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                            batterHand === h ? 'bg-blue-600 text-white' : 'bg-zinc-800 text-zinc-400'
                          }`}>
                          {h === 'R' ? 'RHB' : 'LHB'}
                        </button>
                      ))}
                      <span className="text-[10px] text-zinc-600 ml-2">
                        Hotter color = more pitches thrown to that zone
                      </span>
                    </div>

                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                      <div>
                        <HeatmapPanel
                          pitcherId={selectedP?.id}
                          batterHand={batterHand}
                          title={`${selectedP?.name} — Pitch Locations vs ${batterHand}HB`}
                        />
                      </div>
                      <div>
                        <BatterHotZonePanel
                          batterId={selectedB?.id}
                          pitcherHand={selectedP?.hand || 'R'}
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Batter vs pitch type tab */}
                {activeTab === 'vs-pitch' && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-zinc-300">
                      {selectedB?.name} vs {selectedP?.name}'s Arsenal
                      <span className="ml-2 text-xs font-normal text-zinc-500">
                        (season Statcast, split by pitch type)
                      </span>
                    </h3>
                    <BatterVsPitchTable
                      data={matchup.batter_vs_pitch}
                      batterName={selectedB?.name || ''}
                    />
                  </div>
                )}

                {/* Full summary tab */}
                {activeTab === 'h2h' && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      {/* Pitcher card */}
                      <div className="bg-zinc-800/40 rounded-xl p-4">
                        <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide mb-3">
                          {selectedP?.name}
                        </div>
                        <div className="space-y-2 text-sm">
                          {matchup.arsenal?.slice(0,4).map(a => (
                            <div key={a.pitch_type} className="flex items-center gap-2">
                              <span className="w-2 h-2 rounded-full"
                                    style={{ background: PITCH_COLORS[a.pitch_type] || '#94a3b8' }} />
                              <span className="text-zinc-300 flex-1">{a.pitch_name}</span>
                              <span className="text-zinc-400 text-xs">{a.pct?.toFixed(0)}%</span>
                              <span className="text-zinc-500 text-xs">{a.velo?.toFixed(1)} mph</span>
                              <span className={`text-xs font-bold ${a.whiff_pct >= 28 ? 'text-green-400' : 'text-zinc-400'}`}>
                                W:{a.whiff_pct?.toFixed(0)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Batter card */}
                      <div className="bg-zinc-800/40 rounded-xl p-4">
                        <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide mb-3">
                          {selectedB?.name}
                        </div>
                        <div className="space-y-2 text-sm">
                          {matchup.batter_vs_pitch?.slice(0,4).map(b => (
                            <div key={b.pitch_type} className="flex items-center gap-2">
                              <span className="w-2 h-2 rounded-full"
                                    style={{ background: PITCH_COLORS[b.pitch_type] || '#94a3b8' }} />
                              <span className="text-zinc-300 flex-1">{b.pitch_name}</span>
                              {b.woba != null ? (
                                <span className={`text-xs font-bold ${b.woba >= 0.38 ? 'text-red-400' : b.woba <= 0.22 ? 'text-green-400' : 'text-zinc-300'}`}>
                                  wOBA .{String(Math.round(b.woba*1000)).padStart(3,'0')}
                                </span>
                              ) : <span className="text-xs text-zinc-600">no data</span>}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Full grade breakdown */}
                    <div className="bg-zinc-800/30 rounded-xl p-4 flex items-center gap-6">
                      <GradeBadge grade={matchup.grade} />
                      <div className="space-y-1 text-sm text-zinc-400 flex-1">
                        <div className="font-bold text-white">{matchup.edge_note}</div>
                        <div className="text-xs">
                          Sample: {matchup.pitcher_pitches} pitcher pitches · {matchup.batter_pitches} batter pitches · last 60 days
                        </div>
                        {matchup.h2h?.pa > 0 && (
                          <div className="text-xs text-yellow-400/80">
                            H2H: {matchup.h2h.pa} PA, {matchup.h2h.hits} H, {matchup.h2h.hr} HR, {matchup.h2h.k} K
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
