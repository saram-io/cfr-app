const API_BASE = '/api/v1';

let authToken: string | null = localStorage.getItem('cfr_token');

export function setAuthToken(token: string | null) {
  authToken = token;
  if (token) {
    localStorage.setItem('cfr_token', token);
  } else {
    localStorage.removeItem('cfr_token');
  }
}

export function getAuthToken(): string | null {
  return authToken;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errDetail = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (data.detail) {
        errDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(errDetail);
  }

  return response.json() as Promise<T>;
}

export function getSnapshotDownloadUrl(snapshotId: string): string {
  return `${API_BASE}/backups/snapshots/${encodeURIComponent(snapshotId)}/download`;
}
