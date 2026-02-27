"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getSearchResult,
  addToWatchlist,
  retrySearch,
  type SearchResult,
} from "@/lib/api";
import ScoreBadge from "@/components/ScoreBadge";
import EvidenceCard from "@/components/EvidenceCard";

export default function ResultsPage() {
  const { markId } = useParams<{ markId: string }>();
  const [data, setData] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [watchlistAdded, setWatchlistAdded] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const result = await getSearchResult(markId);
      setData(result);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
      return null;
    }
  }, [markId]);

  useEffect(() => {
    let cancelled = false;
    let timer: NodeJS.Timeout;

    async function poll() {
      const result = await fetchData();
      if (cancelled) return;

      // Keep polling if any job is still pending or running
      const stillWorking = result?.jobs.some(
        (j) => j.status === "pending" || j.status === "running"
      );
      if (stillWorking) {
        timer = setTimeout(poll, 3000);
      }
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [fetchData]);

  async function handleAddToWatchlist() {
    try {
      await addToWatchlist(markId);
      setWatchlistAdded(true);
    } catch {
      // Might already be on watchlist (409)
      setWatchlistAdded(true);
    }
  }

  async function handleRetry() {
    await retrySearch(markId);
    fetchData();
  }

  if (error) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12">
        <p className="text-red-600">{error}</p>
        <Link href="/" className="mt-4 text-blue-600 hover:underline">
          Back to search
        </Link>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12">
        <div className="animate-pulse text-gray-400">Loading...</div>
      </main>
    );
  }

  const anyPending = data.jobs.some(
    (j) => j.status === "pending" || j.status === "running"
  );
  const anyFailed = data.jobs.some((j) => j.status === "failed");

  const authEvidence = data.evidence.filter(
    (e) => e.source_type === "authoritative"
  );
  const secEvidence = data.evidence.filter(
    (e) => e.source_type === "secondary"
  );

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          &larr; New search
        </Link>
        <Link
          href="/watchlist"
          className="text-sm text-blue-600 hover:underline"
        >
          Watchlist
        </Link>
      </div>

      {/* Brand + Score */}
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">{data.mark.name}</h1>
        <ScoreBadge score={data.score} />
      </div>

      {/* Job status */}
      {anyPending && (
        <div className="mb-4 rounded-lg bg-blue-50 border border-blue-200 px-4 py-3 text-sm text-blue-700">
          Searching sources... results will appear as they come in.
        </div>
      )}
      {anyFailed && !anyPending && (
        <div className="mb-4 flex items-center justify-between rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          <span>Some sources failed to respond.</span>
          <button
            onClick={handleRetry}
            className="rounded bg-red-100 px-3 py-1 text-xs font-medium hover:bg-red-200"
          >
            Retry
          </button>
        </div>
      )}

      {/* Score breakdown */}
      {data.score.factors.length > 0 && (
        <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-semibold text-gray-600 uppercase tracking-wide">
            Score Breakdown
          </h2>
          <div className="space-y-1">
            {data.score.factors.map((f, i) => (
              <div key={i} className="flex justify-between text-sm">
                <span className="text-gray-700">
                  {f.source.replace(/_/g, " ")}
                  {f.status ? ` (${f.status})` : ""}
                </span>
                <span className="font-medium text-gray-900">
                  +{f.points} pts
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Authoritative Evidence */}
      {authEvidence.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-3 text-sm font-semibold text-gray-600 uppercase tracking-wide">
            Authoritative Evidence
          </h2>
          <div className="space-y-3">
            {authEvidence.map((e) => (
              <EvidenceCard key={e.id} item={e} markName={data.mark.name} />
            ))}
          </div>
        </section>
      )}

      {/* Secondary Evidence */}
      {secEvidence.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-3 text-sm font-semibold text-gray-600 uppercase tracking-wide">
            Secondary Sources (informational)
          </h2>
          <div className="space-y-3">
            {secEvidence.map((e) => (
              <EvidenceCard key={e.id} item={e} markName={data.mark.name} />
            ))}
          </div>
        </section>
      )}

      {/* No evidence */}
      {data.evidence.length === 0 && !anyPending && (
        <p className="text-gray-500 py-8 text-center">
          No evidence found for this brand.
        </p>
      )}

      {/* Actions */}
      <div className="mt-8 flex justify-center">
        <button
          onClick={handleAddToWatchlist}
          disabled={watchlistAdded}
          className="rounded-lg bg-gray-900 px-6 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {watchlistAdded ? "Added to Watchlist" : "Add to Watchlist"}
        </button>
      </div>
    </main>
  );
}
