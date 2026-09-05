import React, { useState, useEffect, useRef } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ── Helpers ──────────────────────────────────────────────────────────────────

const fmtTime = (iso) => {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZoneName: 'short' });
  } catch { return ''; }
};

const statColor = (val, thresholds, invert = false) => {
  if (val === '-' || val === null || val === undefined) return 'text-zinc-400';
  const n = parseFloat(val);
  if (isNaN(n)) return 'text-zinc-400';
  const [good, avg, bad] = thresholds;
  if (!invert) {
    if (n >= good) return 'text-emerald-400';
    if (n >= avg) return 'text-yellow-400';
    return 'text-red-400';
  } else {
    if (n <= good) return 'text-emerald-400';
    if (n <= avg) return 'text-yellow-400';
    return 'text-red-400';
  }
};

const gradeColor = { 'A+': 'emerald', A: 'emerald', B: 'green', C: 'yellow', D: 'orange', F: 'red', '?': 'zinc' };

// ── Pitch Arsenal Bar ─────────────────────────────────────────────────────────

function PitchBar({ pitch }) {
  const colors = {
    FF: 'from-red-500 to-red-400', SI: 'from-orange-500 to-orange-400',
    FC: 'from-amber-500 to-amber-400', SL: 'from-blue-500 to-blue-400',
    CU: 'from-purple-500 to-purple-400', KC: 'from-violet-500 to-violet-400',
    CH: 'from-emerald-500 to-emerald-400', FS: 'from-teal-500 to-teal-400',
    ST: 'from-sky-500 to-sky-400', KN: 'from-zinc-400 to-zinc-300',
  };
  const color = colors[pitch.pitch_type] || 'from-zinc-500 to-zinc-400';
  return (
    <div className="mb-3">
      <div className="flex justify-between items-center mb-1 text-xs">
        <span className="font-semibold text-white">{pitch.pitch_name}</span>
        <div className="flex gap-3 text-zinc-400">
          <span className="text-white font-bold">{pitch.usage_pct}%</span>
          <span>{pitch.avg_velocity > 0 ? `${pitch.avg_velocity} mph` : ''}</span>
          <span className={pitch.whiff_pct >= 30 ? 'text-emerald-400' : pitch.whiff_pct >= 20 ? 'text-yellow-400' : 'text-zinc-400'}>
            {pitch.whiff_pct > 0 ? `${pitch.whiff_pct}% whiff` : ''}
          </span>
        </div>
      </div>
      <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full bg-gradient-to-r ${color} transition-all`} style={{ width: `${pitch.usage_pct}%` }} />
      </div>
    </div>
  );
}

// ── Weather Card ──────────────────────────────────────────────────────────────

function WeatherCard({ weather }) {
  if (!weather) return null;
  if (!weather.available) return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-4">
      <div className="text-xs text-zinc-500 uppercase tracking-widest mb-1">Weather</div>
      <div className="text-sm text-zinc-400">{weather.note || 'Indoor venue'}</div>
    </div>
  );

  const imp = weather.impact || {};
  const impColor = imp.score > 1 ? 'emerald' : imp.score < -1 ? 'red' : 'yellow';

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-4">
      <div className="text-xs text-zinc-500 uppercase tracking-widest mb-3">Weather — {weather.venue_name}</div>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div><div className="text-xs text-zinc-500">Temp</div><div className="text-lg font-bold">{weather.temperature}°F</div></div>
        <div><div className="text-xs text-zinc-500">Humidity</div><div className="text-lg font-bold">{weather.humidity}%</div></div>
        <div><div className="text-xs text-zinc-500">Wind</div><div className="text-sm font-semibold">{weather.wind_speed} mph {weather.wind_direction}</div></div>
        <div><div className="text-xs text-zinc-500">Rain%</div><div className={`text-sm font-semibold ${weather.precipitation_probability >= 50 ? 'text-red-400' : 'text-zinc-300'}`}>{weather.precipitation_probability}%</div></div>
      </div>
      <div className="text-xs text-zinc-400 mb-2">{weather.conditions}</div>
      {weather.mlb_reported && weather.mlb_reported.condition && (
        <div className="text-xs text-zinc-500 mb-2">MLB: {weather.mlb_reported.condition} • {weather.mlb_reported.temp}°F • {weather.mlb_reported.wind}</div>
      )}
      <div className={`bg-${impColor}-500/10 border border-${impColor}-500/30 rounded-xl p-2`}>
        <div className={`text-xs font-bold text-${impColor}-400`}>{imp.offense}</div>
        <div className="text-xs text-zinc-400 mt-0.5">{imp.note}</div>
      </div>
    </div>
  );
}

// ── Park Factors Card ─────────────────────────────────────────────────────────

function ParkCard({ park }) {
  if (!park) return null;
  const hrColor = park.hr >= 1.10 ? 'emerald' : park.hr <= 0.90 ? 'red' : 'yellow';
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-4">
      <div className="text-xs text-zinc-500 uppercase tracking-widest mb-3">Park Factors</div>
      <div className="text-sm font-semibold mb-2">{park.venue}</div>
      <div className="text-xs text-zinc-400 mb-3">{park.description}</div>
      <div className="grid grid-cols-3 gap-2 text-center">
        {[['Run', park.run], ['HR', park.hr], ['Hit', park.hit]].map(([label, val]) => {
          const c = val >= 1.10 ? 'emerald' : val <= 0.90 ? 'red' : 'yellow';
          return (
            <div key={label} className={`bg-${c}-500/10 border border-${c}-500/30 rounded-lg p-2`}>
              <div className="text-xs text-zinc-500">{label}</div>
              <div className={`text-lg font-bold text-${c}-400`}>{val?.toFixed(2)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Pitcher Stats Card ────────────────────────────────────────────────────────

function PitcherCard({ side, pitcherData, teamName }) {
  const [tab, setTab] = useState('stats');
  if (!pitcherData) return null;
  const { info, stats: profile, arsenal, splits, recent_starts } = pitcherData;
  const s = profile?.stats || {};

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl overflow-hidden">
      <div className="px-4 pt-4 pb-3 border-b border-zinc-800">
        <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">{side} Starter • {teamName}</div>
        <div className="flex items-center gap-3">
          <img src={profile?.headshot} className="w-12 h-12 rounded-xl bg-zinc-800 object-cover"
            onError={e => { e.target.src = `https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/${info?.id}/headshot/67/current`; }} />
          <div>
            <div className="font-bold text-lg">{info?.name || 'TBD'}</div>
            <div className="text-xs text-zinc-400">
              {profile?.throws && `Throws ${profile.throws}`}
              {profile?.age && ` • Age ${profile.age}`}
            </div>
          </div>
          <div className="ml-auto text-right">
            <div className={`text-2xl font-black ${statColor(s.era, [3.50, 4.25, 99], true)}`}>{s.era || '-'}</div>
            <div className="text-[10px] text-zinc-500">ERA</div>
          </div>
        </div>

        <div className="flex gap-1 mt-3">
          {['stats', 'arsenal', 'splits', 'recent'].map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-2 py-1 rounded-lg text-xs font-medium capitalize ${tab === t ? 'bg-blue-600 text-white' : 'text-zinc-400 hover:text-white'}`}>
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="p-4">
        {tab === 'stats' && (
          <div>
            <div className="grid grid-cols-4 gap-2 mb-4">
              {[
                ['W-L', `${s.wins || 0}-${s.losses || 0}`, null, false],
                ['ERA', s.era, [3.50, 4.25, 99], true],
                ['WHIP', s.whip, [1.10, 1.35, 99], true],
                ['IP', s.innings_pitched, null, false],
                ['K/9', s.k9, [9.0, 7.5, 0], false],
                ['BB/9', s.bb9, [2.5, 3.5, 99], true],
                ['HR/9', s.hr9, [1.0, 1.3, 99], true],
                ['FIP', s.fip, [3.50, 4.25, 99], true],
              ].map(([label, val, thresh, inv]) => (
                <div key={label} className="bg-zinc-800/50 rounded-lg p-2 text-center">
                  <div className="text-[10px] text-zinc-500 mb-0.5">{label}</div>
                  <div className={`text-sm font-bold ${thresh ? statColor(val, thresh, inv) : 'text-white'}`}>{val || '-'}</div>
                </div>
              ))}
            </div>
            <div className="grid grid-cols-3 gap-2">
              {[
                ['K%', s.k_pct, [25, 18, 0], false],
                ['BB%', s.bb_pct, [6, 9, 99], true],
                ['K-BB%', s.k_bb, [3.5, 2.5, 0], false],
              ].map(([label, val, thresh, inv]) => (
                <div key={label} className="bg-zinc-800/50 rounded-lg p-2 text-center">
                  <div className="text-[10px] text-zinc-500 mb-0.5">{label}</div>
                  <div className={`text-sm font-bold ${thresh ? statColor(val, thresh, inv) : 'text-white'}`}>{val || '-'}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              {[
                ['AVG Against', s.avg, [0.230, 0.260, 0.300], true],
                ['OBP Against', s.obp, [0.290, 0.320, 0.360], true],
                ['OPS Against', s.ops, [0.650, 0.730, 0.820], true],
              ].map(([label, val, thresh, inv]) => (
                <div key={label} className="bg-zinc-800/50 rounded-lg p-2 text-center">
                  <div className="text-[10px] text-zinc-500 mb-0.5">{label}</div>
                  <div className={`text-sm font-bold ${thresh ? statColor(val, thresh, inv) : 'text-white'}`}>{val || '-'}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'arsenal' && (
          <div>
            {arsenal && arsenal.length > 0 ? arsenal.map((p, i) => <PitchBar key={i} pitch={p} />) : (
              <div className="text-zinc-500 text-sm text-center py-4">Pitch data unavailable</div>
            )}
          </div>
        )}

        {tab === 'splits' && splits && (
          <div className="space-y-2">
            {Object.entries(splits).map(([splitName, stat]) => (
              <div key={splitName} className="bg-zinc-800/50 rounded-xl p-3">
                <div className="text-xs font-semibold text-zinc-400 mb-2">{splitName}</div>
                <div className="grid grid-cols-4 gap-2 text-xs text-center">
                  {[['ERA', stat.era, [3.50, 4.25, 99], true], ['WHIP', stat.whip, [1.10, 1.35, 99], true],
                    ['AVG', stat.avg, [0.230, 0.260, 0.300], true], ['OPS', stat.ops, [0.650, 0.730, 0.820], true]].map(([l, v, t, inv]) => (
                    <div key={l}>
                      <div className="text-zinc-600">{l}</div>
                      <div className={`font-bold ${statColor(v, t, inv)}`}>{v || '-'}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {Object.keys(splits).length === 0 && (
              <div className="text-zinc-500 text-sm text-center py-4">Splits unavailable</div>
            )}
          </div>
        )}

        {tab === 'recent' && (
          <div>
            {recent_starts && recent_starts.length > 0 ? (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-zinc-500 border-b border-zinc-800">
                    {['Date', 'Opp', 'IP', 'H', 'R', 'BB', 'K', 'Pit'].map(h => (
                      <th key={h} className="py-1 px-1 text-center">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {recent_starts.map((g, i) => {
                    const qualityStart = (() => {
                      try {
                        const parts = String(g.ip).split('.');
                        const inn = parseInt(parts[0]) + (parseInt(parts[1] || 0)) / 3;
                        return inn >= 6 && g.er <= 3;
                      } catch { return false; }
                    })();
                    return (
                      <tr key={i} className={`border-b border-zinc-800/40 ${qualityStart ? 'bg-emerald-500/5' : ''}`}>
                        <td className="py-1.5 px-1 text-zinc-400">{g.date?.slice(5)}</td>
                        <td className="py-1.5 px-1 text-center">{g.opponent}</td>
                        <td className="py-1.5 px-1 text-center font-bold">{g.ip}</td>
                        <td className="py-1.5 px-1 text-center">{g.h}</td>
                        <td className={`py-1.5 px-1 text-center font-bold ${g.er >= 4 ? 'text-red-400' : g.er <= 1 ? 'text-emerald-400' : 'text-yellow-400'}`}>{g.er}</td>
                        <td className="py-1.5 px-1 text-center">{g.bb}</td>
                        <td className={`py-1.5 px-1 text-center font-bold ${g.k >= 8 ? 'text-emerald-400' : ''}`}>{g.k}</td>
                        <td className="py-1.5 px-1 text-center text-zinc-500">{g.pitches}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <div className="text-zinc-500 text-sm text-center py-4">No recent start data</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Matchup Row ───────────────────────────────────────────────────────────────

function MatchupRow({ item }) {
  const [expanded, setExpanded] = useState(false);
  const [last5, setLast5] = useState(null);
  const { batter, h2h, matchup_grade } = item;
  const grade = matchup_grade || {};
  const gc = gradeColor[grade.grade] || 'zinc';
  const career = h2h?.career_summary || {};
  const hasPa = career.pa > 0;

  const loadLast5 = async () => {
    if (last5 || !batter?.player_id) return;
    try {
      const r = await fetch(`${API_URL}/baseball/batter/${batter.player_id}/last5`);
      const d = await r.json();
      setLast5(d.games || []);
    } catch { setLast5([]); }
  };

  return (
    <div className="border-b border-zinc-800/50 last:border-0">
      <button className="w-full px-3 py-2.5 flex items-center gap-3 hover:bg-zinc-800/30 text-left" onClick={() => { setExpanded(x => !x); loadLast5(); }}>
        <span className="text-xs text-zinc-500 w-4 text-right">{batter.order}</span>
        <span className="text-xs bg-zinc-800 rounded px-1.5 py-0.5 w-8 text-center text-zinc-300">{batter.position}</span>
        <span className="flex-1 text-sm font-medium">{batter.name}</span>
        <span className="text-xs text-zinc-500 mr-2">{batter.avg} / {batter.ops}</span>
        <span className={`px-2 py-0.5 rounded-lg text-xs font-bold bg-${gc}-500/20 text-${gc}-400`}>
          {grade.grade} <span className="font-normal text-zinc-400 hidden sm:inline">— {grade.label}</span>
        </span>
        <span className="text-zinc-600 text-xs ml-1">{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <div className="px-4 pb-3 bg-zinc-900/30">
          {last5 && (
            <div className="mb-3 pt-2">
              <div className="text-xs text-zinc-500 mb-1.5">Last 5 Games</div>
              <Last5Bar games={last5} />
              {last5.length > 0 && (
                <div className="flex gap-4 mt-1.5 text-xs text-zinc-500">
                  <span>L5 AVG: <span className="text-white font-bold">
                    {(() => { const ab = last5.reduce((s,g)=>s+g.ab,0); const h = last5.reduce((s,g)=>s+g.h,0); return ab>0 ? `.${String(Math.round(h/ab*1000)).padStart(3,'0')}` : '-'; })()}
                  </span></span>
                  <span>TB: <span className="text-white font-bold">{last5.reduce((s,g)=>s+g.total_bases,0)}</span></span>
                  <span>HR: <span className="text-white font-bold">{last5.reduce((s,g)=>s+g.hr,0)}</span></span>
                </div>
              )}
            </div>
          )}
          {hasPa ? (
            <div>
              <div className="text-xs text-zinc-500 mb-2">Career H2H vs this pitcher ({career.pa} PA)</div>
              <div className="grid grid-cols-4 sm:grid-cols-8 gap-2 text-center text-xs">
                {[['PA', career.pa], ['AB', career.ab], ['H', career.hits],
                  ['2B', career.doubles], ['3B', career.triples], ['HR', career.hr],
                  ['BB', career.bb], ['K', career.k]].map(([l, v]) => (
                  <div key={l} className="bg-zinc-800/50 rounded p-1.5">
                    <div className="text-zinc-600 text-[10px]">{l}</div>
                    <div className="font-bold text-white">{v}</div>
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-4 gap-2 text-center text-xs mt-2">
                {[['AVG', career.avg, [0.280, 0.230, 0], false], ['OBP', career.obp, [0.340, 0.290, 0], false],
                  ['SLG', career.slg, [0.450, 0.360, 0], false], ['OPS', career.ops, [0.800, 0.670, 0], false]].map(([l, v, t, inv]) => (
                  <div key={l} className="bg-zinc-800/50 rounded p-1.5">
                    <div className="text-zinc-600 text-[10px]">{l}</div>
                    <div className={`font-bold ${statColor(v, t, inv)}`}>{v}</div>
                  </div>
                ))}
              </div>
              <div className="text-xs text-zinc-500 mt-2">{h2h?.summary}</div>
            </div>
          ) : (
            <div className="text-xs text-zinc-500 py-2">
              No career H2H history — based on season stats (OPS: {batter.ops})
            </div>
          )}
          {h2h?.season && h2h.season.length > 0 && (
            <div className="mt-2">
              <div className="text-xs text-zinc-500 mb-1">This Season vs Pitcher</div>
              {h2h.season.map((s, i) => (
                <div key={i} className="text-xs text-zinc-300">{s.pa} PA, {s.avg} AVG, {s.hr} HR, {s.ops} OPS</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Matchup Panel ─────────────────────────────────────────────────────────────

function MatchupPanel({ title, items, pitcherName }) {
  if (!items || items.length === 0) return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-4">
      <div className="text-sm font-semibold mb-2">{title}</div>
      <div className="text-sm text-zinc-500">Lineup not yet confirmed</div>
    </div>
  );
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-800">
        <div className="font-semibold text-sm">{title}</div>
        <div className="text-xs text-zinc-500">vs {pitcherName}</div>
      </div>
      <div>
        {items.map((item, i) => <MatchupRow key={i} item={item} />)}
      </div>
    </div>
  );
}

// ── Analysis Summary ──────────────────────────────────────────────────────────

function AnalysisSummary({ analysis, awayTeam, homeTeam }) {
  if (!analysis) return null;
  const edgeColor = analysis.edge?.includes('Away') ? 'blue' : analysis.edge?.includes('Home') ? 'emerald' : 'zinc';
  const overUnderColor = analysis.over_under_lean === 'Over' ? 'emerald' : analysis.over_under_lean === 'Under' ? 'red' : 'zinc';
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-4">
      <div className="text-xs text-zinc-500 uppercase tracking-widest mb-3">AI Game Analysis</div>
      <div className="flex gap-4 mb-3">
        <div className={`flex-1 bg-${edgeColor}-500/10 border border-${edgeColor}-500/30 rounded-xl p-3 text-center`}>
          <div className="text-xs text-zinc-500">Game Edge</div>
          <div className={`font-bold text-${edgeColor}-400`}>{analysis.edge}</div>
        </div>
        <div className={`flex-1 bg-${overUnderColor}-500/10 border border-${overUnderColor}-500/30 rounded-xl p-3 text-center`}>
          <div className="text-xs text-zinc-500">O/U Lean</div>
          <div className={`font-bold text-${overUnderColor}-400`}>{analysis.over_under_lean}</div>
        </div>
        <div className="flex-1 bg-zinc-800/50 border border-zinc-700 rounded-xl p-3 text-center">
          <div className="text-xs text-zinc-500">Est. Total</div>
          <div className="font-bold text-white">{analysis.estimated_total}</div>
        </div>
      </div>
      {analysis.notes && analysis.notes.length > 0 && (
        <ul className="space-y-1">
          {analysis.notes.map((note, i) => (
            <li key={i} className="text-xs text-zinc-400 flex gap-1.5">
              <span className="text-blue-500 mt-0.5">•</span>{note}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Odds Badge ────────────────────────────────────────────────────────────────

function OddsLine({ odds }) {
  if (!odds || !odds.total) return null;
  const ml = odds.moneyline || {};
  const tot = odds.total || {};
  const fmtML = (v) => v > 0 ? `+${v}` : v < 0 ? `${v}` : 'Live';
  return (
    <div className="mt-2 grid grid-cols-3 gap-1 text-xs">
      <div className="bg-zinc-800 rounded-lg p-1.5 text-center">
        <div className="text-zinc-600 text-[9px]">AWAY ML</div>
        <div className={`font-bold ${ml.away > 0 ? 'text-zinc-300' : ml.away < 0 ? 'text-emerald-400' : 'text-zinc-500'}`}>{fmtML(ml.away)}</div>
      </div>
      <div className="bg-zinc-800 rounded-lg p-1.5 text-center">
        <div className="text-zinc-600 text-[9px]">O/U</div>
        <div className="font-bold text-yellow-400">{tot.line}</div>
        <div className="text-[9px] text-zinc-600">O{tot.over_odds} U{tot.under_odds}</div>
      </div>
      <div className="bg-zinc-800 rounded-lg p-1.5 text-center">
        <div className="text-zinc-600 text-[9px]">HOME ML</div>
        <div className={`font-bold ${ml.home < 0 ? 'text-emerald-400' : ml.home > 0 ? 'text-zinc-300' : 'text-zinc-500'}`}>{fmtML(ml.home)}</div>
      </div>
    </div>
  );
}

// ── Prop Card ─────────────────────────────────────────────────────────────────

function PropCard({ prop }) {
  const leanColor = prop.lean === 'OVER' ? 'emerald' : prop.lean === 'UNDER' ? 'red' : 'zinc';
  const confBadge = prop.confidence === 'Strong' ? 'bg-yellow-500/20 text-yellow-400' : prop.confidence === 'Lean' ? 'bg-blue-500/20 text-blue-400' : 'bg-zinc-700 text-zinc-400';

  return (
    <div className={`bg-zinc-900/60 border border-${leanColor}-500/30 rounded-xl p-3`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <div className="text-xs text-zinc-500 uppercase tracking-widest">{prop.prop_type}</div>
          <div className="font-semibold text-sm">{prop.batter || prop.pitcher || 'Game Total'}</div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className={`text-xs font-bold px-2 py-0.5 rounded-lg bg-${leanColor}-500/20 text-${leanColor}-400`}>{prop.lean}</span>
          <span className={`text-xs px-2 py-0.5 rounded-lg ${confBadge}`}>{prop.confidence}</span>
        </div>
      </div>
      {prop.line && (
        <div className="flex gap-3 text-xs mb-2">
          <span className="text-zinc-500">Line</span>
          <span className="font-bold text-white">{prop.line}</span>
          {prop.avg_k_per_start > 0 && <span className="text-zinc-500">Avg: <span className="text-white">{prop.avg_k_per_start}K/start</span></span>}
          {prop.l5_avg && <span className="text-zinc-500">L5 AVG: <span className={statColor(prop.l5_avg, [0.300, 0.240, 0])}>{prop.l5_avg}</span></span>}
        </div>
      )}
      {prop.recent_k_games?.length > 0 && (
        <div className="flex gap-1 mb-2">
          {prop.recent_k_games.map((k, i) => (
            <span key={i} className={`text-xs font-bold px-1.5 py-0.5 rounded ${k >= 9 ? 'bg-emerald-500/20 text-emerald-400' : k >= 7 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-zinc-700 text-zinc-400'}`}>{k}K</span>
          ))}
        </div>
      )}
      {prop.recent_hits?.length > 0 && (
        <div className="flex gap-1 mb-2">
          {prop.recent_hits.map((h, i) => (
            <span key={i} className={`text-xs font-bold px-1.5 py-0.5 rounded ${h >= 3 ? 'bg-emerald-500/20 text-emerald-400' : h >= 1 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400'}`}>{h}H</span>
          ))}
        </div>
      )}
      <ul className="space-y-0.5">
        {(prop.notes || []).map((n, i) => (
          <li key={i} className="text-xs text-zinc-400 flex gap-1.5"><span className={`text-${leanColor}-500`}>•</span>{n}</li>
        ))}
      </ul>
      {prop.posted_line && (
        <div className="mt-2 pt-2 border-t border-zinc-800 flex gap-3 text-xs">
          <span className="text-zinc-500">Posted O/U: <span className="font-bold text-white">{prop.posted_line}</span></span>
          {prop.over_odds && <span className="text-zinc-500">O{prop.over_odds} U{prop.under_odds}</span>}
        </div>
      )}
    </div>
  );
}

// ── Last 5 mini bar ───────────────────────────────────────────────────────────

function Last5Bar({ games }) {
  if (!games || games.length === 0) return <span className="text-xs text-zinc-600">No data</span>;
  return (
    <div className="flex gap-1 items-center">
      {games.map((g, i) => (
        <div key={i} className="group relative">
          <div className={`w-5 h-5 rounded text-[9px] font-bold flex items-center justify-center
            ${g.h >= 3 ? 'bg-emerald-500/30 text-emerald-400' : g.h >= 1 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/10 text-red-400'}`}>
            {g.h}
          </div>
          <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 hidden group-hover:block z-30 pointer-events-none">
            <div className="bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1 text-xs whitespace-nowrap">
              <div className="font-bold">{g.home_away} {g.opponent}</div>
              <div>{g.ab} AB · {g.h} H · {g.hr} HR · {g.rbi} RBI · {g.bb} BB · {g.k} K</div>
              <div className="text-zinc-500">{g.date?.slice(5)}</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Game Card (today's games list) ────────────────────────────────────────────

function GameCard({ game, onSelect }) {
  const statusColor = game.status_code === 'I' ? 'text-red-400' : game.status_code === 'F' ? 'text-zinc-500' : 'text-emerald-400';
  return (
    <button onClick={() => onSelect(game)}
      className="w-full bg-zinc-900/50 border border-zinc-800 rounded-2xl p-4 hover:border-blue-500/50 hover:bg-zinc-800/50 transition-all text-left">
      <div className="flex justify-between items-start mb-2">
        <span className={`text-xs font-semibold ${statusColor}`}>{game.status}</span>
        <span className="text-xs text-zinc-500">{fmtTime(game.game_time)}</span>
      </div>
      <div className="flex items-center justify-between">
        <div className="text-center flex-1">
          <div className="font-bold">{game.away.team_abbr}</div>
          <div className="text-xs text-zinc-500">{game.away.record}</div>
        </div>
        <div className="text-zinc-600 font-bold px-3">@</div>
        <div className="text-center flex-1">
          <div className="font-bold">{game.home.team_abbr}</div>
          <div className="text-xs text-zinc-500">{game.home.record}</div>
        </div>
      </div>
      <OddsLine odds={game.odds} />
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="bg-zinc-800/50 rounded-lg p-2">
          <div className="text-zinc-600 mb-0.5">Away SP</div>
          <div className="font-medium truncate">{game.away.probable_pitcher?.name || 'TBD'}</div>
        </div>
        <div className="bg-zinc-800/50 rounded-lg p-2">
          <div className="text-zinc-600 mb-0.5">Home SP</div>
          <div className="font-medium truncate">{game.home.probable_pitcher?.name || 'TBD'}</div>
        </div>
      </div>
      <div className="mt-2 text-[10px] text-zinc-600 truncate">{game.venue_name}</div>
    </button>
  );
}

// ── Player Search Modal ───────────────────────────────────────────────────────

function PlayerSearchModal({ title, type, onSelect, onClose }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  useEffect(() => { inputRef.current?.focus(); }, []);
  useEffect(() => {
    if (query.length < 2) { setResults([]); return; }
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API_URL}/baseball/players/search?q=${encodeURIComponent(query)}&type=${type}`);
        const d = await r.json();
        setResults(d.players || []);
      } catch { setResults([]); }
      finally { setLoading(false); }
    }, 400);
    return () => clearTimeout(t);
  }, [query, type]);

  return (
    <div className="fixed inset-0 bg-black/90 z-50 flex items-start justify-center pt-20 px-4" onClick={onClose}>
      <div className="w-full max-w-lg" onClick={e => e.stopPropagation()}>
        <div className="text-sm text-zinc-500 mb-2">{title}</div>
        <input ref={inputRef} value={query} onChange={e => setQuery(e.target.value)}
          placeholder={`Search ${type === 'pitcher' ? 'pitcher' : type === 'batter' ? 'batter' : 'player'} name...`}
          className="w-full px-5 py-4 bg-zinc-900 border border-zinc-700 rounded-2xl text-white text-lg focus:outline-none focus:border-blue-500" />
        {loading && <div className="mt-2 text-center text-zinc-500 text-sm">Searching...</div>}
        {results.length > 0 && (
          <div className="mt-2 bg-zinc-900 border border-zinc-800 rounded-2xl max-h-80 overflow-y-auto">
            {results.map(p => (
              <button key={p.id} onClick={() => onSelect(p)}
                className="w-full px-4 py-3 flex items-center gap-3 hover:bg-zinc-800 text-left border-b border-zinc-800 last:border-0">
                <img src={p.headshot} className="w-10 h-10 rounded-full bg-zinc-800 object-cover"
                  onError={e => e.target.style.display = 'none'} />
                <div className="flex-1">
                  <div className="font-semibold">{p.name}</div>
                  <div className="text-xs text-zinc-500">{p.team_abbr} • {p.position} • {p.throws ? `T: ${p.throws}` : ''}{p.bats ? ` B: ${p.bats}` : ''}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Quick Matchup (standalone pitcher vs batter) ──────────────────────────────

function QuickMatchup() {
  const [pitcher, setPitcher] = useState(null);
  const [batter, setBatter] = useState(null);
  const [matchupData, setMatchupData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searchFor, setSearchFor] = useState(null);

  const runMatchup = async () => {
    if (!pitcher || !batter) return;
    setLoading(true);
    try {
      const r = await fetch(`${API_URL}/baseball/matchup?batter_id=${batter.id}&pitcher_id=${pitcher.id}`);
      const d = await r.json();
      setMatchupData(d);
    } catch { }
    finally { setLoading(false); }
  };

  useEffect(() => { if (pitcher && batter) runMatchup(); }, [pitcher, batter]);

  return (
    <div>
      {searchFor && (
        <PlayerSearchModal
          title={searchFor === 'pitcher' ? 'Search Pitcher' : 'Search Batter'}
          type={searchFor}
          onSelect={p => { searchFor === 'pitcher' ? setPitcher(p) : setBatter(p); setSearchFor(null); }}
          onClose={() => setSearchFor(null)}
        />
      )}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div>
          <div className="text-xs text-zinc-500 mb-2">PITCHER</div>
          <button onClick={() => setSearchFor('pitcher')}
            className="w-full bg-zinc-900/50 border border-zinc-800 rounded-2xl p-4 hover:border-blue-500/50 text-left">
            {pitcher ? (
              <div className="flex items-center gap-3">
                <img src={pitcher.headshot} className="w-10 h-10 rounded-xl bg-zinc-800" onError={e => e.target.style.display = 'none'} />
                <div>
                  <div className="font-semibold">{pitcher.name}</div>
                  <div className="text-xs text-zinc-500">{pitcher.team_abbr} • {pitcher.position}</div>
                </div>
              </div>
            ) : (
              <div className="text-zinc-500 text-sm">+ Select Pitcher</div>
            )}
          </button>
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-2">BATTER</div>
          <button onClick={() => setSearchFor('batter')}
            className="w-full bg-zinc-900/50 border border-zinc-800 rounded-2xl p-4 hover:border-blue-500/50 text-left">
            {batter ? (
              <div className="flex items-center gap-3">
                <img src={batter.headshot} className="w-10 h-10 rounded-xl bg-zinc-800" onError={e => e.target.style.display = 'none'} />
                <div>
                  <div className="font-semibold">{batter.name}</div>
                  <div className="text-xs text-zinc-500">{batter.team_abbr} • {batter.position}</div>
                </div>
              </div>
            ) : (
              <div className="text-zinc-500 text-sm">+ Select Batter</div>
            )}
          </button>
        </div>
      </div>

      {loading && <div className="text-center py-8"><div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" /></div>}

      {matchupData && !loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            {matchupData.pitcher?.stats && (
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-4">
                <div className="text-xs text-zinc-500 mb-2">Pitcher Season</div>
                {[['ERA', matchupData.pitcher.stats.era, [3.50, 4.25, 99], true],
                  ['WHIP', matchupData.pitcher.stats.whip, [1.10, 1.35, 99], true],
                  ['K/9', matchupData.pitcher.stats.k9, [9.0, 7.5, 0], false],
                  ['FIP', matchupData.pitcher.stats.fip, [3.50, 4.25, 99], true]].map(([l, v, t, inv]) => (
                  <div key={l} className="flex justify-between text-sm py-1 border-b border-zinc-800 last:border-0">
                    <span className="text-zinc-500">{l}</span>
                    <span className={`font-bold ${statColor(v, t, inv)}`}>{v || '-'}</span>
                  </div>
                ))}
              </div>
            )}
            {matchupData.batter?.stats && (
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-4">
                <div className="text-xs text-zinc-500 mb-2">Batter Season</div>
                {[['AVG', matchupData.batter.stats.avg, [0.280, 0.250, 0], false],
                  ['OBP', matchupData.batter.stats.obp, [0.350, 0.310, 0], false],
                  ['SLG', matchupData.batter.stats.slg, [0.450, 0.380, 0], false],
                  ['OPS', matchupData.batter.stats.ops, [0.800, 0.700, 0], false]].map(([l, v, t, inv]) => (
                  <div key={l} className="flex justify-between text-sm py-1 border-b border-zinc-800 last:border-0">
                    <span className="text-zinc-500">{l}</span>
                    <span className={`font-bold ${statColor(v, t, inv)}`}>{v || '-'}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {matchupData.h2h && (
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-4">
              <div className="text-xs text-zinc-500 uppercase tracking-widest mb-3">Head-to-Head History</div>
              {matchupData.h2h.career_summary?.pa > 0 ? (
                <div>
                  <div className="text-sm text-zinc-300 mb-3 font-medium">{matchupData.h2h.summary}</div>
                  <div className="grid grid-cols-4 gap-2 text-center text-xs">
                    {[['PA', matchupData.h2h.career_summary.pa], ['H', matchupData.h2h.career_summary.hits],
                      ['HR', matchupData.h2h.career_summary.hr], ['K', matchupData.h2h.career_summary.k]].map(([l, v]) => (
                      <div key={l} className="bg-zinc-800/50 rounded-lg p-2">
                        <div className="text-zinc-500">{l}</div>
                        <div className="font-bold text-white">{v}</div>
                      </div>
                    ))}
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-center text-xs mt-2">
                    {[['AVG', matchupData.h2h.career_summary.avg, [0.280, 0.230, 0], false],
                      ['OBP', matchupData.h2h.career_summary.obp, [0.340, 0.290, 0], false],
                      ['SLG', matchupData.h2h.career_summary.slg, [0.450, 0.360, 0], false],
                      ['OPS', matchupData.h2h.career_summary.ops, [0.800, 0.670, 0], false]].map(([l, v, t]) => (
                      <div key={l} className="bg-zinc-800/50 rounded-lg p-2">
                        <div className="text-zinc-500">{l}</div>
                        <div className={`font-bold ${statColor(v, t)}`}>{v}</div>
                      </div>
                    ))}
                  </div>
                  {matchupData.h2h.career && matchupData.h2h.career.length > 1 && (
                    <div className="mt-3">
                      <div className="text-xs text-zinc-500 mb-2">By Season</div>
                      <table className="w-full text-xs">
                        <thead><tr className="text-zinc-600 border-b border-zinc-800">
                          {['Season', 'PA', 'H', 'HR', 'BB', 'K', 'AVG', 'OPS'].map(h => <th key={h} className="py-1 px-1 text-center">{h}</th>)}
                        </tr></thead>
                        <tbody>{matchupData.h2h.career.map((s, i) => (
                          <tr key={i} className="border-b border-zinc-800/40">
                            <td className="py-1 px-1 text-center text-zinc-400">{s.season}</td>
                            <td className="py-1 px-1 text-center">{s.pa}</td>
                            <td className="py-1 px-1 text-center">{s.hits}</td>
                            <td className="py-1 px-1 text-center">{s.hr}</td>
                            <td className="py-1 px-1 text-center">{s.bb}</td>
                            <td className="py-1 px-1 text-center">{s.k}</td>
                            <td className={`py-1 px-1 text-center font-bold ${statColor(s.avg, [0.280, 0.230, 0])}`}>{s.avg}</td>
                            <td className={`py-1 px-1 text-center font-bold ${statColor(s.ops, [0.800, 0.670, 0])}`}>{s.ops}</td>
                          </tr>
                        ))}</tbody>
                      </table>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-sm text-zinc-500">{matchupData.h2h?.summary || 'No historical matchup data found'}</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Prop Sheet Panel ──────────────────────────────────────────────────────────

function PropSheetPanel({ gamePk }) {
  const [sheet, setSheet] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (!gamePk) return;
    setLoading(true); setErr('');
    fetch(`${API_URL}/baseball/game/${gamePk}/prop-sheet`)
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(d => setSheet(d))
      .catch(e => setErr(`Could not load prop sheet: ${e.message}`))
      .finally(() => setLoading(false));
  }, [gamePk]);

  if (loading) return <div className="text-center py-12"><div className="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" /><div className="text-zinc-400 text-sm">Building prop sheet...</div></div>;
  if (err) return <div className="text-red-400 text-sm bg-red-500/10 rounded-xl p-4">{err}</div>;
  if (!sheet) return null;

  const top = sheet.top_plays || [];
  const all = sheet.props || [];
  const totals = all.filter(p => p.prop_type === 'Game Total');
  const kProps = all.filter(p => p.prop_type === 'Strikeouts');
  const hitProps = all.filter(p => p.prop_type === 'Hits');
  const hrProps = all.filter(p => p.prop_type === 'Home Run');

  return (
    <div className="space-y-6">
      {top.length > 0 && (
        <div>
          <div className="text-sm font-semibold mb-3 flex items-center gap-2">
            <span className="text-yellow-400">★</span> Top Plays
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            {top.map((p, i) => <PropCard key={i} prop={p} />)}
          </div>
        </div>
      )}
      {totals.length > 0 && (
        <div>
          <div className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Game Total</div>
          <div className="grid sm:grid-cols-2 gap-3">{totals.map((p, i) => <PropCard key={i} prop={p} />)}</div>
        </div>
      )}
      {kProps.length > 0 && (
        <div>
          <div className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Strikeout Props</div>
          <div className="grid sm:grid-cols-2 gap-3">{kProps.map((p, i) => <PropCard key={i} prop={p} />)}</div>
        </div>
      )}
      {hitProps.length > 0 && (
        <div>
          <div className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Hit Props</div>
          <div className="grid sm:grid-cols-2 gap-3">{hitProps.map((p, i) => <PropCard key={i} prop={p} />)}</div>
        </div>
      )}
      {hrProps.length > 0 && (
        <div>
          <div className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Home Run Props</div>
          <div className="grid sm:grid-cols-2 gap-3">{hrProps.map((p, i) => <PropCard key={i} prop={p} />)}</div>
        </div>
      )}
      {top.length === 0 && all.length === 0 && <div className="text-zinc-500 text-sm">No strong prop angles detected for this game.</div>}
    </div>
  );
}

// ── Statcast Advanced Components ─────────────────────────────────────────────

const FireRating = ({ n }) => '🔥'.repeat(Math.min(Math.max(n || 1, 1), 3));

const FormBadge = ({ form }) => {
  const colors = { Hot: 'text-emerald-400 bg-emerald-500/15 border-emerald-500/30', Cold: 'text-sky-400 bg-sky-500/15 border-sky-500/30', Neutral: 'text-yellow-400 bg-yellow-500/15 border-yellow-500/30' };
  return <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${colors[form] || colors.Neutral}`}>{form}</span>;
};

const GradeBadge = ({ grade }) => {
  const colors = { 'A+': 'bg-emerald-500 text-black', A: 'bg-green-500 text-black', B: 'bg-lime-500 text-black', C: 'bg-yellow-500 text-black', D: 'bg-orange-500 text-black', F: 'bg-red-500 text-white' };
  return <span className={`text-xs px-2 py-0.5 rounded font-black ${colors[grade] || 'bg-zinc-700 text-zinc-300'}`}>{grade}</span>;
};

const PowerBar = ({ val, max = 1, color = 'blue' }) => {
  const pct = Math.min((val / max) * 100, 100);
  const gradients = { blue: 'from-blue-600 to-blue-400', green: 'from-emerald-600 to-emerald-400', red: 'from-red-600 to-red-400', orange: 'from-orange-600 to-orange-400' };
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full bg-gradient-to-r ${gradients[color]}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-zinc-400 w-10 text-right">{typeof val === 'number' ? val.toFixed(2) : val}</span>
    </div>
  );
};

function HRMatchupTable({ gamePk }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/baseball/game/${gamePk}/hr-table`)
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(d => setData(d))
      .catch(e => setErr(`HR table error: ${e.message}`))
      .finally(() => setLoading(false));
  }, [gamePk]);

  if (loading) return <div className="text-center py-10"><div className="w-8 h-8 border-4 border-orange-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" /><div className="text-zinc-400 text-sm">Loading Statcast HR table...</div></div>;
  if (err) return <div className="text-red-400 text-sm p-4 bg-red-500/10 rounded-xl">{err}</div>;
  if (!data) return null;

  const rows = data.table || [];
  const weather = data.weather || {};
  const park = data.park_factors || {};

  return (
    <div className="space-y-4">
      {/* Context bar */}
      <div className="flex flex-wrap gap-3 text-xs">
        {park.description && <span className="px-3 py-1 bg-zinc-800 rounded-full text-zinc-300">🏟 {data.venue?.name} — {park.description}</span>}
        {weather.available && <span className="px-3 py-1 bg-zinc-800 rounded-full text-zinc-300">🌤 {weather.condition} · {weather.temp_f}°F · {weather.wind_speed_mph} mph {weather.wind_dir}</span>}
        {park.hr && <span className={`px-3 py-1 rounded-full ${park.hr >= 1.10 ? 'bg-orange-500/20 text-orange-300' : park.hr <= 0.90 ? 'bg-blue-500/20 text-blue-300' : 'bg-zinc-800 text-zinc-300'}`}>HR Park Factor: {park.hr?.toFixed(2)}</span>}
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-2xl border border-zinc-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-zinc-900/80 text-zinc-500 text-xs uppercase tracking-wider">
              <th className="text-left px-3 py-3">Batter</th>
              <th className="px-2 py-3">Grade</th>
              <th className="px-2 py-3">HR%</th>
              <th className="px-2 py-3">Form</th>
              <th className="text-left px-3 py-3">Pitcher</th>
              <th className="px-2 py-3">Power</th>
              <th className="px-2 py-3">Vuln</th>
              <th className="px-2 py-3">Ctx</th>
              <th className="px-2 py-3">Match</th>
              <th className="px-2 py-3">Fair ML</th>
              <th className="px-2 py-3">Barrel%</th>
              <th className="px-2 py-3">xSLG</th>
              <th className="px-2 py-3">Bat Spd</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const hrColor = row.hr_prob_pct >= 25 ? 'text-orange-400 font-bold' : row.hr_prob_pct >= 15 ? 'text-yellow-400 font-semibold' : 'text-zinc-400';
              const powerColor = row.batter_power >= 0.7 ? 'text-emerald-400' : row.batter_power >= 0.5 ? 'text-yellow-400' : 'text-zinc-400';
              const vulnColor = row.pitcher_vuln >= 0.7 ? 'text-red-400' : row.pitcher_vuln >= 0.5 ? 'text-orange-400' : 'text-zinc-400';
              return (
                <tr key={i} className={`border-t border-zinc-800/50 hover:bg-zinc-800/30 transition-colors ${row.fire_rating >= 3 ? 'bg-orange-500/5' : ''}`}>
                  <td className="px-3 py-2.5">
                    <div className="font-medium text-white">{row.batter}</div>
                    <div className="text-xs text-zinc-500">#{row.order} · {row.season_avg} AVG</div>
                  </td>
                  <td className="px-2 py-2.5 text-center"><GradeBadge grade={row.grade} /></td>
                  <td className={`px-2 py-2.5 text-center ${hrColor}`}>{row.hr_prob_pct}%</td>
                  <td className="px-2 py-2.5 text-center"><FormBadge form={row.form} /></td>
                  <td className="px-3 py-2.5 text-xs text-zinc-300">{row.pitcher}</td>
                  <td className="px-2 py-2.5 text-center">
                    <div className={`text-xs font-mono font-bold ${powerColor}`}>{row.batter_power?.toFixed(2)}</div>
                  </td>
                  <td className="px-2 py-2.5 text-center">
                    <div className={`text-xs font-mono font-bold ${vulnColor}`}>{row.pitcher_vuln?.toFixed(2)}</div>
                  </td>
                  <td className="px-2 py-2.5 text-center">
                    <div className={`text-xs font-mono ${row.context_score >= 0.6 ? 'text-orange-400' : row.context_score >= 0.5 ? 'text-yellow-400' : 'text-zinc-400'}`}>{row.context_score?.toFixed(2)}</div>
                  </td>
                  <td className="px-2 py-2.5 text-center text-base leading-none"><FireRating n={row.fire_rating} /></td>
                  <td className={`px-2 py-2.5 text-center text-xs font-mono font-bold ${row.fair_odds?.startsWith('+') ? 'text-emerald-400' : 'text-zinc-300'}`}>{row.fair_odds}</td>
                  <td className="px-2 py-2.5 text-center text-xs font-mono text-orange-300">{row.barrel_pct > 0 ? `${row.barrel_pct?.toFixed(1)}%` : '—'}</td>
                  <td className="px-2 py-2.5 text-center text-xs font-mono text-purple-300">{row.xslg > 0 ? row.xslg?.toFixed(3) : '—'}</td>
                  <td className="px-2 py-2.5 text-center text-xs font-mono text-sky-300">{row.avg_bat_speed > 0 ? `${row.avg_bat_speed?.toFixed(1)}` : '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {rows.length === 0 && <div className="text-center py-8 text-zinc-500 text-sm">No Statcast data available for this game yet.</div>}
      </div>
    </div>
  );
}

function SlateAdvancedPanel() {
  const [activeTab, setActiveTab] = useState('meatball');
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const endpoints = {
    meatball: '/baseball/today/meatball-matchups',
    blast: '/baseball/today/blast-alerts',
    speed: '/baseball/today/bat-speed',
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const [mm, ba, bs] = await Promise.all([
        fetch(`${API_URL}${endpoints.meatball}`).then(r => r.json()),
        fetch(`${API_URL}${endpoints.blast}`).then(r => r.json()),
        fetch(`${API_URL}${endpoints.speed}`).then(r => r.json()),
      ]);
      setData({ meatball: mm.matchups || [], blast: ba.alerts || [], speed: bs.surges || [] });
      setLoaded(true);
    } catch (e) {
      setData({ error: e.message });
    } finally { setLoading(false); }
  };

  if (!loaded && !loading) return (
    <div className="text-center py-16 space-y-4">
      <div className="text-4xl">⚾</div>
      <div className="text-zinc-300 font-semibold">Statcast Advanced Panel</div>
      <div className="text-zinc-500 text-sm max-w-sm mx-auto">Loads Barrel%, xSLG, Bat Speed, Blast Rate, Meatball Matchups and Danger Combos across today's full slate.</div>
      <div className="text-zinc-600 text-xs">Takes ~60-90 seconds to analyze all games</div>
      <button onClick={loadData} className="px-6 py-3 bg-orange-600 hover:bg-orange-500 rounded-xl font-semibold text-white">Load Statcast Data</button>
    </div>
  );

  if (loading) return (
    <div className="text-center py-20 space-y-3">
      <div className="w-12 h-12 border-4 border-orange-500 border-t-transparent rounded-full animate-spin mx-auto" />
      <div className="text-zinc-300 font-medium">Fetching Statcast leaderboards...</div>
      <div className="text-zinc-500 text-sm">Barrel%, xSLG, bat speed, blast rates across all games</div>
    </div>
  );

  const tabs = [
    { key: 'meatball', label: '🎯 Meatball Matchups', count: data.meatball?.length },
    { key: 'blast', label: '💥 Blast Alerts', count: data.blast?.length },
    { key: 'speed', label: '⚡ Bat Speed', count: data.speed?.length },
  ];

  return (
    <div className="space-y-4">
      <div className="flex gap-2 flex-wrap">
        {tabs.map(t => (
          <button key={t.key} onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-2 ${activeTab === t.key ? 'bg-orange-600 text-white' : 'bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white'}`}>
            {t.label} <span className="bg-black/30 px-1.5 rounded text-xs">{t.count}</span>
          </button>
        ))}
        <button onClick={loadData} className="ml-auto px-3 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-xl text-xs text-zinc-400">↻ Refresh</button>
      </div>

      {/* MEATBALL MATCHUPS */}
      {activeTab === 'meatball' && (
        <div>
          <div className="text-xs text-zinc-500 mb-3">Heart-zone power matchups — high xSLG batters vs hard-contact pitchers (Statcast barrel% proxy)</div>
          <div className="space-y-2">
            {(data.meatball || []).map((m, i) => (
              <div key={i} className={`rounded-xl border p-4 ${m.fire_rating >= 3 ? 'bg-orange-500/8 border-orange-500/30' : 'bg-zinc-900/50 border-zinc-800'}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-white">{m.batter}</span>
                      <span className="text-xs text-zinc-500">{m.batter_team}</span>
                      <span className="text-base"><FireRating n={m.fire_rating} /></span>
                    </div>
                    <div className="text-xs text-zinc-400 mt-0.5">vs <span className="text-zinc-300">{m.pitcher}</span></div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-orange-400 font-bold text-sm">Score {m.matchup_score?.toFixed(3)}</div>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3 mt-3 text-xs">
                  <div className="bg-zinc-800/60 rounded-lg p-2 text-center">
                    <div className="text-zinc-500 mb-0.5">Batter xSLG</div>
                    <div className="text-purple-300 font-bold text-sm">{m.batter_xslg}</div>
                  </div>
                  <div className="bg-zinc-800/60 rounded-lg p-2 text-center">
                    <div className="text-zinc-500 mb-0.5">Batter Barrel%</div>
                    <div className="text-orange-300 font-bold text-sm">{m.batter_barrel}%</div>
                  </div>
                  <div className="bg-zinc-800/60 rounded-lg p-2 text-center">
                    <div className="text-zinc-500 mb-0.5">P Barrel Allowed</div>
                    <div className={`font-bold text-sm ${m.pitcher_barrel_against >= 12 ? 'text-red-400' : m.pitcher_barrel_against >= 8 ? 'text-orange-400' : 'text-zinc-300'}`}>{m.pitcher_barrel_against}%</div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 mt-2 text-xs">
                  <div>
                    <div className="text-zinc-500 mb-1">Batter Power</div>
                    <PowerBar val={m.batter_power} color="orange" />
                  </div>
                  <div>
                    <div className="text-zinc-500 mb-1">Pitcher Vuln</div>
                    <PowerBar val={m.pitcher_vuln} color="red" />
                  </div>
                </div>
                {m.batter_bat_speed > 0 && <div className="mt-2 text-xs text-zinc-500">Bat speed: <span className="text-sky-300">{m.batter_bat_speed} mph</span> · P EV against: <span className="text-zinc-300">{m.pitcher_ev_against} mph</span></div>}
              </div>
            ))}
            {(!data.meatball || data.meatball.length === 0) && <div className="text-zinc-500 text-sm text-center py-8">No strong meatball matchups found</div>}
          </div>
        </div>
      )}

      {/* BLAST ALERTS */}
      {activeTab === 'blast' && (
        <div>
          <div className="text-xs text-zinc-500 mb-3">High barrel/blast rate batters vs HR-prone pitchers — 🚨 = Danger Combo (high barrel + high pitcher HR/9)</div>
          <div className="space-y-2">
            {(data.blast || []).map((b, i) => (
              <div key={i} className={`rounded-xl border p-4 ${b.danger_combo ? 'bg-red-500/8 border-red-500/30' : 'bg-zinc-900/50 border-zinc-800'}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      {b.danger_combo && <span className="text-red-400 text-xs font-bold bg-red-500/15 border border-red-500/30 px-2 py-0.5 rounded-full">🚨 DANGER COMBO</span>}
                      <span className="font-semibold text-white">{b.batter}</span>
                      <span className="text-xs text-zinc-500">{b.batter_team} #{b.order}</span>
                      <span className="text-base"><FireRating n={b.fire_rating} /></span>
                    </div>
                    <div className="text-xs text-zinc-400 mt-0.5">vs <span className="text-zinc-300">{b.pitcher}</span></div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className={`text-lg font-black ${b.hr_probability >= 30 ? 'text-red-400' : b.hr_probability >= 20 ? 'text-orange-400' : 'text-yellow-400'}`}>{b.hr_probability}%</div>
                    <div className="text-xs text-zinc-500">HR Prob</div>
                  </div>
                </div>
                <div className="grid grid-cols-4 gap-2 mt-3 text-xs">
                  <div className="bg-zinc-800/60 rounded-lg p-2 text-center">
                    <div className="text-zinc-500 mb-0.5">Barrel%</div>
                    <div className={`font-bold ${b.barrel_pct >= 15 ? 'text-red-400' : b.barrel_pct >= 10 ? 'text-orange-400' : 'text-yellow-400'}`}>{b.barrel_pct}%</div>
                  </div>
                  <div className="bg-zinc-800/60 rounded-lg p-2 text-center">
                    <div className="text-zinc-500 mb-0.5">Blast%</div>
                    <div className="text-orange-300 font-bold">{b.blast_pct}%</div>
                  </div>
                  <div className="bg-zinc-800/60 rounded-lg p-2 text-center">
                    <div className="text-zinc-500 mb-0.5">P HR/9</div>
                    <div className={`font-bold ${b.pitcher_hr9 >= 1.5 ? 'text-red-400' : b.pitcher_hr9 >= 1.2 ? 'text-orange-400' : 'text-zinc-300'}`}>{b.pitcher_hr9}</div>
                  </div>
                  <div className="bg-zinc-800/60 rounded-lg p-2 text-center">
                    <div className="text-zinc-500 mb-0.5">Fair Odds</div>
                    <div className={`font-bold font-mono ${b.fair_odds?.startsWith('+') ? 'text-emerald-400' : 'text-zinc-300'}`}>{b.fair_odds}</div>
                  </div>
                </div>
                <div className="mt-2 flex gap-4 text-xs text-zinc-500">
                  <span>Park HR PF: <span className={b.park_hr_pf >= 1.1 ? 'text-orange-300' : 'text-zinc-400'}>{b.park_hr_pf?.toFixed(2)}</span></span>
                  <span>EV50: <span className="text-sky-300">{b.ev50 > 0 ? b.ev50 : '—'}</span></span>
                  {b.park_name && <span className="text-zinc-600">{b.park_name}</span>}
                </div>
              </div>
            ))}
            {(!data.blast || data.blast.length === 0) && <div className="text-zinc-500 text-sm text-center py-8">No blast alerts for today's slate</div>}
          </div>
        </div>
      )}

      {/* BAT SPEED */}
      {activeTab === 'speed' && (
        <div>
          <div className="text-xs text-zinc-500 mb-3">Fastest bats on today's slate (avg bat speed mph, min 20 competitive swings)</div>
          <div className="space-y-2">
            {(data.speed || []).map((s, i) => (
              <div key={i} className="bg-zinc-900/50 border border-zinc-800 rounded-xl px-4 py-3 flex items-center gap-4">
                <div className="text-zinc-600 font-mono text-sm w-5 shrink-0">{i + 1}</div>
                <div className="flex-1">
                  <div className="font-medium text-white">{s.batter} <span className="text-xs text-zinc-500">{s.batter_team}</span></div>
                  <div className="text-xs text-zinc-500 mt-0.5">vs {s.pitcher}</div>
                </div>
                <div className="text-right shrink-0 space-y-1">
                  <div className={`text-lg font-black ${s.avg_bat_speed >= 76 ? 'text-sky-400' : s.avg_bat_speed >= 73 ? 'text-blue-400' : 'text-zinc-300'}`}>{s.avg_bat_speed} <span className="text-xs font-normal text-zinc-500">mph</span></div>
                  <div className="flex gap-3 text-xs text-zinc-500 justify-end">
                    <span>Blast: <span className="text-orange-300">{s.blast_pct}%</span></span>
                    <span>Hard: <span className="text-emerald-300">{s.hard_swing_rate?.toFixed(1)}%</span></span>
                  </div>
                </div>
              </div>
            ))}
            {(!data.speed || data.speed.length === 0) && <div className="text-zinc-500 text-sm text-center py-8">No bat speed data available</div>}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Baseball Analysis Component ─────────────────────────────────────────

export default function BaseballAnalysis() {
  const [view, setView] = useState('games');
  const [analysisTab, setAnalysisTab] = useState('breakdown');
  const [games, setGames] = useState([]);
  const [gamesDate, setGamesDate] = useState('');
  const [gamesLoading, setGamesLoading] = useState(false);
  const [selectedGame, setSelectedGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState('');
  const [gameOdds, setGameOdds] = useState(null);

  const todayStr = new Date().toISOString().slice(0, 10);

  const loadGames = async (dateStr) => {
    setGamesLoading(true);
    try {
      const url = `${API_URL}/baseball/games/with-odds${dateStr ? `?date=${dateStr}` : ''}`;
      const r = await fetch(url);
      const d = await r.json();
      setGames(d.games || []);
    } catch {
      // fallback to no-odds endpoint
      try {
        const url2 = `${API_URL}/baseball/games${dateStr ? `?date=${dateStr}` : ''}`;
        const r2 = await fetch(url2);
        const d2 = await r2.json();
        setGames(d2.games || []);
      } catch { setGames([]); }
    } finally { setGamesLoading(false); }
  };

  const loadAnalysis = async (game) => {
    setSelectedGame(game);
    setView('analysis');
    setAnalysisTab('breakdown');
    setAnalysis(null);
    setAnalysisError('');
    setGameOdds(game.odds || null);
    setAnalysisLoading(true);
    try {
      const r = await fetch(`${API_URL}/baseball/game/${game.game_pk}/analysis`);
      if (!r.ok) throw new Error(`${r.status}`);
      const d = await r.json();
      setAnalysis(d);
    } catch (e) {
      setAnalysisError(`Analysis failed: ${e.message}. The game may not have confirmed pitchers or lineups yet.`);
    } finally {
      setAnalysisLoading(false);
    }
  };

  useEffect(() => {
    if (view === 'games') loadGames(gamesDate || null);
  }, [view, gamesDate]);

  return (
    <div>
      {/* Sub-nav */}
      <div className="flex gap-2 mb-6 overflow-x-auto pb-1">
        {[
          { key: 'games', label: 'Today\'s Games' },
          { key: 'statcast', label: '🔬 Statcast' },
          { key: 'matchup', label: 'Matchup Lookup' },
          ...(selectedGame ? [{ key: 'analysis', label: `${selectedGame.away?.team_abbr} @ ${selectedGame.home?.team_abbr}` }] : []),
        ].map(tab => (
          <button key={tab.key} onClick={() => setView(tab.key)}
            className={`px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap ${
              view === tab.key
                ? tab.key === 'statcast' ? 'bg-orange-600 text-white' : 'bg-blue-600 text-white'
                : 'bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white'
            }`}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Games View ── */}
      {view === 'games' && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <input type="date" value={gamesDate || todayStr}
              onChange={e => setGamesDate(e.target.value)}
              className="bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-white" />
            <button onClick={() => loadGames(gamesDate || null)} className="px-4 py-2 bg-blue-600 rounded-xl text-sm font-medium">Refresh</button>
          </div>
          {gamesLoading ? (
            <div className="text-center py-20"><div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" /></div>
          ) : games.length === 0 ? (
            <div className="text-center py-20 text-zinc-500">No games found for this date</div>
          ) : (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {games.map(g => <GameCard key={g.game_pk} game={g} onSelect={loadAnalysis} />)}
            </div>
          )}
        </div>
      )}

      {/* ── Statcast View ── */}
      {view === 'statcast' && (
        <div>
          <div className="mb-5">
            <h2 className="text-lg font-bold text-white">Statcast Advanced</h2>
            <p className="text-xs text-zinc-500 mt-1">Barrel%, xSLG, bat speed, blast rates and HR probability models powered by Baseball Savant</p>
          </div>
          <SlateAdvancedPanel />
        </div>
      )}

      {/* ── Matchup View ── */}
      {view === 'matchup' && <QuickMatchup />}

      {/* ── Analysis View ── */}
      {view === 'analysis' && (
        <div>
          {analysisLoading && (
            <div className="text-center py-20">
              <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <div className="text-zinc-400">Building full game analysis...</div>
              <div className="text-zinc-600 text-sm mt-1">Fetching pitcher profiles, lineups, H2H matchups & weather</div>
            </div>
          )}
          {analysisError && !analysisLoading && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-4 text-red-400">{analysisError}</div>
          )}
          {analysis && !analysisLoading && (
            <div className="space-y-5">
              {/* Game header with live odds */}
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-5">
                <div className="flex items-center justify-between mb-1">
                  <div className="text-xs text-zinc-500">{analysis.venue?.name}</div>
                  <div className="text-xs text-zinc-500">{fmtTime(analysis.game_time)}</div>
                </div>
                <div className="flex items-center justify-around text-center mb-2">
                  <div>
                    <div className="text-2xl font-black">{analysis.away_team?.abbr}</div>
                    <div className="text-xs text-zinc-400">{analysis.away_team?.name}</div>
                    <div className="text-xs text-zinc-600">{analysis.away_team?.record}</div>
                  </div>
                  <div className="text-zinc-600 text-2xl font-bold">@</div>
                  <div>
                    <div className="text-2xl font-black">{analysis.home_team?.abbr}</div>
                    <div className="text-xs text-zinc-400">{analysis.home_team?.name}</div>
                    <div className="text-xs text-zinc-600">{analysis.home_team?.record}</div>
                  </div>
                </div>
                {gameOdds && <OddsLine odds={gameOdds} />}
              </div>

              {/* Analysis tabs */}
              <div className="flex gap-2 flex-wrap">
                {[
                  { key: 'breakdown', label: 'Full Breakdown', color: 'blue' },
                  { key: 'props', label: '★ Prop Sheet', color: 'purple' },
                  { key: 'hrtable', label: '🔥 HR Table', color: 'orange' },
                ].map(t => (
                  <button key={t.key} onClick={() => setAnalysisTab(t.key)}
                    className={`px-4 py-2 rounded-xl text-sm font-medium ${analysisTab === t.key
                      ? t.color === 'purple' ? 'bg-purple-600 text-white' : t.color === 'orange' ? 'bg-orange-600 text-white' : 'bg-blue-600 text-white'
                      : 'bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white'}`}>
                    {t.label}
                  </button>
                ))}
              </div>

              {analysisTab === 'breakdown' && (
                <div className="space-y-5">
                  <AnalysisSummary analysis={analysis.analysis} awayTeam={analysis.away_team} homeTeam={analysis.home_team} />
                  <div className="grid lg:grid-cols-2 gap-4">
                    <PitcherCard side="Away" pitcherData={analysis.pitchers?.away} teamName={analysis.away_team?.name} />
                    <PitcherCard side="Home" pitcherData={analysis.pitchers?.home} teamName={analysis.home_team?.name} />
                  </div>
                  <div className="grid sm:grid-cols-2 gap-4">
                    <WeatherCard weather={analysis.weather} />
                    <ParkCard park={analysis.park_factors} />
                  </div>
                  <div className="grid lg:grid-cols-2 gap-4">
                    <MatchupPanel
                      title={`${analysis.away_team?.abbr} Lineup`}
                      items={analysis.matchups?.away_batters_vs_home_pitcher}
                      pitcherName={analysis.pitchers?.home?.info?.name || 'Home SP'}
                    />
                    <MatchupPanel
                      title={`${analysis.home_team?.abbr} Lineup`}
                      items={analysis.matchups?.home_batters_vs_away_pitcher}
                      pitcherName={analysis.pitchers?.away?.info?.name || 'Away SP'}
                    />
                  </div>
                </div>
              )}

              {analysisTab === 'props' && <PropSheetPanel gamePk={analysis.game_pk} />}
              {analysisTab === 'hrtable' && <HRMatchupTable gamePk={analysis.game_pk} />}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
