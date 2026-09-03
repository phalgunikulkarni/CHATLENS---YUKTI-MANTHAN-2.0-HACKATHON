import { useContext } from "react";
import { DispatchContext, StateContext, type AppAction } from "../state/store";
import type { RootState } from "../state/types";
import type { Dispatch } from "react";

export function useRootState(): RootState {
  const ctx = useContext(StateContext);
  if (!ctx) throw new Error("useRootState must be used within StoreProvider");
  return ctx;
}

export function useDispatch(): Dispatch<AppAction> {
  const ctx = useContext(DispatchContext);
  if (!ctx) throw new Error("useDispatch must be used within StoreProvider");
  return ctx;
}

export const useConversation = () => useRootState().conversation;
export const useResults = () => useRootState().results;
export const useIngestion = () => useRootState().ingestion;
export const useActions = () => useRootState().actions;
export const useConnectors = () => useRootState().connectors;
export const useConversations = () => useRootState().conversations;
export const useUi = () => useRootState().ui;
