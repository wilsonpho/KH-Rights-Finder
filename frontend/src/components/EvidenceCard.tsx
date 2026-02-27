"use client";

import type { EvidenceItem } from "@/lib/api";

const MAX_VISIBLE = 8;

function normalize(s: string): string {
  return s.replace(/\u00A0/g, " ").trim();
}

function isCleanEntry(key: string, val: string): boolean {
  const k = key.trim();
  const v = val.trim();
  if (!k || !v) return false;
  if (k.length > 50) return false;
  if (v.endsWith(":")) return false;
  if ((v.match(/:/g) || []).length >= 3) return false;
  if (/^\d{4}-\d{2}-\d{2}$/.test(k)) return false;
  if (/\/\w+\//.test(k) && !k.includes(" ")) return false;
  return true;
}

function labelFromKey(key: string): string {
  return key.replace(/:$/, "").replace(/_/g, " ").trim();
}

export default function EvidenceCard({
  item,
  markName,
}: {
  item: EvidenceItem;
  markName?: string;
}) {
  const isAuth = item.source_type === "authoritative";
  const borderColor = isAuth ? "border-blue-200" : "border-gray-200";

  const title =
    item.title && item.title !== "Unknown mark"
      ? item.title
      : markName || "Untitled";

  const entries = Object.entries(item.detail || {})
    .filter(([k]) => k !== "status")
    .map(([k, v]) => [k, String(v ?? "")] as [string, string]);

  const clean = entries.filter(([k, v]) => isCleanEntry(k, v));
  const raw = entries.filter(
    ([k, v]) => !isCleanEntry(k, v) && (k.trim() || String(v).trim()),
  );

  const visible = clean.slice(0, MAX_VISIBLE);
  const overflow = clean.slice(MAX_VISIBLE);
  const collapsedCount = overflow.length + raw.length;

  return (
    <div
      className={`w-full max-w-full min-w-0 overflow-hidden rounded-lg border ${borderColor} bg-white p-4 shadow-sm`}
    >
      {/* Header */}
      <div className="mb-2 flex min-w-0 items-center justify-between">
        <h3 className="min-w-0 break-words [overflow-wrap:anywhere] font-medium text-gray-900">
          {title}
        </h3>
        <div className="ml-2 flex shrink-0 items-center gap-2">
          <span
            className={`rounded px-2 py-0.5 text-xs font-medium ${
              isAuth
                ? "bg-blue-100 text-blue-700"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            {item.source_type}
          </span>
          <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
            {item.source}
          </span>
        </div>
      </div>

      {/* Structured fields */}
      {visible.length > 0 && (
        <dl className="mt-2 grid min-w-0 grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          {visible.map(([key, value]) => (
            <div key={key} className="contents">
              <dt className="shrink-0 capitalize text-gray-500">
                {labelFromKey(key)}:
              </dt>
              <dd className="min-w-0 break-words [overflow-wrap:anywhere] text-gray-900">
                {key === "pdf_url" && value.startsWith("http") ? (
                  <a
                    href={value}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    View PDF
                  </a>
                ) : (
                  normalize(value)
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {/* Collapsed overflow + raw */}
      {collapsedCount > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer select-none text-xs text-gray-400 hover:text-gray-600">
            {overflow.length > 0
              ? `+${collapsedCount} more fields`
              : `Show raw data (${raw.length})`}
          </summary>
          <dl className="mt-1 grid min-w-0 grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            {[...overflow, ...raw].map(([key, value], i) => (
              <div key={i} className="contents">
                <dt className="max-w-[10rem] shrink-0 truncate capitalize text-gray-400">
                  {labelFromKey(key) || "(empty)"}:
                </dt>
                <dd className="min-w-0 break-all text-gray-500">
                  {normalize(value) || "\u2014"}
                </dd>
              </div>
            ))}
          </dl>
        </details>
      )}

      {item.confidence !== null && (
        <div className="mt-2 text-xs text-gray-400">
          Confidence: {item.confidence}%
        </div>
      )}
    </div>
  );
}
