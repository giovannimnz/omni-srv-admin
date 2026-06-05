// ecosystem.config.cjs — PM2 config para fork-sync
// REPL/scheduler principal. Iniciar com: pm2 start ecosystem.config.cjs
module.exports = {
  apps: [
    {
      name: "fork-sync-scheduler",
      script: "/home/ubuntu/.local/bin/fork-sync",
      args: ["repl"],
      cwd: "/home/ubuntu/fork-sync",
      interpreter: "none",
      watch: false,
      autorestart: false,
      max_restarts: 0,
      env: {
        FORK_SYNC_ROOT: "/home/ubuntu/fork-sync",
        PYTHONUNBUFFERED: "1",
        FORK_SYNC_LOG_RETENTION_DAYS: "30",
        FORK_SYNC_KEEP_PER_PROJECT: "5",
        FORK_SYNC_MAX_LOG_SIZE_MB: "50"
      },
      log_file: "/home/ubuntu/fork-sync/logs/pm2-fork-sync.log",
      error_file: "/home/ubuntu/fork-sync/logs/pm2-fork-sync-error.log",
      out_file: "/home/ubuntu/fork-sync/logs/pm2-fork-sync-out.log",
      time: true,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss Z"
    }
  ]
};
