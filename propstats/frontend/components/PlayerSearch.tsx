'use client';

import { useState, useEffect } from 'react';
import { Search, Loader2 } from 'lucide-react';

interface Player {
  id: number;
  name: string;
  team?: string;
}

interface PlayerSearchProps {
  onPlayerSelect: (player: Player) => void;
}

export default function PlayerSearch({ onPlayerSelect }: PlayerSearchProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Player[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (query.length < 2) {
      setResults([]);
      return;
    }

    const searchPlayers = async () => {
      setLoading(true);
      setError('');

      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${apiUrl}/players/search?q=${encodeURIComponent(query)}`);

        if (!response.ok) {
          throw new Error('Failed to search players');
        }

        const data = await response.json();
        setResults(data.players || []);
      } catch (err) {
        setError('Error searching players. Make sure the backend is running.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    const debounce = setTimeout(searchPlayers, 300);
    return () => clearTimeout(debounce);
  }, [query]);

  const handleSelectPlayer = (player: Player) => {
    onPlayerSelect(player);
    setQuery(player.name);
    setResults([]);
  };

  return (
    <div className="relative">
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for any NBA player..."
          className="w-full pl-12 pr-4 py-4 bg-white/10 border border-white/20 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
        />
        {loading && (
          <Loader2 className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-purple-400 animate-spin" />
        )}
      </div>

      {error && (
        <div className="mt-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {results.length > 0 && (
        <div className="absolute w-full mt-2 bg-slate-900 border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50">
          {results.map((player) => (
            <button
              key={player.id}
              onClick={() => handleSelectPlayer(player)}
              className="w-full px-4 py-3 text-left hover:bg-white/5 transition-colors border-b border-white/5 last:border-b-0"
            >
              <div className="font-semibold text-white">{player.name}</div>
              {player.team && (
                <div className="text-sm text-slate-400">{player.team}</div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
