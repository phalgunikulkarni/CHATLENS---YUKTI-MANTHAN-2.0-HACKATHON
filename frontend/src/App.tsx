import { StoreProvider } from "./state/store";
import { AuthProvider } from "./features/auth/AuthContext";
import { AuthGate } from "./features/auth/AuthGate";
import { OnboardingGate } from "./features/onboarding/OnboardingGate";
import { AppLayout } from "./layouts/AppLayout";
import { useUi } from "./hooks";
import { SearchWorkspace } from "./pages/SearchWorkspace";
import { LibraryPage } from "./pages/LibraryPage";
import { UploadPage } from "./pages/UploadPage";
import { ConnectorsPage } from "./pages/ConnectorsPage";

/** The protected dashboard - only rendered for authenticated users. */
function Dashboard() {
  const { view } = useUi();
  return (
    <AppLayout>
      {view === "search" && <SearchWorkspace />}
      {view === "library" && <LibraryPage />}
      {view === "upload" && <UploadPage />}
      {view === "connectors" && <ConnectorsPage />}
    </AppLayout>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AuthGate>
        <StoreProvider>
          <OnboardingGate>
            <Dashboard />
          </OnboardingGate>
        </StoreProvider>
      </AuthGate>
    </AuthProvider>
  );
}