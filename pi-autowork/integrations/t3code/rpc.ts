export type Task = { id: string; title: string; state: string; why: string };
export type Repository = { id: string; label: string };
export type Snapshot = {
  repository: string; capturedAt: string; state: string; needs: string;
  blockers: string[]; tasks: Task[]; logs: string;
};
export type AutoworkRpc = {
  methods: {
    repositories: { input: undefined; output: Repository[] };
    snapshot: { input: { repository: string }; output: Snapshot };
  };
  channels: {};
};
