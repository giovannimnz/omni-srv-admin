import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { getFleetStatus, triggerProcessAction } from '../src/pm2.mjs';

test('Wave 3: PM2 Fleet status aggregates processes and flags anomalies', async () => {
  // Setup a lightweight mock server for the fleet dashboard API
  const mockServer = http.createServer((req, res) => {
    if (req.url === '/api/fleet' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        servers: [
          {
            id: 'atius-srv-1',
            status: 'online',
            processes: [
              { name: 'atius-web', status: 'online', memory: 150000000, restarts: 0 },
              { name: 'err-worker', status: 'errored', memory: 50000000, restarts: 12 }
            ]
          },
          {
            id: 'atius-srv-2',
            status: 'online',
            processes: [
              { name: 'ats-bot', status: 'online', memory: 800000000, restarts: 2 } // >500MB
            ]
          }
        ]
      }));
    } else if (req.url === '/api/action' && req.method === 'POST') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, message: 'Restarted successfully' }));
    }
  });

  await new Promise((resolve) => mockServer.listen(0, '127.0.0.1', resolve));
  const port = mockServer.address().port;
  const baseUrl = `http://127.0.0.1:${port}`;

  try {
    const report = await getFleetStatus({ baseUrl });
    assert.equal(report.totalProcesses, 3);
    assert.equal(report.online, 2);
    assert.equal(report.errored, 1);
    assert.equal(report.anomalies.length, 3, 'err-worker (errored + high_restarts) and ats-bot (high_memory)');

    const actionRes = await triggerProcessAction({
      baseUrl,
      serverId: 'atius-srv-1',
      action: 'restart',
      target: 'err-worker'
    });
    assert.equal(actionRes.success, true);
  } finally {
    mockServer.close();
  }
});
