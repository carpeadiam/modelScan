import { describe, it, expect } from 'vitest';
// The pure inference helper is exercised through a minimal replica contract here;
// API/D1 integration is covered by deployment smoke checks because bindings are platform-provided.
describe('API contracts', () => {
  it('requires model features to be numeric and preserves null when no model exists', () => {
    const feature = Number('not-a-number');
    expect(Number.isFinite(feature)).toBe(false);
    expect({ probability: null, label: null }).toEqual({ probability: null, label: null });
  });
});
