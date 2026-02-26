"use client";

import type { EvidenceItem } from "@/lib/api";

export default function EvidenceCard({ item }: { item: EvidenceItem }) {
  const isAuth = item.source_type === "authoritative";
  const borderColor = isAuth ? "border-blue-200" : "border-gray-200";

  return (
    <div className={`rounded-lg border ${borderColor} bg-white p-4 shadow-sm`}>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-medium text-gray-900 truncate">
          {item.title || "Untitled"}
        </h3>
        <div className="flex items-center gap-2 shrink-0 ml-2">
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

      {item.detail && (
        <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          {Object.entries(item.detail).map(([key, value]) => {
            if (!value || key === "status") return null;
            const displayValue = String(value);
            const isPdfLink =
              key === "pdf_url" && displayValue.startsWith("http");
            return (
              <div key={key} className="col-span-2 flex gap-2">
                <dt className="text-gray-500 capitalize whitespace-nowrap">
                  {key.replace(/_/g, " ")}:
                </dt>
                <dd className="text-gray-900 truncate">
                  {isPdfLink ? (
                    <a
                      href={displayValue}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      View PDF
                    </a>
                  ) : (
                    displayValue
                  )}
                </dd>
              </div>
            );
          })}
        </dl>
      )}

      {item.confidence !== null && (
        <div className="mt-2 text-xs text-gray-400">
          Confidence: {item.confidence}%
        </div>
      )}
    </div>
  );
}
