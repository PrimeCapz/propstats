'use client';

import { X, Check, Zap, TrendingUp, BarChart3, Crown } from 'lucide-react';

interface UpgradePromptProps {
  onClose: () => void;
}

export default function UpgradePrompt({ onClose }: UpgradePromptProps) {
  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-gradient-to-br from-slate-900 to-purple-900 border border-white/10 rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-8">
          {/* Header */}
          <div className="flex items-start justify-between mb-8">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl">
                <Crown className="w-8 h-8 text-white" />
              </div>
              <div>
                <h2 className="text-3xl font-bold text-white">Upgrade to Pro</h2>
                <p className="text-slate-300">Unlock unlimited access and premium features</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/10 rounded-lg transition-colors"
            >
              <X className="w-6 h-6 text-slate-400" />
            </button>
          </div>

          {/* Pricing Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            {/* Free Tier */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-6">
              <div className="text-sm font-semibold text-slate-400 mb-2">FREE</div>
              <div className="text-4xl font-bold text-white mb-4">$0<span className="text-lg text-slate-400">/mo</span></div>
              <ul className="space-y-3 mb-6">
                <li className="flex items-center gap-2 text-slate-300">
                  <Check className="w-5 h-5 text-green-400" />
                  <span>10 searches/day</span>
                </li>
                <li className="flex items-center gap-2 text-slate-300">
                  <Check className="w-5 h-5 text-green-400" />
                  <span>Basic hit rates</span>
                </li>
                <li className="flex items-center gap-2 text-slate-300">
                  <Check className="w-5 h-5 text-green-400" />
                  <span>Last 10 games</span>
                </li>
              </ul>
              <button className="w-full py-3 bg-white/10 text-white rounded-lg font-semibold">
                Current Plan
              </button>
            </div>

            {/* Premium Tier */}
            <div className="bg-gradient-to-br from-purple-600 to-pink-600 rounded-xl p-6 transform scale-105 shadow-2xl">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-semibold text-purple-100">PREMIUM</div>
                <div className="px-2 py-1 bg-white/20 rounded text-xs font-bold text-white">
                  POPULAR
                </div>
              </div>
              <div className="text-4xl font-bold text-white mb-4">$19<span className="text-lg text-purple-100">/mo</span></div>
              <ul className="space-y-3 mb-6">
                <li className="flex items-center gap-2 text-white">
                  <Check className="w-5 h-5 text-white" />
                  <span>Unlimited searches</span>
                </li>
                <li className="flex items-center gap-2 text-white">
                  <Check className="w-5 h-5 text-white" />
                  <span>Advanced analytics</span>
                </li>
                <li className="flex items-center gap-2 text-white">
                  <Check className="w-5 h-5 text-white" />
                  <span>Full season history</span>
                </li>
                <li className="flex items-center gap-2 text-white">
                  <Check className="w-5 h-5 text-white" />
                  <span>Line shopping alerts</span>
                </li>
                <li className="flex items-center gap-2 text-white">
                  <Check className="w-5 h-5 text-white" />
                  <span>Priority support</span>
                </li>
              </ul>
              <button className="w-full py-3 bg-white text-purple-600 rounded-lg font-bold hover:bg-gray-100 transition-colors">
                Start 7-Day Trial
              </button>
            </div>

            {/* Pro Tier */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-6">
              <div className="text-sm font-semibold text-slate-400 mb-2">PRO</div>
              <div className="text-4xl font-bold text-white mb-4">$39<span className="text-lg text-slate-400">/mo</span></div>
              <ul className="space-y-3 mb-6">
                <li className="flex items-center gap-2 text-slate-300">
                  <Check className="w-5 h-5 text-green-400" />
                  <span>Everything in Premium</span>
                </li>
                <li className="flex items-center gap-2 text-slate-300">
                  <Check className="w-5 h-5 text-green-400" />
                  <span>API access</span>
                </li>
                <li className="flex items-center gap-2 text-slate-300">
                  <Check className="w-5 h-5 text-green-400" />
                  <span>Custom alerts</span>
                </li>
                <li className="flex items-center gap-2 text-slate-300">
                  <Check className="w-5 h-5 text-green-400" />
                  <span>Betting syndicates</span>
                </li>
                <li className="flex items-center gap-2 text-slate-300">
                  <Check className="w-5 h-5 text-green-400" />
                  <span>White-label option</span>
                </li>
              </ul>
              <button className="w-full py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg font-semibold hover:from-purple-700 hover:to-pink-700 transition-all">
                Contact Sales
              </button>
            </div>
          </div>

          {/* Features Comparison */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-xl font-bold text-white mb-4">Why Upgrade?</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-purple-500/20 rounded-lg">
                  <Zap className="w-5 h-5 text-purple-400" />
                </div>
                <div>
                  <div className="font-semibold text-white mb-1">Unlimited Access</div>
                  <div className="text-sm text-slate-400">
                    Research as many props as you need, no daily limits
                  </div>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="p-2 bg-blue-500/20 rounded-lg">
                  <TrendingUp className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <div className="font-semibold text-white mb-1">Advanced Analytics</div>
                  <div className="text-sm text-slate-400">
                    Deeper insights with home/away splits, matchup history
                  </div>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="p-2 bg-green-500/20 rounded-lg">
                  <BarChart3 className="w-5 h-5 text-green-400" />
                </div>
                <div>
                  <div className="font-semibold text-white mb-1">Line Shopping</div>
                  <div className="text-sm text-slate-400">
                    Compare odds across 20+ sportsbooks automatically
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Note */}
          <div className="mt-6 text-center text-sm text-slate-400">
            <p>All plans include a 7-day money-back guarantee. Cancel anytime.</p>
            <p className="mt-2">
              <span className="text-purple-400">🔒</span> Secure payment via Stripe
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
