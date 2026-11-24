import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { dataSyncApi } from '../services/api';

describe('Activity Telemetry API Contract & State Filtering', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('1. getPRs(projectId) sends no state query', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ number: 1, title: 'PR 1' }],
    });
    global.fetch = fetchMock;

    const res = await dataSyncApi.getPRs('proj-123');
    expect(res).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const calledUrl = fetchMock.mock.calls[0][0];
    expect(calledUrl).toContain('/projects/proj-123/prs');
    expect(calledUrl).not.toContain('state=');
  });

  it('2. getPRs(projectId, "open") sends state=open', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    global.fetch = fetchMock;

    await dataSyncApi.getPRs('proj-123', 'open');
    const calledUrl = fetchMock.mock.calls[0][0];
    expect(calledUrl).toContain('/projects/proj-123/prs?state=open');
  });

  it('3. getPRs(projectId, "closed") sends state=closed', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    global.fetch = fetchMock;

    await dataSyncApi.getPRs('proj-123', 'closed');
    const calledUrl = fetchMock.mock.calls[0][0];
    expect(calledUrl).toContain('/projects/proj-123/prs?state=closed');
  });

  it('4. getPRs(projectId, "merged") sends state=merged', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    global.fetch = fetchMock;

    await dataSyncApi.getPRs('proj-123', 'merged');
    const calledUrl = fetchMock.mock.calls[0][0];
    expect(calledUrl).toContain('/projects/proj-123/prs?state=merged');
  });

  it('5. getPRs(projectId, "all") must omit state query (never send state=all)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    global.fetch = fetchMock;

    await dataSyncApi.getPRs('proj-123', 'all');
    const calledUrl = fetchMock.mock.calls[0][0];
    expect(calledUrl).toContain('/projects/proj-123/prs');
    expect(calledUrl).not.toContain('state=all');
    expect(calledUrl).not.toContain('state=');
  });

  it('6. getIssues(projectId) sends no state query', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ number: 10, title: 'Issue 10' }],
    });
    global.fetch = fetchMock;

    const res = await dataSyncApi.getIssues('proj-123');
    expect(res).toHaveLength(1);
    const calledUrl = fetchMock.mock.calls[0][0];
    expect(calledUrl).toContain('/projects/proj-123/issues');
    expect(calledUrl).not.toContain('state=');
  });

  it('7. getIssues(projectId, "open") sends state=open', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    global.fetch = fetchMock;

    await dataSyncApi.getIssues('proj-123', 'open');
    const calledUrl = fetchMock.mock.calls[0][0];
    expect(calledUrl).toContain('/projects/proj-123/issues?state=open');
  });

  it('8. getIssues(projectId, "closed") sends state=closed', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    global.fetch = fetchMock;

    await dataSyncApi.getIssues('proj-123', 'closed');
    const calledUrl = fetchMock.mock.calls[0][0];
    expect(calledUrl).toContain('/projects/proj-123/issues?state=closed');
  });

  it('9. getIssues(projectId, "all") must omit state query (never send state=all)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    global.fetch = fetchMock;

    await dataSyncApi.getIssues('proj-123', 'all');
    const calledUrl = fetchMock.mock.calls[0][0];
    expect(calledUrl).toContain('/projects/proj-123/issues');
    expect(calledUrl).not.toContain('state=all');
    expect(calledUrl).not.toContain('state=');
  });

  it('10. syncPRs succeeds on 200 OK', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, status: 'synced', fetched_count: 5 }),
    });
    global.fetch = fetchMock;

    const res = await dataSyncApi.syncPRs('proj-123');
    expect(res.success).toBe(true);
    expect(res.status).toBe('synced');
  });

  it('11. syncPRs aborts and throws timeout error when request exceeds timeoutMs', async () => {
    // Simulate fetch hanging forever
    const fetchMock = vi.fn().mockImplementation((_url, options) => {
      return new Promise((_resolve, reject) => {
        if (options?.signal) {
          options.signal.addEventListener('abort', () => {
            const err = new Error('The operation was aborted');
            err.name = 'AbortError';
            reject(err);
          });
        }
      });
    });
    global.fetch = fetchMock;

    // Call with very short timeout of 50ms
    await expect(dataSyncApi.syncPRs('proj-123', 50)).rejects.toThrow(
      'Synchronization timed out. Please try again.'
    );
  });

  it('12. syncIssues aborts and throws timeout error when request exceeds timeoutMs', async () => {
    const fetchMock = vi.fn().mockImplementation((_url, options) => {
      return new Promise((_resolve, reject) => {
        if (options?.signal) {
          options.signal.addEventListener('abort', () => {
            const err = new Error('The operation was aborted');
            err.name = 'AbortError';
            reject(err);
          });
        }
      });
    });
    global.fetch = fetchMock;

    await expect(dataSyncApi.syncIssues('proj-123', 50)).rejects.toThrow(
      'Synchronization timed out. Please try again.'
    );
  });
});
