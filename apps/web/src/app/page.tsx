import { AppStateProvider } from "@/contexts/app-context";
import { MainShell } from "@/components/shell/main-shell";

export default function HomePage() {
  return (
    <AppStateProvider>
      <MainShell />
    </AppStateProvider>
  );
}
