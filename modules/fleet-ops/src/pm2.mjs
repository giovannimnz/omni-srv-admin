export async function getFleetStatus({ baseUrl = 'http://127.0.0.1:3210' } = {}) {
  const res = await fetch(`${baseUrl}/api/fleet`, { signal: AbortSignal.timeout(3000) });
  if (!res.ok) throw new Error(`Fleet API error: ${res.status}`);
  const data = await res.json();

  let totalProcesses = 0;
  let online = 0;
  let errored = 0;
  const anomalies = [];

  const serverList = Array.isArray(data.servers) ? data.servers : Object.values(data.servers || {});

  for (const server of serverList) {
    for (const proc of server.processes || []) {
      totalProcesses++;
      if (proc.status === 'online') {
        online++;
      } else {
        errored++;
        anomalies.push({ server: server.id, process: proc.name, reason: proc.status });
      }

      if (proc.memory > 500 * 1024 * 1024) { // >500MB
        anomalies.push({ server: server.id, process: proc.name, reason: 'high_memory', memory: proc.memory });
      }
      if (proc.restarts > 10) {
        anomalies.push({ server: server.id, process: proc.name, reason: 'high_restarts', restarts: proc.restarts });
      }
    }
  }

  return {
    totalServers: Array.isArray(data.servers) ? data.servers.length : Object.keys(data.servers || {}).length,
    totalProcesses,
    online,
    errored,
    anomalies,
    raw: data
  };
}

export async function triggerProcessAction({ baseUrl = 'http://127.0.0.1:3210', serverId, action, target }) {
  const res = await fetch(`${baseUrl}/api/action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ serverId, action, target }),
    signal: AbortSignal.timeout(5000)
  });
  if (!res.ok) throw new Error(`Action API error: ${res.status}`);
  return await res.json();
}
