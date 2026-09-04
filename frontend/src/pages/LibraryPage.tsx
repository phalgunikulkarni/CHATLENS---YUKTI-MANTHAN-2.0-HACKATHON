import { useEffect, useState } from "react";
import type { SearchResult } from "../api/types";
import { apiService } from "../api/client";
import { isNotConnected } from "../api/errors";
import { MemoryGrid } from "../features/results/MemoryGrid";
import { EmptyState } from "../components/States";
import { SkeletonGrid } from "../components/SkeletonGrid";

/**
 * The library shows the user's canonical, indexed visual memories, read from
 * the read-only /api/library endpoint (backed by ML/Chroma). It never
 * fabricates memories: an honest empty/not-connected/error state is shown
 * whenever the backend has nothing (or can't be reached).
 */

type LibraryStatus = "loading" | "ready" | "empty" | "notConnected" | "error";

export function LibraryPage() {
  const [items, setItems] = useState<SearchResult[]>([]);
  const [status, setStatus] = useState<LibraryStatus>("loading");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");

    apiService
      .listLibrary()
      .then((result) => {
        if (cancelled) return;
        if (result.length > 0) {
          setItems(result);
          setStatus("ready");
        } else {
          setItems([]);
          setStatus("empty");
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setItems([]);
        setStatus(isNotConnected(err) ? "notConnected" : "error");
      });

    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (status === "loading") {
    return <SkeletonGrid count={6} />;
  }

  if (status === "ready") {
    return (
      <MemoryGrid
        results={items}
        selectedIds={[]}
        view="grid"
        onToggleSelect={() => {}}
        onOpen={() => {}}
        onWhy={() => {}}
      />
    );
  }

  if (status === "notConnected") {
    return (
      <EmptyState
        icon="library"
        title="Connect ChatLens to see your memories"
        message="Your indexed memories will appear here once ChatLens is connected to your library."
      />
    );
  }

  if (status === "error") {
    return (
      <EmptyState
        icon="library"
        title="Couldn't load your memories"
        message="Something went wrong loading your library. Please try again."
        action={
          <button className="btn btn-primary" onClick={() => setReloadKey((k) => k + 1)}>
            Try again
          </button>
        }
      />
    );
  }

  // empty
  return (
    <EmptyState
      icon="library"
      title="No memories yet"
      message="Once ChatLens has access to your image folders and finishes indexing them, your searchable memories will appear here."
    />
  );
}
