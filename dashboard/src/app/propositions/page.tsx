"use client"

import { useState, useEffect } from "react";
import { LiquidButton, MetalButton } from "@/components/ui/liquid-glass-button";

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
      const response = await fetch('http://localhost:8000/api/propositions?limit=20');
      
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
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">
            GUM Propositions
          </h1>
          <p className="text-gray-300">
            {totalCount} propositions found • Mixed-initiative decisions with liquid glass interface
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="rounded-xl bg-white/10 p-4 backdrop-blur-sm">
            <div className="text-2xl font-bold text-white">{totalCount}</div>
            <div className="text-sm text-gray-300">Total Propositions</div>
          </div>
          <div className="rounded-xl bg-white/10 p-4 backdrop-blur-sm">
            <div className="text-2xl font-bold text-green-400">
              {propositions.filter(p => p.mixed_initiative_score?.decision === 'autonomous_action').length}
            </div>
            <div className="text-sm text-gray-300">Autonomous Actions</div>
          </div>
          <div className="rounded-xl bg-white/10 p-4 backdrop-blur-sm">
            <div className="text-2xl font-bold text-yellow-400">
              {propositions.filter(p => p.mixed_initiative_score?.decision === 'dialogue').length}
            </div>
            <div className="text-sm text-gray-300">Dialogue Triggers</div>
          </div>
          <div className="rounded-xl bg-white/10 p-4 backdrop-blur-sm">
            <div className="text-2xl font-bold text-blue-400">
              {Math.round(propositions.reduce((acc, p) => acc + (p.confidence || 0), 0) / propositions.length * 10) / 10}
            </div>
            <div className="text-sm text-gray-300">Avg Confidence</div>
          </div>
        </div>

        {/* Propositions Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {propositions.map((proposition) => (
            <div
              key={proposition.id}
              className="rounded-xl bg-white/10 p-6 backdrop-blur-sm border border-white/20 hover:bg-white/15 transition-all duration-300"
            >
              {/* Proposition Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-white mb-2 line-clamp-2">
                    {proposition.text}
                  </h3>
                  <div className="flex items-center gap-4 text-sm text-gray-300">
                    <span>ID: {proposition.id}</span>
                    <span>v{proposition.version}</span>
                    <span>{proposition.observation_count} obs</span>
                  </div>
                </div>
                <div className={`text-2xl ${getConfidenceColor(proposition.confidence)}`}>
                  {proposition.confidence || '?'}/10
                </div>
              </div>

              {/* Reasoning */}
              <div className="mb-4">
                <p className="text-sm text-gray-300 line-clamp-3">
                  {proposition.reasoning}
                </p>
              </div>

              {/* Mixed-Initiative Score */}
              {proposition.mixed_initiative_score && (
                <div className="mb-4 p-3 rounded-lg bg-white/5 border border-white/10">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-white">Mixed-Initiative Decision</span>
                    <span className={`text-lg ${getDecisionColor(proposition.mixed_initiative_score.decision)}`}>
                      {getDecisionIcon(proposition.mixed_initiative_score.decision)} {proposition.mixed_initiative_score.decision}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-gray-400">EU:</span>
                      <span className="text-white ml-1">{proposition.mixed_initiative_score.expected_utility}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">Attention:</span>
                      <span className="text-white ml-1">{proposition.mixed_initiative_score.attention_level}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">Confidence:</span>
                      <span className="text-white ml-1">{proposition.mixed_initiative_score.confidence_normalized}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">Interruption:</span>
                      <span className="text-white ml-1">{proposition.mixed_initiative_score.interruption_cost}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center justify-between">
                <div className="text-xs text-gray-400">
                  {new Date(proposition.created_at).toLocaleString()}
                </div>
                <div className="flex gap-2">
                  <LiquidButton size="sm">
                    📖 Details
                  </LiquidButton>
                  <MetalButton variant="primary" className="text-xs px-3 py-1">
                    🎯 Action
                  </MetalButton>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Load More */}
        {propositions.length < totalCount && (
          <div className="mt-8 text-center">
            <LiquidButton onClick={fetchPropositions}>
              📥 Load More Propositions
            </LiquidButton>
          </div>
        )}

        {/* Empty State */}
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
