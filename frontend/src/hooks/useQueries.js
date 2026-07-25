import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "../lib/api.js";

// Server state lives here (plan s.1). TanStack Query polls the fleet, caches,
// and refetches in the background. refetchInterval does NOT fire on a hidden
// tab (v5 default refetchIntervalInBackground: false), so a backgrounded
// console spends no quota.

const FLEET_POLL = 10_000;

// There is deliberately no /health poll here. It existed only to colour a dot
// and a banner, and a single failed request would announce trouble over a
// dashboard visibly full of working data. Genuine failures already surface
// where they matter: the queries below feed ErrorState, which explains itself
// and offers a retry. Losing the poll also spares a small instance a quarter
// of its request load. Uptime belongs to an external monitor, not to a widget
// inside the app it is meant to be watching.

export const keys = {
  stats: ["stats"],
  fleet: (owner) => ["fleet", owner || "all"],
  watcher: (id) => ["watcher", id],
  runs: (id) => ["runs", id],
  transmissions: (id) => ["transmissions", id],
};


export function useStats(enabled = true) {
  return useQuery({
    queryKey: keys.stats,
    queryFn: api.stats,
    refetchInterval: FLEET_POLL,
    enabled,
    retry: false,
  });
}

// `owner` is only the cache key now: the server reads whose watchers these
// are from the session token. Keeping it keyed means signing in as someone
// else cannot show you the previous account's roster from cache.
export function useFleet(owner) {
  return useQuery({
    queryKey: keys.fleet(owner),
    queryFn: () => api.listWatchers(),
    refetchInterval: FLEET_POLL,
  });
}

export function useSharedFleet(enabled = true) {
  return useQuery({
    queryKey: ["shared"],
    queryFn: api.listShared,
    refetchInterval: FLEET_POLL,
    enabled,
  });
}

export function useWatcher(id) {
  return useQuery({
    queryKey: keys.watcher(id),
    queryFn: () => api.getWatcher(id),
    enabled: id != null,
    refetchInterval: FLEET_POLL,
  });
}

export function useRuns(id) {
  return useQuery({
    queryKey: keys.runs(id),
    queryFn: () => api.runs(id),
    enabled: id != null,
    refetchInterval: FLEET_POLL,
  });
}

export function useTransmissions(id) {
  return useQuery({
    queryKey: keys.transmissions(id),
    queryFn: () => api.transmissions(id),
    enabled: id != null,
  });
}

// Control mutations invalidate the fleet and the affected probe so the UI
// reconciles on the next poll (optimistic feel, honest reconcile).
export function useProbeControls(id) {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["fleet"] });
    if (id != null) {
      qc.invalidateQueries({ queryKey: keys.watcher(id) });
      qc.invalidateQueries({ queryKey: keys.runs(id) });
    }
  };
  return {
    pause: useMutation({ mutationFn: () => api.pause(id), onSuccess: invalidate }),
    resume: useMutation({ mutationFn: () => api.resume(id), onSuccess: invalidate }),
    retire: useMutation({ mutationFn: () => api.retire(id), onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["fleet"] }) }),
    runNow: useMutation({ mutationFn: () => api.runNow(id), onSuccess: invalidate }),
  };
}
