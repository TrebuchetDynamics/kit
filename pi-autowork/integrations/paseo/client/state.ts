import { useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useHosts, useRpc } from '@getpaseo/plugin/client';
import { commitRpc, fleetRpc, prepareRpc, watchRpc, type ActionInput, type Operation, type Ticket } from '../shared/contracts';
import { reloadRequired } from './presentation';

export function useReadBackoff() {
  const failures = useRef(0);
  return {
    async run<T>(read: () => Promise<T>): Promise<T> {
      try { const value = await read(); failures.current = 0; return value; }
      catch (error) { failures.current = Math.min(8, failures.current + 1); throw error; }
    },
    delay: (base: number, maximum: number) => Math.min(maximum, base * 2 ** failures.current),
  };
}

export function useHostState(hostId: string) {
  const hosts = useHosts();
  const online = hosts.find(host => host.serverId === hostId)?.status === 'online';
  const [foreground, setForeground] = useState(AppState.currentState === 'active');
  useEffect(() => {
    const subscription = AppState.addEventListener('change', state => setForeground(state === 'active'));
    return () => subscription.remove();
  }, []);
  const enabled = online && foreground;
  // A connectivity epoch revokes both tickets and late responses, even on the same host.
  const scope = useRef({ enabled, epoch: 0, since: Date.now() });
  if (scope.current.enabled !== enabled) scope.current = { enabled, epoch: scope.current.epoch + 1, since: Date.now() };
  const callFleet = useRpc(fleetRpc);
  const backoff = useReadBackoff();
  const fleet = useQuery({
    queryKey: ['autowork', hostId, 'fleet'], enabled, staleTime: 15000, gcTime: 300000,
    retry: false, refetchOnMount: 'always', refetchOnWindowFocus: false, refetchOnReconnect: false,
    // A stale plugin generation refuses every read until the owner reloads it; polling cannot
    // recover that state and would only burn battery until the reload remounts this tree.
    refetchInterval: query => enabled && !reloadRequired(query.state.error) ? backoff.delay(20000, 120000) : false,
    queryFn: () => backoff.run(async () => {
      const epoch = scope.current.epoch;
      if (!scope.current.enabled) throw new Error('Host offline or polling paused');
      const value = await callFleet({});
      if (!scope.current.enabled || scope.current.epoch !== epoch) throw new Error('Discarded stale host response');
      return value;
    }),
  });
  const queries = useQueryClient();
  useEffect(() => { if (enabled) void queries.invalidateQueries({ queryKey: ['autowork', hostId] }); }, [enabled, hostId, queries]);
  const captureAge = fleet.data ? Date.now() - fleet.data.capturedAt : Infinity;
  const current = enabled && fleet.isSuccess && !fleet.isFetching && fleet.dataUpdatedAt >= scope.current.since && captureAge >= -5000 && captureAge <= 30000;
  const refresh = () => { if (scope.current.enabled) void queries.invalidateQueries({ queryKey: ['autowork', hostId] }); };
  return { online, foreground, enabled, scope, fleet, current, refresh };
}

export type HostState = ReturnType<typeof useHostState>;
const pause = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));
/** Long-poll the daemon's change digest while this host is live; a change invalidates every read. */
export function useWatch(host: HostState, hostId: string, instance: string | undefined) {
  const watch = useRpc(watchRpc);
  const queries = useQueryClient();
  const call = useRef(watch); call.current = watch;
  const [digest, setDigest] = useState('');
  const enabled = host.enabled;
  useEffect(() => {
    if (!enabled || !instance) return;
    let active = true;
    const epoch = host.scope.current.epoch;
    let last = '';
    (async () => {
      while (active) {
        const started = Date.now();
        try {
          const result = await call.current({ instance, digest: last });
          if (!active || host.scope.current.epoch !== epoch) return;
          if (result.changed && last) void queries.invalidateQueries({ queryKey: ['autowork', hostId] });
          last = result.digest; setDigest(result.digest);
        } catch {
          if (!active) return;
          await pause(15000);
        }
        if (active && Date.now() - started < 1000) await pause(1000);
      }
    })();
    return () => { active = false; };
  }, [enabled, instance, hostId, host.scope, queries]);
  return digest;
}
export async function readForHost<T>(host: HostState, read: () => Promise<T>): Promise<T> {
  const epoch = host.scope.current.epoch;
  if (!host.scope.current.enabled) throw new Error('Host offline or polling paused');
  const value = await read();
  if (!host.scope.current.enabled || host.scope.current.epoch !== epoch) throw new Error('Discarded stale host response; refresh to read again');
  return value;
}
export const operationsKey = (hostId: string, instance: string) => ['autowork', hostId, instance, 'accepted-operations'] as const;
export function rememberOperation(existing: Operation[] = [], operation: Operation): Operation[] {
  return [...existing.filter(item => item.id !== operation.id), operation].slice(-32);
}
interface Confirmation { ticket: Ticket; epoch: number; context: string }
export function useConfirmedAction(host: HostState, hostId: string, instance: string, context: string, onOperation: (operation: Operation) => void) {
  const prepare = useRpc(prepareRpc), commit = useRpc(commitRpc);
  const queryClient = useQueryClient();
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const lock = useRef(false);
  const alive = useRef(true);
  const latest = useRef({ context, current: host.current, enabled: host.enabled });
  latest.current = { context, current: host.current, enabled: host.enabled };
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { setConfirmation(null); }, [context, host.enabled]);
  const valid = (epoch: number, expectedContext: string) => alive.current && host.scope.current.enabled && host.scope.current.epoch === epoch && latest.current.context === expectedContext;
  const request = async (action: ActionInput) => {
    if (lock.current || !latest.current.current) return;
    lock.current = true; setBusy(true); setConfirmation(null); setMessage('Preparing confirmation…');
    const epoch = host.scope.current.epoch;
    try {
      const ticket = await prepare({ instance, action });
      if (valid(epoch, context)) { setConfirmation({ ticket, epoch, context }); setMessage('Review before confirming. Nothing has been dispatched.'); }
    } catch (error) { if (valid(epoch, context)) setMessage(error instanceof Error ? error.message : String(error)); }
    finally { lock.current = false; if (alive.current) setBusy(false); }
  };
  const confirm = async () => {
    const pending = confirmation;
    if (!pending || lock.current || !valid(pending.epoch, pending.context) || !latest.current.current || pending.ticket.expiresAt <= Date.now()) {
      setConfirmation(null); return;
    }
    // Consume locally before awaiting: a second tap cannot commit the ticket twice.
    lock.current = true; setBusy(true); setConfirmation(null); setMessage('Dispatching once…');
    try {
      const operation = await commit({ instance, ticket: pending.ticket.ticket });
      // Preserve even a late accepted handle on its original host/generation, not the new surface.
      queryClient.setQueryData<Operation[]>(operationsKey(hostId, instance), existing => rememberOperation(existing, operation));
      if (alive.current) {
        onOperation(operation);
        setMessage(`${operation.status}: ${operation.message}`);
        void queryClient.invalidateQueries({ queryKey: ['autowork', hostId] });
      }
    } catch (error) {
      if (alive.current) setMessage(`Delivery unknown; not retried. Refresh and inspect before a new action. ${error instanceof Error ? error.message : String(error)}`);
    } finally { lock.current = false; if (alive.current) setBusy(false); }
  };
  return { request, confirm, busy, message, confirmation: confirmation && host.enabled && confirmation.epoch === host.scope.current.epoch && confirmation.context === context ? confirmation.ticket : null, dismiss: () => setConfirmation(null) };
}
