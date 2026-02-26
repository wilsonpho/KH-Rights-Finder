"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getWatchlist, type WatchlistEntry } from "@/lib/api";
import WatchlistTable from "@/components/WatchlistTable";

export default function WatchlistPage() {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const data = await getWatchlist();
      setEntries(data);
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Watchlist</h1>
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          &larr; Search
        </Link>
      </div>

      {loading ? (
        <div className="animate-pulse text-gray-400 py-12 text-center">
          Loading...
        </div>
      ) : (
        <WatchlistTable entries={entries} onRefresh={fetchData} />
      )}
    </main>
  );
}
