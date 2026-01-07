'use client';

import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Target, Loader2, ChevronDown } from 'lucide-react';

interface Player {
  id: number;
  name: string;
}

interface StatsAnalysisProps {
  player: Player;
}

const STAT_OPTIONS = [
  { value: 'points', label: 'Points' },
  { value: 'rebounds', label: 'Rebounds' },
  { value: 'assists', label: 'Assists' },
  { value: 'threes', label: '3-Pointers' },
  { value: 'steals', label: 'Steals' },
  { value: 'blocks', label: 'Blocks' },
  { value: 'pra', label: 'PRA (Pts+Reb+Ast)' },
];

export default function StatsAnalysis({ player }: StatsAnalysisProps) {
  const [stat, setStat] = useState('points');
  const [line, setLine] = useState('25.5');
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (player && stat && line) {
      fetchAnalysis();
    }
  }, [player, stat, line]);

  const fetchAnalysis = async () => {
    setLoading(true);
    setError('');

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(
        `${apiUrl}/players/${player.id}/analysis?stat=${stat}&line=${line}`
      );

      if (!response.ok) {
        throw new Error('Failed to fetch analysis');
      }

      const data = await response.json();
      setAnalysis(data);
    } catch (err) {
      setError('Error fetching analysis. Make sure the backend is running.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const getHitRateColor = (rate: number) => {
    if (rate >= 70) return 'text-green-400';
    if (rate >= 50) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getRecommendation = () => {
    if (!analysis?.hit_rates) return null;

    const recent = analysis.hit_rates.last_5;
    if (recent >= 80) return { text: 'Strong Over', color: 'bg-green-500' };
    if (recent >= 60) return { text: 'Lean Over', color: 'bg-green-600' };
    if (recent <= 20) return { text: 'Strong Under', color: 'bg-red-500' };
    if (recent <= 40) return { text: 'Lean Under', color: 'bg-red-600' };
    return { text: 'No Clear Edge', color: 'bg-gray-600' };
  };

  if (loading) {
    return (
      <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl p-8">
        <div className="flex items-center justify-center gap-3">
          <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
          <span className="text-white">Analyzing {player.name}'s performance...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl p-8">
        <div className="text-red-400">{error}</div>
      </div>
    );
  }

  const recommendation = getRecommendation();

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Player
            </label>
            <div className="px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white">
              {player.name}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Stat Type
            </label>
            <div className="relative">
              <select
                value={stat}
                onChange={(e) => setStat(e.target.value)}
                className="w-full appearance-none px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {STAT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value} className="bg-slate-900">
                    {option.label}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 pointer-events-none" />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Betting Line
            </label>
            <input
              type="number"
              step="0.5"
              value={line}
              onChange={(e) => setLine(e.target.value)}
              className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>
        </div>
      </div>

      {/* Analysis Results */}
      {analysis && (
        <>
          {/* Recommendation */}
          {recommendation && (
            <div className={`${recommendation.color} rounded-2xl p-6 text-white`}>
              <div className="flex items-center gap-3">
                <Target className="w-6 h-6" />
                <div>
                  <div className="font-semibold text-lg">{recommendation.text}</div>
                  <div className="text-sm opacity-90">
                    Based on recent performance trends
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Hit Rates */}
          <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl p-6">
            <h3 className="text-xl font-bold text-white mb-6">Hit Rate Analysis</h3>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {analysis.hit_rates && Object.entries(analysis.hit_rates).map(([key, value]: [string, any]) => (
                <div key={key} className="bg-white/5 rounded-xl p-4 border border-white/10">
                  <div className="text-sm text-slate-400 mb-1 uppercase">
                    {key.replace('_', ' ')}
                  </div>
                  <div className={`text-3xl font-bold ${getHitRateColor(value)}`}>
                    {value}%
                  </div>
                  <div className="text-xs text-slate-500 mt-1">
                    {value >= 50 ? 'Over' : 'Under'} trend
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Game Logs */}
          {analysis.game_logs && analysis.game_logs.length > 0 && (
            <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl p-6">
              <h3 className="text-xl font-bold text-white mb-6">Recent Game Logs</h3>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-white/10">
                      <th className="text-left py-3 px-4 text-sm font-semibold text-slate-300">Date</th>
                      <th className="text-left py-3 px-4 text-sm font-semibold text-slate-300">Opponent</th>
                      <th className="text-left py-3 px-4 text-sm font-semibold text-slate-300">Value</th>
                      <th className="text-left py-3 px-4 text-sm font-semibold text-slate-300">Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.game_logs.slice(0, 10).map((game: any, idx: number) => (
                      <tr key={idx} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                        <td className="py-3 px-4 text-sm text-white">{game.date}</td>
                        <td className="py-3 px-4 text-sm text-slate-300">{game.opponent || 'N/A'}</td>
                        <td className="py-3 px-4 text-sm font-semibold text-white">{game.value}</td>
                        <td className="py-3 px-4">
                          {game.hit ? (
                            <span className="inline-flex items-center gap-1 text-green-400">
                              <TrendingUp className="w-4 h-4" />
                              Over
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-red-400">
                              <TrendingDown className="w-4 h-4" />
                              Under
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
