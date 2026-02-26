"use client";

import type { Score } from "@/lib/api";

const COLORS: Record<string, string> = {
  strong: "bg-green-100 text-green-800 border-green-300",
  moderate: "bg-yellow-100 text-yellow-800 border-yellow-300",
  weak: "bg-orange-100 text-orange-800 border-orange-300",
  none: "bg-gray-100 text-gray-500 border-gray-300",
};

export default function ScoreBadge({ score }: { score: Score }) {
  const color = COLORS[score.label] || COLORS.none;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-medium ${color}`}
    >
      <span className="font-bold">{score.total}</span>
      <span className="capitalize">{score.label}</span>
    </span>
  );
}
