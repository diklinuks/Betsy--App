import { create } from "zustand";
import type { RunBundle, ViewId } from "./types";

interface ReplayState {
  run: RunBundle | null;
  loading: boolean;
  error: string | null;

  cursorDay: number; // 1..sim_days
  playing: boolean;
  speed: number; // days per second multiplier (1, 2, 4)
  view: ViewId;
  selectedDecisionId: string | null;

  load: () => Promise<void>;
  setCursor: (day: number) => void;
  tick: () => void;
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  restart: () => void;
  step: (delta: number) => void;
  setSpeed: (s: number) => void;
  setView: (v: ViewId) => void;
  selectDecision: (id: string | null) => void;
}

// Resolve run.json relative to the document so it works at the domain root AND
// under a GitHub Pages project subpath (e.g. /Betsy-App/) without guessing the base.
const RUN_URL = new URL("run.json", document.baseURI).href;

export const useReplay = create<ReplayState>((set, get) => ({
  run: null,
  loading: true,
  error: null,
  cursorDay: 1,
  playing: false,
  speed: 2,
  view: "deck",
  selectedDecisionId: null,

  load: async () => {
    try {
      const res = await fetch(RUN_URL, { cache: "no-cache" });
      if (!res.ok) throw new Error(`run.json ${res.status}`);
      const run = (await res.json()) as RunBundle;
      set({ run, loading: false, cursorDay: run.meta.sim_days });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  setCursor: (day) => {
    const max = get().run?.meta.sim_days ?? 90;
    set({ cursorDay: Math.min(max, Math.max(1, Math.round(day))) });
  },

  tick: () => {
    const { cursorDay, run } = get();
    const max = run?.meta.sim_days ?? 90;
    if (cursorDay >= max) {
      set({ playing: false });
      return;
    }
    set({ cursorDay: cursorDay + 1 });
  },

  play: () => {
    const { cursorDay, run } = get();
    const max = run?.meta.sim_days ?? 90;
    set({ playing: true, cursorDay: cursorDay >= max ? 1 : cursorDay });
  },
  pause: () => set({ playing: false }),
  togglePlay: () => (get().playing ? get().pause() : get().play()),
  restart: () => set({ cursorDay: 1, playing: true }),
  step: (delta) => {
    set({ playing: false });
    get().setCursor(get().cursorDay + delta);
  },
  setSpeed: (s) => set({ speed: s }),
  setView: (v) => set({ view: v }),
  selectDecision: (id) => set({ selectedDecisionId: id }),
}));
