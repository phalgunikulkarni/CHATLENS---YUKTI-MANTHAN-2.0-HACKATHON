import { useMemo, useRef, useState } from "react";
import { useActions, useConversation, useResults, useUi } from "../hooks";
import { useChatLens } from "../hooks/useChatLens";
import { SearchHero } from "../features/results/SearchHero";
import { ResultsToolbar, pillForResult, type CategoryValue, type SortValue } from "../features/results/ResultsToolbar";
import { MemoryGrid } from "../features/results/MemoryGrid";
import { QuickInsights } from "../features/results/QuickInsights";
import { ImageDetailDrawer } from "../features/results/ImageDetailDrawer";
import { ConversationPanel } from "../features/conversation/ConversationPanel";
import { ActionGrid, type ActionId } from "../features/actions/ActionGrid";
import { ExecutionWorkspace, type ExecHandle } from "../features/actions/ExecutionWorkspace";
import { ConfirmDialog } from "../features/actions/ConfirmDialog";
import { SkeletonGrid } from "../components/SkeletonGrid";
import { EmptyState, ErrorState, NotConnectedState } from "../components/States";

export function SearchWorkspace() {
  const results = useResults();
  const conversation = useConversation();
  const ui = useUi();
  const actions = useActions();
  const c = useChatLens();
  const [view] = useState<"grid" | "list">("grid");
  const [category, setCategory] = useState<CategoryValue>("all");
  const [sort, setSort] = useState<SortValue>("relevance");
  const execRef = useRef<ExecHandle | null>(null);

  const defaultTitle = useMemo(() => {
    const first = results.items.find((r) => results.selectedIds.includes(r.id));
    return (first?.title || results.echoedQuery || "").trim() || undefined;
  }, [results.items, results.selectedIds, results.echoedQuery]);

  const visibleItems = useMemo(() => {
    let items = category === "all" ? results.items : results.items.filter((r) => pillForResult(r) === category);
    if (sort === "recent") {
      items = [...items].sort((a, b) => (b.capturedAt ?? "").localeCompare(a.capturedAt ?? ""));
    }
    return items;
  }, [results.items, category, sort]);

  const openResult = results.items.find((r) => r.id === ui.drawerOpenForId);
  const onAction = (id: ActionId) => execRef.current?.run(id);

  return (
    <div className="cl-theme">
      {!results.hasSearched ? (
        <SearchHero onSearch={c.runSearch} />
      ) : (
        <div className="cl-workspace">
          <ResultsToolbar
            query={results.echoedQuery}
            count={visibleItems.length}
            results={results.items}
            category={category}
            sort={sort}
            onSearch={c.runSearch}
            onCategory={setCategory}
            onSort={setSort}
          />

          <div className="cl-results-row">
            <div className="results-col">
              {results.loading ? (
                <SkeletonGrid count={6} />
              ) : results.notConnected ? (
                <NotConnectedState />
              ) : results.error ? (
                <ErrorState title="Search failed" message={results.error} onRetry={() => c.runSearch(results.echoedQuery)} />
              ) : visibleItems.length === 0 ? (
                <EmptyState icon="search" title="No memories matched"
                  message="Try adding a memory clue - for example the type of image, a topic, or something you remember seeing." />
              ) : (
                <MemoryGrid results={visibleItems} selectedIds={results.selectedIds} view={view}
                  onToggleSelect={c.toggleSelect} onOpen={c.openDrawer} onWhy={c.openDrawer} />
              )}
            </div>

            <aside className="cl-refine-col">
              <ConversationPanel onSend={c.runRefine} />
              <QuickInsights results={results.items} />
            </aside>
          </div>

          <ActionGrid heading="What would you like to do with these results?" onAction={onAction} />

          <ExecutionWorkspace
            selectedIds={results.selectedIds}
            defaultTitle={defaultTitle}
            sessionId={conversation.sessionId}
            handleRef={execRef}
          />
        </div>
      )}

      {openResult && (
        <ImageDetailDrawer
          result={openResult}
          selected={results.selectedIds.includes(openResult.id)}
          onClose={c.closeDrawer}
          onToggleSelect={c.toggleSelect}
          onSummarize={c.summarizeImage}
          onRoadmap={c.roadmapImage}
        />
      )}
      {ui.confirmDialogOpen && actions.proposal && (
        <ConfirmDialog
          proposal={actions.proposal}
          onConfirm={() => c.confirmSchedule(actions.proposal!.events)}
          onCancel={c.cancelSchedule}
        />
      )}
    </div>
  );
}
