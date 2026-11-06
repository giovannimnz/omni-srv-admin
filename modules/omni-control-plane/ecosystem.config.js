module.exports = {
  apps: [
    {
      name: 'omni-control-plane',
      script: 'uvicorn',
      args: 'app.main:app --host 127.0.0.1 --port 34805 --workers 1',
      cwd: '/home/ubuntu/GitHub/omni-srv-admin',
      interpreter: 'none',
      autorestart: true,
      max_restarts: 10,
      env: {
        OMNI_CONTROL_PLANE_HOST: '127.0.0.1',
        OMNI_CONTROL_PLANE_PORT: '34805',
        ATIUS_SSO_IAM_PORT: '8015',
        ATIUS_IAM_STATE_FILE: '/var/tmp/atius_iam_control_plane_state.json',
        PYTHONUNBUFFERED: '1',
      },
    },
    {
      name: 'atius-sso-iam-gateway',
      script: 'uvicorn',
      args: 'app.main:app --host 127.0.0.1 --port 8015 --workers 1',
      cwd: '/home/ubuntu/GitHub/omni-srv-admin',
      interpreter: 'none',
      autorestart: true,
      max_restarts: 10,
      env: {
        OMNI_CONTROL_PLANE_HOST: '127.0.0.1',
        OMNI_CONTROL_PLANE_PORT: '34805',
        ATIUS_SSO_IAM_PORT: '8015',
        ATIUS_IAM_STATE_FILE: '/var/tmp/atius_iam_control_plane_state.json',
        PYTHONUNBUFFERED: '1',
      },
    },
  ],
};
