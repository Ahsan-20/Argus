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

export const keys = {
  health: ["health"],
  stats: ["stats"],
  fleet: (owner) => ["fleet", owner || "all"],
  watcher: (id) => ["watcher", id],
  runs: (id) => ["runs", id],
  transmissions: (id) => ["transmissions", id],
};

export function useHealth() {
  return useQuery({
    queryKey: keys.health,
    queryFn: api.health,
    refetchInterval: FLEET_POLL,
    // One retry, not none. This drives the connection banner, and a host that
    // sleeps when idle fails the very first request while it wakes. Without a
    // retry that single stumble latches the banner on for a full poll cycle,
    // announcing a problem that has already fixed itself.
    retry: 1,
    retryDelay: 2000,
  });
}

// How long the connection has to stay bad before we say so out loud.
// One failed cycle is almost always a sleeping host waking up. Two in a row
// means something is actually wrong.
const OFFLINE_AFTER = 25_000;

/**
 * Is the backend really unreachable, or did one request just stumble?
 *
 * `isError` alone is too eager: it goes true on a single failure, which on a
 * host that sleeps when idle is the ordinary first request of any visit. The
 * banner would then announce a problem that had already fixed itself before
 * anyone finished reading it.
 *
 * So a failure only counts once it has persisted well past one poll cycle
 * beyond the last success. A genuine outage still surfaces within about half a
 * minute, and a wake-up never does.
 */
export function useConnection() {
  const health = useHealth();
  const { isError, data, errorUpdatedAt, dataUpdatedAt } = health;

  const neverConnected = isError && !data;
  const staleFailure =
    isError && Boolean(data) && errorUpdatedAt - dataUpdatedAt > OFFLINE_AFTER;
  const offline = neverConnected || staleFailure;

  return {
    query: health,
    offline,
    // ok, degraded (reachable but the database is not), or offline.
    status: offline
      ? "offline"
      : data?.status === "ok"
        ? "ok"
        : data
          ? "degraded"
          : "ok",
  };
}

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
