"use client";

import Link from "next/link";
import type { WatchlistEntry } from "@/lib/api";
import { removeFromWatchlist, createSearch } from "@/lib/api";
import ScoreBadge from "./ScoreBadge";

interface Props {
  entries: WatchlistEntry[];
  onRefresh: () => void;
}

export default function WatchlistTable({ entries, onRefresh }: Props) {
  async function handleRemove(entryId: string) {
    await removeFromWatchlist(entryId);
    onRefresh();
  }

  async function handleRecheck(markName: string) {
    await createSearch(markName);
    onRefresh();
  }

  if (entries.length === 0) {
    return (
      <p className="text-center text-gray-500 py-12">
        No brands on your watchlist yet. Search for a brand and add it.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-gray-200 text-gray-600">
          <tr>
            <th className="py-3 pr-4 font-medium">Brand</th>
            <th className="py-3 pr-4 font-medium">Score</th>
            <th className="py-3 pr-4 font-medium">Last Checked</th>
            <th className="py-3 pr-4 font-medium">Interval</th>
            <th className="py-3 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {entries.map((entry) => (
            <tr key={entry.id}>
              <td className="py-3 pr-4">
                <Link
                  href={`/results/${entry.mark.id}`}
                  className="font-medium text-blue-600 hover:underline"
                >
                  {entry.mark.name}
                </Link>
              </td>
              <td className="py-3 pr-4">
                <ScoreBadge score={entry.score} />
              </td>
              <td className="py-3 pr-4 text-gray-500">
                {entry.last_checked
                  ? new Date(entry.last_checked).toLocaleDateString()
                  : "Never"}
              </td>
              <td className="py-3 pr-4 text-gray-500">
                {entry.check_interval_days}d
              </td>
              <td className="py-3 flex gap-2">
                <button
                  onClick={() => handleRecheck(entry.mark.name)}
                  className="rounded bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200"
                >
                  Re-check
                </button>
                <button
                  onClick={() => handleRemove(entry.id)}
                  className="rounded bg-red-50 px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-100"
                >
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
