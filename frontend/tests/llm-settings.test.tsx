import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LlmProviderSettings } from '../src/components/settings/LlmProviderSettings';
import * as service from '../src/services/llmSettings';

vi.mock('../src/services/llmSettings', async () => {
  const actual = await vi.importActual<typeof import('../src/services/llmSettings')>('../src/services/llmSettings');
  return {
    ...actual,
    getLlmConfiguration: vi.fn(),
    getLlmUsage: vi.fn(),
    saveLlmCredential: vi.fn(),
    revalidateLlmCredential: vi.fn(),
    deleteLlmCredential: vi.fn(),
    updateLlmPreferences: vi.fn(),
  };
});

const configuration = {
  mode: 'hybrid' as const,
  preferred_provider: null,
  preferred_model: null,
  preference_revision: 1,
  allow_background_ai: false,
  providers: [
    { provider: 'gemini' as const, enabled: true, configured: false, status: null, key_hint: null, credential_revision: null, last_validated_at: null, validation_failure_code: null, allowed_models: ['gemini-2.0-flash'] },
    { provider: 'groq' as const, enabled: true, configured: false, status: null, key_hint: null, credential_revision: null, last_validated_at: null, validation_failure_code: null, allowed_models: ['llama-3.3-70b-versatile'] },
    { provider: 'openai' as const, enabled: true, configured: false, status: null, key_hint: null, credential_revision: null, last_validated_at: null, validation_failure_code: null, allowed_models: ['gpt-5-mini'] },
  ],
  deployment_fallback: { available: true, privileged: false, calls_used: 0, calls_limit: 10, calls_remaining: 10 },
};

describe('LLM provider settings', () => {
  beforeEach(() => {
    vi.mocked(service.getLlmConfiguration).mockResolvedValue(structuredClone(configuration));
    vi.mocked(service.getLlmUsage).mockResolvedValue({ items: [], next_cursor: null });
    vi.mocked(service.saveLlmCredential).mockResolvedValue({ id: '1', owner_id: 'u', provider: 'openai', key_hint: 'cret', status: 'valid', credential_revision: 1, preference_revision: 2, last_validated_at: null });
  });

  it('shows fallback calls rather than describing them as questions', async () => {
    render(<LlmProviderSettings />);
    expect(await screen.findByText(/10 of 10 lifetime provider calls remain/i)).toBeInTheDocument();
    expect(screen.queryByText(/10 questions/i)).not.toBeInTheDocument();
  });

  it('clears a plaintext API key after validation and save', async () => {
    render(<LlmProviderSettings />);
    const keyInput = await screen.findByLabelText('API_KEY', { selector: '#key-openai' });
    fireEvent.change(keyInput, { target: { value: 'openai-user-secret' } });
    const saveButtons = screen.getAllByRole('button', { name: /validate & save/i });
    fireEvent.click(saveButtons[2]);

    await waitFor(() => expect(service.saveLlmCredential).toHaveBeenCalled());
    await waitFor(() => expect(keyInput).toHaveValue(''));
  });
});
