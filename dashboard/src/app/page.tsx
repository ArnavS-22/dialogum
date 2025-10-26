"use client"

import { useState, useEffect } from "react";
import { LiquidButton } from "@/components/ui/liquid-glass-button";
import { BorderTrail } from "@/components/ui/border-trail";

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

    // Lightweight polling to auto-refresh while CLI runs
    let isCancelled = false;
    const POLL_MS = 3000;

    const silentRefresh = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/propositions?limit=50', {
          cache: 'no-store',
        });
        if (!response.ok) return;
        const data: PropositionsResponse = await response.json();
        if (!isCancelled) {
          setPropositions(data.propositions);
          setTotalCount(data.total_count);
        }
      } catch {
        // swallow errors in background polling to avoid UI interruptions
      }
    };

    const id = setInterval(silentRefresh, POLL_MS);
    return () => {
      isCancelled = true;
      clearInterval(id);
    };
  }, []);

  const fetchPropositions = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8000/api/propositions?limit=50', {
        cache: 'no-store',
      });
      
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

  const getConfidenceColor = (confidence: number | null) => {
    if (!confidence) return 'text-gray-400';
    if (confidence >= 8) return 'text-green-400';
    if (confidence >= 6) return 'text-yellow-400';
    return 'text-red-400';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-black p-8">
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
      <div className="min-h-screen bg-black p-8">
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
    <div className="min-h-screen bg-black p-8">
      <div className="mx-auto max-w-6xl">
        {/* Simple Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">
            GUM Propositions
          </h1>
          <p className="text-gray-300">
            {totalCount} propositions • Confidence overview
          </p>
        </div>

        {/* Simple Stats */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="relative rounded-xl bg-white/10 p-4 backdrop-blur-sm">
            <BorderTrail size={40} />
            <div className="text-2xl font-bold text-white">{totalCount}</div>
            <div className="text-sm text-gray-300">Total</div>
          </div>
          <div className="relative rounded-xl bg-white/10 p-4 backdrop-blur-sm">
            <BorderTrail size={40} />
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
              className="relative rounded-xl bg-white/10 p-6 backdrop-blur-sm border border-white/20 hover:bg-white/15 transition-all duration-300"
            >
              <BorderTrail size={60} />
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

              <div className="flex items-center justify-between mt-4">
                <div className="flex items-center gap-4">
                  <span className="text-sm text-gray-300">
                    {proposition.observation_count} observations
                  </span>
                </div>
                <div className="text-xs text-gray-400">
                  {new Date(proposition.created_at).toLocaleString()}
                </div>
              </div>
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