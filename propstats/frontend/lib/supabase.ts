import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

// Create a single supabase client for interacting with your database
export const supabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null;

// Types for our database (expand as needed)
export type Player = {
  id: string;
  name: string;
  team: string;
  position: string;
};

export type PropBet = {
  id: string;
  player_id: string;
  stat_type: string;
  line: number;
  over_odds: number;
  under_odds: number;
  sportsbook: string;
  created_at: string;
};

export type UserSubscription = {
  id: string;
  user_id: string;
  status: 'active' | 'cancelled' | 'expired';
  plan: 'free' | 'premium' | 'pro';
  expires_at: string;
};
