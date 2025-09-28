"use client"

import { useState, useEffect } from "react";
import { LiquidButton } from "@/components/ui/liquid-glass-button";
import { BorderTrail } from "@/components/ui/border-trail";
import { Navigation } from "@/components/navigation";

interface Memory {
  id: number;
  category: "workflow" | "preference" | "habit";
  generalization: string;
  supporting_prop_ids: number[];
  rationale: string;
  first_seen: string;
  last_seen: string;
  tags: string[];
  created_at: string;
  updated_at: string;
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
  mixed_initiative_score: any | null;
}

interface MemoriesResponse {
  memories: Memory[];
  total_count: number;
}

export default function MemoryPage() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [expandedMemory, setExpandedMemory] = useState<number | null>(null);
  const [supportingPropositions, setSupportingPropositions] = useState<Map<number, Proposition[]>>(new Map());
  const [loadingPropositions, setLoadingPropositions] = useState<Set<number>>(new Set());

  useEffect(() => {
    fetchMemories();

    // Auto-refresh every 10 seconds
    const interval = setInterval(fetchMemories, 10000);
    return () => clearInterval(interval);
  }, [selectedCategory]);

  const fetchMemories = async () => {
    try {
      setLoading(true);
      const categoryParam = selectedCategory === "all" ? "" : `?category=${selectedCategory}`;
      const response = await fetch(`http://localhost:8000/api/memories${categoryParam}`, {
        cache: 'no-store',
      });
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      const data: MemoriesResponse = await response.json();
      setMemories(data.memories);
      setTotalCount(data.total_count);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch memories');
    } finally {
      setLoading(false);
    }
  };

  const fetchSupportingPropositions = async (memoryId: number) => {
    const id = Number(memoryId);
    // Don't fetch if already loaded or currently loading
    if (supportingPropositions.has(id) || loadingPropositions.has(id)) {
      return;
    }

    try {
      setLoadingPropositions(prev => new Set(prev).add(id));
      
      const response = await fetch(`http://localhost:8000/api/memories/${id}/propositions`, {
        cache: 'no-store',
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      setSupportingPropositions(prev => new Map(prev).set(id, data.propositions));
    } catch (err) {
      console.error(`Failed to fetch propositions for memory ${id}:`, err);
    } finally {
      setLoadingPropositions(prev => {
        const newSet = new Set(prev);
        newSet.delete(id);
        return newSet;
      });
    }
  };

  const handleMemoryExpand = (memoryId: number) => {
    const id = Number(memoryId);
    if (expandedMemory === id) {
      setExpandedMemory(null);
    } else {
      setExpandedMemory(id);
      fetchSupportingPropositions(id);
    }
  };

  const generateMemoryManually = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/memories/generate', {
        method: 'POST',
      });
      
      if (!response.ok) {
        throw new Error(`Generation failed: ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.status === "success") {
        // Refresh memories after generation
        await fetchMemories();
      }
      
      return result;
    } catch (err) {
      console.error('Memory generation failed:', err);
      throw err;
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'workflow': return '⚙️';
      case 'preference': return '❤️';
      case 'habit': return '🔄';
      default: return '💭';
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'workflow': return 'text-blue-400';
      case 'preference': return 'text-pink-400';
      case 'habit': return 'text-green-400';
      default: return 'text-gray-400';
    }
  };

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateString;
    }
  };

  if (loading && memories.length === 0) {
    return (
      <>
        <Navigation />
        <div className="flex items-center justify-center h-64">
          <div className="text-white text-xl">Loading memories...</div>
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <Navigation />
        <div className="rounded-xl bg-red-500/20 p-6 backdrop-blur-sm border border-red-500/30">
          <h2 className="text-xl font-semibold text-red-400 mb-2">Error Loading Memories</h2>
          <p className="text-red-300 mb-4">{error}</p>
          <LiquidButton onClick={fetchMemories}>
            🔄 Retry
          </LiquidButton>
        </div>
      </>
    );
  }

  return (
    <>
      <Navigation />
      
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-white mb-2">
          Long-term Memory
        </h1>
        <p className="text-gray-300">
          {totalCount} memories • Generated from user behavior patterns
        </p>
      </div>

      {/* Category Filter & Actions */}
      <div className="mb-8 flex items-center justify-between">
        <div className="flex gap-4">
          {["all", "workflow", "preference", "habit"].map((category) => (
            <button
              key={category}
              onClick={() => setSelectedCategory(category)}
              className={`
                relative px-4 py-2 rounded-lg transition-all duration-300
                ${selectedCategory === category
                  ? "bg-white/20 text-white backdrop-blur-sm"
                  : "bg-white/5 text-gray-300 hover:bg-white/10"
                }
              `}
            >
              {selectedCategory === category && <BorderTrail size={30} />}
              <span className="relative z-10 flex items-center gap-2 capitalize">
                {category !== "all" && getCategoryIcon(category)}
                {category}
              </span>
            </button>
          ))}
        </div>
        
        <LiquidButton onClick={generateMemoryManually}>
          ⚡ Generate Memory
        </LiquidButton>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="relative rounded-xl bg-white/10 p-4 backdrop-blur-sm">
          <BorderTrail size={40} />
          <div className="text-2xl font-bold text-white">{totalCount}</div>
          <div className="text-sm text-gray-300">Total Memories</div>
        </div>
        <div className="relative rounded-xl bg-white/10 p-4 backdrop-blur-sm">
          <BorderTrail size={40} />
          <div className="text-2xl font-bold text-blue-400">
            {memories.filter(m => m.category === 'workflow').length}
          </div>
          <div className="text-sm text-gray-300">Workflows</div>
        </div>
        <div className="relative rounded-xl bg-white/10 p-4 backdrop-blur-sm">
          <BorderTrail size={40} />
          <div className="text-2xl font-bold text-pink-400">
            {memories.filter(m => m.category === 'preference').length}
          </div>
          <div className="text-sm text-gray-300">Preferences</div>
        </div>
        <div className="relative rounded-xl bg-white/10 p-4 backdrop-blur-sm">
          <BorderTrail size={40} />
          <div className="text-2xl font-bold text-green-400">
            {memories.filter(m => m.category === 'habit').length}
          </div>
          <div className="text-sm text-gray-300">Habits</div>
        </div>
      </div>

      {/* Memory Cards */}
      <div className="space-y-4">
        {memories.map((memory) => (
          <div
            key={memory.id}
            className="relative rounded-xl bg-white/10 p-6 backdrop-blur-sm border border-white/20 hover:bg-white/15 transition-all duration-300"
          >
            <BorderTrail size={60} />
            
            {/* Memory Header */}
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <span className={`text-2xl ${getCategoryColor(memory.category)}`}>
                  {getCategoryIcon(memory.category)}
                </span>
                <div>
                  <span className={`text-sm font-medium ${getCategoryColor(memory.category)} uppercase tracking-wide`}>
                    {memory.category}
                  </span>
                  <h3 className="text-lg font-semibold text-white mt-1">
                    {memory.generalization}
                  </h3>
                </div>
              </div>
              <button
                onClick={() => handleMemoryExpand(memory.id)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                {expandedMemory === Number(memory.id) ? "🔼" : "🔽"}
              </button>
            </div>

            {/* Tags */}
            <div className="flex flex-wrap gap-2 mb-4">
              {memory.tags.map((tag) => (
                <span
                  key={tag}
                  className="px-2 py-1 bg-white/10 rounded-md text-xs text-gray-300"
                >
                  #{tag}
                </span>
              ))}
            </div>

            {/* Supporting Propositions Count */}
            <div className="text-sm text-gray-400 mb-4">
              Based on {memory.supporting_prop_ids.length} propositions
              • First seen: {formatDate(memory.first_seen)}
              • Last seen: {formatDate(memory.last_seen)}
            </div>

            {/* Expanded Details */}
            {expandedMemory === Number(memory.id) && (
              <div className="border-t border-white/20 pt-4 mt-4">
                <h4 className="text-sm font-medium text-white mb-2">Rationale:</h4>
                <p className="text-gray-300 text-sm mb-4">{memory.rationale}</p>
                
                {/* Supporting Propositions */}
                <div className="mb-4">
                  <h4 className="text-sm font-medium text-white mb-2">
                    Supporting Propositions ({memory.supporting_prop_ids.length}):
                  </h4>
                  
                  {loadingPropositions.has(Number(memory.id)) ? (
                    <div className="text-gray-400 text-sm">Loading propositions...</div>
                  ) : supportingPropositions.has(Number(memory.id)) ? (
                    <div className="space-y-3">
                      {supportingPropositions.get(Number(memory.id))?.map((prop) => (
                        <div key={prop.id} className="bg-white/5 rounded-lg p-3 border border-white/10">
                          <div className="flex items-start justify-between mb-2">
                            <span className="text-xs text-gray-400">Proposition #{prop.id}</span>
                            <span className="text-xs text-gray-400">
                              {formatDate(prop.created_at)}
                            </span>
                          </div>
                          <p className="text-gray-200 text-sm mb-2">{prop.text}</p>
                          <p className="text-gray-400 text-xs">{prop.reasoning}</p>
                          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                            <span>Confidence: {prop.confidence || 'N/A'}</span>
                            <span>Decay: {prop.decay || 'N/A'}</span>
                            <span>Version: {prop.version}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-gray-400 text-sm">No propositions found</div>
                  )}
                </div>
                
                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div>
                    <span className="text-gray-400">Created:</span>
                    <div className="text-white">{formatDate(memory.created_at)}</div>
                  </div>
                  <div>
                    <span className="text-gray-400">Last Updated:</span>
                    <div className="text-white">{formatDate(memory.updated_at)}</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Empty State */}
      {memories.length === 0 && (
        <div className="text-center py-16">
          <div className="text-6xl mb-4">💭</div>
          <h3 className="text-xl font-semibold text-white mb-2">No Memories Found</h3>
          <p className="text-gray-300 mb-6">
            Run GUM with 30+ propositions to generate long-term memories, or try generating manually
          </p>
          <LiquidButton onClick={generateMemoryManually}>
            ⚡ Generate Memory
          </LiquidButton>
        </div>
      )}
    </>
  );
}
