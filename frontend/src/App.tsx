import { StoreProvider } from "./state/store";
import { AuthProvider } from "./features/auth/AuthContext";
import { AuthGate } from "./features/auth/AuthGate";
import { AccountResetBridge } from "./features/auth/AccountResetBridge";
import { ChatHydrationBridge } from "./features/auth/ChatHydrationBridge";
import { OnboardingGate } from "./features/onboarding/OnboardingGate";
import { AppLayout } from "./layouts/AppLayout";
import { useUi } from "./hooks";
import { SearchWorkspace } from "./pages/SearchWorkspace";
import { LibraryPage } from "./pages/LibraryPage";
import { ConnectorsPage } from "./pages/ConnectorsPage";

/** The protected dashboard - only rendered for authenticated users. */
function Dashboard() {
  const { view } = useUi();
  return (
    <AppLayout>
      {view === "search" && <SearchWorkspace />}
      {view === "library" && <LibraryPage />}
      {view === "connectors" && <ConnectorsPage />}
    </AppLayout>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AuthGate>
        <StoreProvider>
          <AccountResetBridge>
            <ChatHydrationBridge>
              <OnboardingGate>
                <Dashboard />
              </OnboardingGate>
            </ChatHydrationBridge>
          </AccountResetBridge>
        </StoreProvider>
      </AuthGate>
    </AuthProvider>
  );
}