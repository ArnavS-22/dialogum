"use client"

import { useState, useEffect } from "react";
import { LiquidButton } from "@/components/ui/liquid-glass-button";

interface MixedInitiativeScore {
  decision: string;
  expected_utility: number;
  confidence_normalized: number;
  attention_level: number;
  interruption_cost: number;
}

interface Proposition {
  id: number;
  text: string;
  reasoning: string;
  confidence: number | null;
  decay: number | null;
  created_at: string;
  updated_at: string;
  revision_group: string;
  version: number;
  observation_count: number;
  mixed_initiative_score: MixedInitiativeScore | null;
}

interface PropositionsResponse {
  propositions: Proposition[];
  total_count: number;
}

export default function PropositionsPage() {
  const [propositions, setPropositions] = useState<Proposition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    fetchPropositions();
  }, []);

  const fetchPropositions = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8000/api/propositions?limit=50');
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      const data: PropositionsResponse = await response.json();
      setPropositions(data.propositions);
      setTotalCount(data.total_count);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch propositions');
    } finally {
      setLoading(false);
    }
  };

  const getDecisionColor = (decision: string) => {
    switch (decision) {
      case 'autonomous_action':
        return 'text-green-400';
      case 'dialogue':
        return 'text-yellow-400';
      case 'no_action':
        return 'text-gray-400';
      default:
        return 'text-white';
    }
  };

  const getDecisionIcon = (decision: string) => {
    switch (decision) {
      case 'autonomous_action':
        return '🤖';
      case 'dialogue':
        return '💬';
      case 'no_action':
        return '⏸️';
      default:
        return '❓';
    }
  };

  const getConfidenceColor = (confidence: number | null) => {
    if (!confidence) return 'text-gray-400';
    if (confidence >= 8) return 'text-green-400';
    if (confidence >= 6) return 'text-yellow-400';
    return 'text-red-400';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-8">
        <div className="mx-auto max-w-6xl">
          <div className="flex items-center justify-center h-64">
            <div className="text-white text-xl">Loading propositions...</div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-8">
        <div className="mx-auto max-w-6xl">
          <div className="rounded-xl bg-red-500/20 p-6 backdrop-blur-sm border border-red-500/30">
            <h2 className="text-xl font-semibold text-red-400 mb-2">Error Loading Propositions</h2>
            <p className="text-red-300 mb-4">{error}</p>
            <LiquidButton onClick={fetchPropositions}>
              🔄 Retry
            </LiquidButton>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-8">
      <div className="mx-auto max-w-6xl">
        {/* Simple Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">
            GUM Propositions
          </h1>
          <p className="text-gray-300">
            {totalCount} propositions • Mixed-initiative decisions
          </p>
        </div>

        {/* Simple Stats */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="rounded-xl bg-white/10 p-4 backdrop-blur-sm">
            <div className="text-2xl font-bold text-white">{totalCount}</div>
            <div className="text-sm text-gray-300">Total</div>
          </div>
          <div className="rounded-xl bg-white/10 p-4 backdrop-blur-sm">
            <div className="text-2xl font-bold text-green-400">
              {propositions.filter(p => p.mixed_initiative_score?.decision === 'autonomous_action').length}
            </div>
            <div className="text-sm text-gray-300">Auto</div>
          </div>
          <div className="rounded-xl bg-white/10 p-4 backdrop-blur-sm">
            <div className="text-2xl font-bold text-yellow-400">
              {propositions.filter(p => p.mixed_initiative_score?.decision === 'dialogue').length}
            </div>
            <div className="text-sm text-gray-300">Dialogue</div>
          </div>
          <div className="rounded-xl bg-white/10 p-4 backdrop-blur-sm">
            <div className="text-2xl font-bold text-blue-400">
              {Math.round(propositions.reduce((acc, p) => acc + (p.confidence || 0), 0) / propositions.length * 10) / 10}
            </div>
            <div className="text-sm text-gray-300">Avg Conf</div>
          </div>
        </div>

        {/* Propositions - Simple Cards */}
        <div className="space-y-4">
          {propositions.map((proposition) => (
            <div
              key={proposition.id}
              className="rounded-xl bg-white/10 p-6 backdrop-blur-sm border border-white/20 hover:bg-white/15 transition-all duration-300"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-white mb-2">
                    {proposition.text}
                  </h3>
                </div>
                <div className={`text-2xl ${getConfidenceColor(proposition.confidence)}`}>
                  {proposition.confidence || '?'}/10
                </div>
              </div>

              {proposition.mixed_initiative_score && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <span className={`text-lg ${getDecisionColor(proposition.mixed_initiative_score.decision)}`}>
                      {getDecisionIcon(proposition.mixed_initiative_score.decision)} {proposition.mixed_initiative_score.decision}
                    </span>
                    <span className="text-sm text-gray-300">
                      EU: {proposition.mixed_initiative_score.expected_utility}
                    </span>
                    <span className="text-sm text-gray-300">
                      {proposition.observation_count} obs
                    </span>
                  </div>
                  <div className="text-xs text-gray-400">
                    {new Date(proposition.created_at).toLocaleString()}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {propositions.length === 0 && (
          <div className="text-center py-16">
            <div className="text-6xl mb-4">🧠</div>
            <h3 className="text-xl font-semibold text-white mb-2">No Propositions Found</h3>
            <p className="text-gray-300 mb-6">
              Run GUM to start generating propositions about user behavior
            </p>
            <LiquidButton onClick={fetchPropositions}>
              🔄 Refresh
            </LiquidButton>
          </div>
        )}
      </div>
    </div>
  );
}