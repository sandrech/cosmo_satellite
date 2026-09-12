import { useCallback } from "react";
import type { GroundSite } from "../../shared/model/types";

export function useGlobePicking(
  setSelectedId: (id: string | null) => void,
  setClientId: (id: string) => void,
) {
  const selectSatellite = useCallback(
    (id: string) => setSelectedId(id),
    [setSelectedId],
  );
  const selectGroundSite = useCallback(
    (site: GroundSite) => {
      setSelectedId(site.id);
      if (site.role === "client") setClientId(site.id);
    },
    [setClientId, setSelectedId],
  );
  return { selectSatellite, selectGroundSite };
}
