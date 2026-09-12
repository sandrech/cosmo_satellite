import type { PropsWithChildren } from "react";
import { AppStateProvider } from "../shared/model/store";

export function AppProviders({ children }: PropsWithChildren) {
  return <AppStateProvider>{children}</AppStateProvider>;
}
