const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ScoreFactor {
  source: string;
  status: string | null;
  points: number;
}

export interface Score {
  total: number;
  authoritative: number;
  secondary: number;
  label: string;
  factors: ScoreFactor[];
}

export interface MarkInfo {
  id: string;
  name: string;
  created_at: string;
}

export interface EvidenceItem {
  id: string;
  source: string;
  source_type: string;
  title: string | null;
  detail: Record<string, unknown> | null;
  snapshot_id: string | null;
  confidence: number | null;
  found_at: string;
}

export interface JobInfo {
  id: string;
  source: string;
  status: string;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface SearchResult {
  mark: MarkInfo;
  jobs: JobInfo[];
  score: Score;
  evidence: EvidenceItem[];
}

export interface WatchlistEntry {
  id: string;
  mark: MarkInfo;
  last_checked: string | null;
  check_interval_days: number;
  active: boolean;
  score: Score;
}

export async function createSearch(brandName: string): Promise<SearchResult> {
  const res = await fetch(`${API_URL}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ brand_name: brandName }),
  });
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export async function getSearchResult(markId: string): Promise<SearchResult> {
  const res = await fetch(`${API_URL}/api/search/${markId}`);
  if (!res.ok) throw new Error(`Fetch failed: ${res.status}`);
  return res.json();
}

export async function retrySearch(markId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/search/${markId}/retry`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Retry failed: ${res.status}`);
}

export async function getWatchlist(): Promise<WatchlistEntry[]> {
  const res = await fetch(`${API_URL}/api/watchlist`);
  if (!res.ok) throw new Error(`Watchlist fetch failed: ${res.status}`);
  return res.json();
}

export async function addToWatchlist(markId: string): Promise<WatchlistEntry> {
  const res = await fetch(`${API_URL}/api/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mark_id: markId }),
  });
  if (!res.ok) throw new Error(`Add to watchlist failed: ${res.status}`);
  return res.json();
}

export async function removeFromWatchlist(entryId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/watchlist/${entryId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Remove failed: ${res.status}`);
}
