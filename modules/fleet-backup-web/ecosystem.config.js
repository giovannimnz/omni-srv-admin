module.exports = {
  apps: [
    {
      name: 'omni-backup-web',
      script: '/usr/bin/python3',
      args: '-m uvicorn backend.app:app --host 127.0.0.1 --port 8085 --workers 2',
      cwd: '/home/ubuntu/omni-srv-admin/modules/fleet-backup-web',
      env: {
        PYTHONPATH: '/home/ubuntu/omni-srv-admin/modules/fleet-backup-web:/home/ubuntu/omni-srv-admin/cli',
        OMNI_GDRIVE_BACKUP_ROOT: '/mnt/gdrive/ATIUS-SRV',
      },
      max_memory_restart: '256M',
      restart_delay: 5000,
      autorestart: true,
      max_restarts: 10,
    },
  ],
};
