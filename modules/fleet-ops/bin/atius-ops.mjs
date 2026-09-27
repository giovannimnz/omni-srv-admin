#!/usr/bin/env node
import { parseCliArgs, validateSafeTargetRoot } from '../src/core.mjs';
import { runPruneScan } from '../src/pruner.mjs';
import { getFleetStatus, triggerProcessAction } from '../src/pm2.mjs';
import { probeSsoEndpoint } from '../src/sso.mjs';

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

async function main() {
  const args = parseCliArgs();

  switch (args.command) {
    case 'prune': {
      const targetRoot = args.options.targetRoot || (args.target !== 'local' ? args.target : '/home/ubuntu/GitHub');
      validateSafeTargetRoot(targetRoot);

      const result = await runPruneScan({
        targetRoot,
        dryRun: args.dryRun
      });

      if (args.json) {
        console.log(JSON.stringify(result, null, 2));
      } else {
        console.log(`\n=== ATIUS OPS: PRUNE (${result.dryRun ? 'DRY-RUN' : 'APPLIED'}) ===`);
        console.log(`Target: ${targetRoot}`);
        console.log(`Candidates found: ${result.candidates.length}`);
        console.log(`Total space ${result.dryRun ? 'recoverable' : 'reclaimed'}: ${formatBytes(result.dryRun ? result.totalBytes : result.reclaimedBytes)}`);
        if (result.candidates.length > 0) {
          console.log('\nTop candidates:');
          result.candidates.slice(0, 10).forEach(c => console.log(` - [${c.type}] ${c.path} (${formatBytes(c.size)})`));
        }
        if (result.dryRun) {
          console.log('\nTo apply changes, run with: atius-ops prune --apply');
        }
      }
      break;
    }

    case 'pm2': {
      const action = args.subcommand || 'status';
      if (action === 'status') {
        const status = await getFleetStatus();
        if (args.json) {
          console.log(JSON.stringify(status, null, 2));
        } else {
          console.log(`\n=== ATIUS OPS: PM2 FLEET STATUS ===`);
          console.log(`Servers connected: ${status.totalServers} | Total Processes: ${status.totalProcesses}`);
          console.log(`Online: ${status.online} | Errored/Stopped: ${status.errored}`);
          if (status.anomalies.length > 0) {
            console.log('\nAnomalies detected:');
            status.anomalies.forEach(a => console.log(` - [${a.server}] ${a.process}: ${a.reason}`));
          } else {
            console.log('\nAll fleet processes are fully healthy.');
          }
        }
      } else if (action === 'restart') {
        const serverId = process.argv[3];
        const target = process.argv[4];
        if (!serverId || !target) {
          console.error('Usage: atius-ops pm2 restart <serverId> <target>');
          process.exit(1);
        }
        const res = await triggerProcessAction({ serverId, action: 'restart', target });
        console.log(JSON.stringify(res));
      }
      break;
    }

    case 'sso': {
      const target = process.argv[3] || 'https://auth.atius.com.br/realms/atius';
      const res = await probeSsoEndpoint(target);
      if (args.json) {
        console.log(JSON.stringify(res, null, 2));
      } else {
        console.log(`\n=== ATIUS OPS: SSO PROBE ===`);
        console.log(`Endpoint: ${res.url}`);
        console.log(`Status: ${res.status} (${res.healthy ? 'HEALTHY' : 'UNHEALTHY'})`);
        console.log(`Latency: ${res.latencyMs}ms`);
      }
      break;
    }

    case 'doctor': {
      console.log('\n=== ATIUS OPS: FLEET DOCTOR ===');
      const pm2Status = await getFleetStatus().catch(err => ({ error: err.message }));
      const ssoStatus = await probeSsoEndpoint('https://auth.atius.com.br/realms/atius');

      console.log(`1. PM2 Fleet Status: ${pm2Status.error ? 'DEGRADED (' + pm2Status.error + ')' : `${pm2Status.online}/${pm2Status.totalProcesses} processes online`}`);
      console.log(`2. SSO Central Auth: ${ssoStatus.healthy ? 'HEALTHY (' + ssoStatus.latencyMs + 'ms)' : 'DEGRADED'}`);
      break;
    }

    default:
      console.log(`
atius-ops - Autonomous Fleet Operations Controller

Usage:
  atius-ops prune [--apply] [--target=<dir>] [--json]
  atius-ops pm2 [status|restart <server> <target>] [--json]
  atius-ops sso [<url>] [--json]
  atius-ops doctor [--json]
`);
  }
}

main().catch(err => {
  console.error(`Error: ${err.message}`);
  process.exit(1);
});
