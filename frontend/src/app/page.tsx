"use client";

import dynamic from "next/dynamic";
import Link from "next/link";

const SearchForm = dynamic(() => import("@/components/SearchForm"), { ssr: false });

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-gray-900">KH Rights Finder</h1>
        <p className="mt-2 text-gray-500">
          Search Cambodia brand-rights evidence from D/IPR authoritative sources
        </p>
      </div>

      <SearchForm />

      <nav className="mt-12">
        <Link
          href="/watchlist"
          className="text-sm text-blue-600 hover:underline"
        >
          View Watchlist
        </Link>
      </nav>
    </main>
  );
}
