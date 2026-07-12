import { create } from 'zustand';
import { getSettings, updateSettings } from '../services/api';
import type { UserSettings } from '../services/api';

interface SettingsState {
  settings: UserSettings | null;
  isLoading: boolean;
  error: string | null;
  
  fetchSettings: () => Promise<void>;
  updateSetting: (updates: Partial<UserSettings>) => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: null,
  isLoading: false,
  error: null,

  fetchSettings: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await getSettings();
      set({ settings: data, isLoading: false });
    } catch (err: unknown) {
      set({ error: err instanceof Error ? err.message : 'Failed to fetch settings', isLoading: false });
    }
  },

  updateSetting: async (updates: Partial<UserSettings>) => {
    const currentSettings = get().settings;
    if (!currentSettings) return;

    // Optimistically update UI
    set({ settings: { ...currentSettings, ...updates } });

    try {
      const updated = await updateSettings(updates);
      // Sync with strict server response just in case
      set({ settings: updated, error: null });
    } catch (err: unknown) {
      // Revert on failure
      set({ settings: currentSettings, error: err instanceof Error ? err.message : 'Failed to update setting' });
    }
  }
}));
