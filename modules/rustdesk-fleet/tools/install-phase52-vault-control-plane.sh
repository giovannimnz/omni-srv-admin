#!/usr/bin/env bash
# Transactional installer/rollback for the reviewed Phase 52 srv3 control-plane.
set -euo pipefail
set +x
IFS=$'\n\t'
umask 077

usage() {
  echo "usage: $0 [--install|--rollback] [--dry-run] [--root ABSOLUTE] [--authorized-key-file FILE --expected-fingerprint SHA256:FULL]" >&2
  exit 64
}

action=install
dry_run=false
root=/
key_file=''
expected_fingerprint=''
while (($#)); do
  case "$1" in
    --install) action=install; shift ;;
    --rollback) action=rollback; shift ;;
    --dry-run) dry_run=true; shift ;;
    --root) (($# >= 2)) || usage; root=$2; shift 2 ;;
    --authorized-key-file) (($# >= 2)) || usage; key_file=$2; shift 2 ;;
    --expected-fingerprint) (($# >= 2)) || usage; expected_fingerprint=$2; shift 2 ;;
    *) usage ;;
  esac
done
[[ "$root" == /* && "$root" != '' && -d "$root" && ! -L "$root" ]] || usage
root=$(realpath -e -- "$root")
# Production identity contract: dispatcher_install_mode=0o755,
# control_plane_uid=0, control_plane_gid=0. Non-root --root is fixture_root_relative_runtime.
[[ "$root" != / || $(id -u) -eq 0 || "$dry_run" == true ]] || { echo 'root-required' >&2; exit 2; }
[[ -z "$key_file" && -z "$expected_fingerprint" || -n "$key_file" && -n "$expected_fingerprint" ]] || usage
[[ -z "$expected_fingerprint" || "$expected_fingerprint" =~ ^SHA256:[A-Za-z0-9+/]{43}$ ]] || usage

script_dir=$(unset CDPATH; cd -- "$(dirname -- "$0")" && pwd -P)
backend_source=$script_dir/atius-vault-export-rustdesk-phase52
dispatcher_source=$script_dir/atius-vault-export-ssh-phase52
writer_source=$script_dir/atius-vault-phase52-write
contract_source=$script_dir/../contracts/phase52-vault-control-plane.json
for source in "$backend_source" "$dispatcher_source" "$writer_source" "$contract_source"; do
  [[ -f "$source" && ! -L "$source" ]] || { echo 'managed-source-missing' >&2; exit 2; }
done

if [[ -n "$key_file" ]]; then
  [[ -f "$key_file" && ! -L "$key_file" ]] || { echo 'authorized-key-invalid' >&2; exit 2; }
  actual_fingerprint=$(ssh-keygen -lf "$key_file" -E sha256 2>/dev/null | awk '{print $2}')
  [[ "$actual_fingerprint" == "$expected_fingerprint" ]] || { echo 'authorized-key-fingerprint-mismatch' >&2; exit 2; }
fi

if "$dry_run"; then
  [[ "$root" != / && -n "$key_file" ]] || { echo 'dry-run-authorized-key-proof-required' >&2; exit 2; }
  authorized_fixture=$root/home/ubuntu/.ssh/authorized_keys
  [[ -f "$authorized_fixture" && ! -L "$authorized_fixture" ]] || { echo 'dry-run-authorized-key-proof-required' >&2; exit 2; }
  if ! python3 - "$action" "$root" "$backend_source" "$dispatcher_source" "$writer_source" "$contract_source" "$key_file" "$expected_fingerprint" <<'PY'
import hashlib,json,pathlib,stat,sys
action=sys.argv[1]; root=pathlib.Path(sys.argv[2])
sources=[pathlib.Path(item) for item in sys.argv[3:7]]
key=pathlib.Path(sys.argv[7]); fingerprint=sys.argv[8]
authorized=root/'home/ubuntu/.ssh/authorized_keys'; info=authorized.lstat()
key_tokens=key.read_text().strip().split(); blob=key_tokens[1]
rows=authorized.read_text().splitlines(); matches=[]
for index,line in enumerate(rows):
 tokens=line.split()
 try: key_index=next(i for i,item in enumerate(tokens) if item.startswith(('ssh-','ecdsa-')))
 except StopIteration: continue
 if key_index+1<len(tokens) and tokens[key_index+1]==blob: matches.append((index,key_index,tokens))
if len(matches)!=1: raise SystemExit('authorized-key-entry-not-unique')
index,key_index,tokens=matches[0]; old_options=' '.join(tokens[:key_index]); old_forced_command=next((x for x in tokens[:key_index] if x.startswith('command=')), '')
expected_legacy='command="/home/ubuntu/.local/bin/atius-vault-export-ssh",no-agent-forwarding,no-X11-forwarding,no-pty,no-port-forwarding'
if old_options != expected_legacy: raise SystemExit('legacy-authorized-key-policy-drift')
replacement='restrict,no-user-rc,command="/usr/local/sbin/atius-vault-export-ssh-phase52" '+' '.join(tokens[key_index:])
print(json.dumps({
 "action":action,"status":"PASS","dry_run":True,"live_write_performed":False,
 "managed_source_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
 "authorized_key_fingerprint_verified":bool(fingerprint),"old_forced_command":old_forced_command,
 "old_options":old_options,"authorized_keys_uid":info.st_uid,"authorized_keys_gid":info.st_gid,
 "authorized_keys_mode":format(stat.S_IMODE(info.st_mode),'04o'),"replacement_count":1,
 "replacement_line_sha256":hashlib.sha256(replacement.encode()).hexdigest(),
 "key_rotation_performed":False,"secret_material_present":False},sort_keys=True,separators=(",",":")))
PY
  then
    exit 2
  fi
  exit 0
fi

if ! python3 - "$action" "$root" "$backend_source" "$dispatcher_source" "$writer_source" "$contract_source" "$key_file" "$expected_fingerprint" <<'PY'
import fcntl,hashlib,json,os,pathlib,shutil,stat,subprocess,sys,tempfile
action,root_s,backend_s,dispatcher_s,writer_s,contract_s,key_s,fingerprint=sys.argv[1:]
root=pathlib.Path(root_s); backend=pathlib.Path(backend_s); dispatcher=pathlib.Path(dispatcher_s); writer=pathlib.Path(writer_s)
state=root/'var/lib/atius-vault-phase52'; manifest=state/'install-state.json'; backup=state/'rollback'
targets={
 'backend':root/'usr/local/sbin/atius-vault-export-rustdesk-phase52',
 'dispatcher':root/'usr/local/sbin/atius-vault-export-ssh-phase52',
 'writer':root/'usr/local/sbin/atius-vault-phase52-write',
 'rustdesk_profile':root/'etc/atius-vault/profiles/rustdesk-phase52-v1.json',
 'rclone_profile':root/'etc/atius-vault/profiles/rclone-giovanni-drive-phase52-v1.json',
 'sudoers':root/'etc/sudoers.d/atius-vault-phase52',
 'authorized_keys':root/'home/ubuntu/.ssh/authorized_keys'}
generated={
 'rustdesk_profile':json.dumps({'protocol':'rustdesk-phase52-v1','references':[{'vault_path':'kv/atius/rustdesk/server','field':'private_key'},{'vault_path':'kv/atius/rustdesk/server','field':'public_key'},{'vault_path':'kv/atius/rustdesk/targets/atius-srv-1','field':'permanent_password'},{'vault_path':'kv/atius/rustdesk/targets/atius-srv-2','field':'permanent_password'},{'vault_path':'kv/atius/rustdesk/targets/atius-srv-3','field':'permanent_password'},{'vault_path':'kv/atius/rustdesk/targets/horistic-srv','field':'permanent_password'},{'vault_path':'kv/atius/rustdesk/targets/giovanni-w11-pc','field':'permanent_password'}]},sort_keys=True,separators=(',',':'))+'\n',
 'rclone_profile':json.dumps({'protocol':'rclone-giovanni-drive-phase52-v1','references':[{'vault_path':'kv/atius/fleet-backup/rclone/giovanni-drive','field':'rclone_conf'}]},sort_keys=True,separators=(',',':'))+'\n',
 'sudoers':'ubuntu ALL=(root) NOPASSWD: /usr/local/sbin/atius-vault-export-rustdesk-phase52 rustdesk-phase52-v1, /usr/local/sbin/atius-vault-export-rustdesk-phase52 rclone-giovanni-drive-phase52-v1\n'}
dispatcher_install_mode=0o755; control_plane_uid=0; control_plane_gid=0
if root != pathlib.Path('/'):
 control_plane_uid=root.stat().st_uid; control_plane_gid=root.stat().st_gid
def validate_parent_chain(path):
 current=path.parent
 while current != root.parent:
  info=current.lstat()
  if current.is_symlink() or not stat.S_ISDIR(info.st_mode): raise SystemExit('parent-chain-drift')
  if current == root: break
  current=current.parent
def prepare_parent_chain(path):
 if path == root: return
 missing=[]; current=path
 while current != root:
  if current.exists() or current.is_symlink():
   info=current.lstat()
   if current.is_symlink() or not stat.S_ISDIR(info.st_mode): raise SystemExit('parent-chain-drift')
  else: missing.append(current)
  current=current.parent
 root_info=root.lstat()
 if root.is_symlink() or not stat.S_ISDIR(root_info.st_mode): raise SystemExit('parent-chain-drift')
 for directory in reversed(missing):
  os.mkdir(directory,0o700)
  os.chown(directory,control_plane_uid,control_plane_gid)
 validate_parent_chain(path/'probe')
def fsync_parent(path):
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(fd)
 finally: os.close(fd)
def atomic(path,data,mode,uid=None,gid=None):
 prepare_parent_chain(path.parent); validate_parent_chain(path); fd,name=tempfile.mkstemp(dir=path.parent,prefix='.'+path.name+'.')
 try:
  os.fchmod(fd,mode)
  if uid is not None and gid is not None: os.fchown(fd,uid,gid)
  os.write(fd,data); os.fsync(fd); os.close(fd); os.replace(name,path); fsync_parent(path)
 finally:
  try: os.close(fd)
  except OSError: pass
  pathlib.Path(name).unlink(missing_ok=True)
def identity(path):
 info=path.lstat()
 if path.is_symlink(): raise SystemExit('symlink-drift')
 if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1: raise SystemExit('hardlink-drift')
 return info
def identity_record(path):
 info=identity(path)
 return {'st_dev':info.st_dev,'st_ino':info.st_ino,'st_uid':info.st_uid,'st_gid':info.st_gid,'mode':stat.S_IMODE(info.st_mode),'st_nlink':info.st_nlink}
def validate_control_dir(path,mode,label):
 info=path.lstat()
 if path.is_symlink() or not stat.S_ISDIR(info.st_mode) or info.st_uid!=control_plane_uid or info.st_gid!=control_plane_gid or stat.S_IMODE(info.st_mode)!=mode:
  raise SystemExit(label+'-identity-drift')
def validate_control_file(path,mode,label):
 info=path.lstat()
 if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=control_plane_uid or info.st_gid!=control_plane_gid or stat.S_IMODE(info.st_mode)!=mode:
  raise SystemExit(label+'-identity-drift')
def prepare_control_dir(path,mode,label):
 if path.exists() or path.is_symlink():
  validate_control_dir(path,mode,label)
  return
 existing=[]; current=path
 while current != root:
  if current.exists() or current.is_symlink(): existing.append(current)
  current=current.parent
 for item in reversed(existing):
  info=item.lstat()
  if item.is_symlink() or not stat.S_ISDIR(info.st_mode) or info.st_uid!=control_plane_uid or info.st_gid!=control_plane_gid or stat.S_IMODE(info.st_mode)&0o022:
   raise SystemExit(label+'-parent-identity-drift')
 path.mkdir(parents=True,mode=mode,exist_ok=True)
 os.chmod(path,mode)
 validate_control_dir(path,mode,label)
def validate_sudoers(path):
 result=subprocess.run(['/usr/sbin/visudo','-cf',str(path)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
 if result.returncode: raise SystemExit('visudo-validation-failed')
prepare_control_dir(state,0o700,'control-plane-state')
lock_path=state/'control-plane-global.lock'; lock_fd=os.open(lock_path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
lock_info=os.fstat(lock_fd)
if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_nlink!=1 or lock_info.st_uid!=control_plane_uid or lock_info.st_gid!=control_plane_gid or stat.S_IMODE(lock_info.st_mode)!=0o600:
 raise SystemExit('control-plane-lock-identity-drift')
fcntl.flock(lock_fd,fcntl.LOCK_EX)
row_keys={'had_previous','previous_mode','previous_uid','previous_gid','previous_sha256','installed_sha256','installed_identity'}
def load_manifest(statuses):
 if not manifest.is_file(): raise SystemExit('rollback-state-missing')
 validate_control_file(manifest,0o600,'control-plane-manifest')
 payload=json.loads(manifest.read_text())
 if not isinstance(payload,dict) or set(payload)!={'schema','status','key_fingerprint','key_rotation_performed','targets'} or payload.get('schema')!=3 or payload.get('status') not in statuses or set(payload.get('targets',{}))!=set(targets): raise SystemExit('control-plane-manifest-shape-drift')
 if any(not isinstance(row,dict) or set(row)!=row_keys for row in payload['targets'].values()): raise SystemExit('control-plane-manifest-shape-drift')
 return payload
def validate_previous(name,row):
 previous=backup/name
 if row['had_previous']:
  if not previous.is_file() or previous.is_symlink() or previous.stat().st_nlink!=1 or hashlib.sha256(previous.read_bytes()).hexdigest()!=row['previous_sha256']: raise SystemExit('rollback-backup-drift')
 elif previous.exists() or previous.is_symlink(): raise SystemExit('rollback-backup-drift')
def expected_installed_metadata(name,row):
 if name=='authorized_keys':
  if not row['had_previous']: raise SystemExit('installed-target-identity-drift')
  return row['previous_mode'],row['previous_uid'],row['previous_gid']
 modes={'backend':0o700,'dispatcher':dispatcher_install_mode,'writer':0o700,'rustdesk_profile':0o600,'rclone_profile':0o600,'sudoers':0o440}
 return modes[name],control_plane_uid,control_plane_gid
def target_state(name,target,row,allow_restored):
 validate_previous(name,row)
 if target.exists() or target.is_symlink():
  info=identity(target); digest=hashlib.sha256(target.read_bytes()).hexdigest()
  if row.get('installed_sha256') and digest==row['installed_sha256']:
   record=identity_record(target)
   if row.get('installed_identity') is not None:
    if record!=row['installed_identity']: raise SystemExit('installed-target-identity-drift')
   else:
    expected_mode,expected_uid,expected_gid=expected_installed_metadata(name,row)
    if stat.S_IMODE(info.st_mode)!=expected_mode or info.st_uid!=expected_uid or info.st_gid!=expected_gid: raise SystemExit('installed-target-identity-drift')
   return 'installed'
  if allow_restored and row['had_previous'] and digest==row['previous_sha256'] and stat.S_IMODE(info.st_mode)==row['previous_mode'] and info.st_uid==row['previous_uid'] and info.st_gid==row['previous_gid']:
   return 'restored'
  raise SystemExit('installed-target-drift')
 if allow_restored and not row['had_previous']: return 'restored'
 raise SystemExit('installed-target-missing')
def restore_target(name,target,row):
 if row['had_previous']:
  previous=backup/name
  atomic(target,previous.read_bytes(),row['previous_mode'],row['previous_uid'],row['previous_gid'])
 else: target.unlink()
if manifest.exists() and action=='install':
 payload=load_manifest({'installing','installed'})
 states={name:target_state(name,target,payload['targets'][name],payload['status']=='installing') for name,target in targets.items()}
 if payload['status']=='installed':
  print('{"action":"install","recovered":true,"secret_material_present":false,"status":"PASS"}')
  raise SystemExit(0)
 if all(value=='installed' for value in states.values()):
  for name,target in targets.items():
   if payload['targets'][name]['installed_identity'] is None: payload['targets'][name]['installed_identity']=identity_record(target)
  payload['status']='installed'; atomic(manifest,(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n').encode(),0o600)
  print('{"action":"install","recovered":true,"secret_material_present":false,"status":"PASS"}')
  raise SystemExit(0)
 for name,target in targets.items():
  if states[name]=='installed': restore_target(name,target,payload['targets'][name])
 manifest.unlink(); shutil.rmtree(backup)
if action=='rollback':
 payload=load_manifest({'installing','installed','rolling-back'})
 allow_restored=payload['status'] in {'installing','rolling-back'}
 states={name:target_state(name,target,payload['targets'][name],allow_restored) for name,target in targets.items()}
 payload['status']='rolling-back'; atomic(manifest,(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n').encode(),0o600)
 for name,target in targets.items():
  if states[name]=='installed': restore_target(name,target,payload['targets'][name])
 shutil.rmtree(state)
 print('{"action":"rollback","secret_material_present":false,"status":"PASS"}')
 raise SystemExit(0)
if manifest.exists(): raise SystemExit('install-state-already-exists')
if not key_s: raise SystemExit('authorized-key-proof-required')
key_source=pathlib.Path(key_s); key_info=identity(key_source)
key_line=key_source.read_text().strip()
if '\n' in key_line or not key_line.startswith(('ssh-ed25519 ','ssh-rsa ','ecdsa-')): raise SystemExit('authorized-key-invalid')
authorized=targets['authorized_keys']
authorized_info=identity(authorized)
existing=authorized.read_text().splitlines()
key_blob=key_line.split()[1]
matches=[]
for index,line in enumerate(existing):
 tokens=line.split()
 try: key_index=next(i for i,item in enumerate(tokens) if item.startswith(('ssh-','ecdsa-')))
 except StopIteration: continue
 if key_index+1<len(tokens) and tokens[key_index+1]==key_blob: matches.append((index,key_index,tokens))
if len(matches)!=1: raise SystemExit('authorized-key-entry-not-unique')
line_index,key_index,tokens=matches[0]
expected_legacy='command="/home/ubuntu/.local/bin/atius-vault-export-ssh",no-agent-forwarding,no-X11-forwarding,no-pty,no-port-forwarding'
if ' '.join(tokens[:key_index]) != expected_legacy: raise SystemExit('legacy-authorized-key-policy-drift')
preserved_key=' '.join(tokens[key_index:])
entry='restrict,no-user-rc,command="/usr/local/sbin/atius-vault-export-ssh-phase52" '+preserved_key
existing[line_index]=entry
payload={'schema':3,'status':'installing','key_fingerprint':fingerprint,'key_rotation_performed':False,'targets':{}}
prepare_control_dir(backup,0o700,'control-plane-backup')
for name,target in targets.items():
 had=target.exists() or target.is_symlink(); row={'had_previous':had,'previous_mode':None,'previous_uid':None,'previous_gid':None,'previous_sha256':None,'installed_sha256':None,'installed_identity':None}
 if had:
  info=identity(target); data=target.read_bytes(); row['previous_mode']=stat.S_IMODE(info.st_mode); row['previous_uid']=info.st_uid; row['previous_gid']=info.st_gid; row['previous_sha256']=hashlib.sha256(data).hexdigest(); atomic(backup/name,data,0o600)
 payload['targets'][name]=row
atomic(manifest,(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n').encode(),0o600)
validate_control_file(manifest,0o600,'control-plane-manifest')
def install_managed(name,data,mode,uid,gid):
 row=payload['targets'][name]
 row['installed_sha256']=hashlib.sha256(data).hexdigest()
 atomic(manifest,(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n').encode(),0o600)
 atomic(targets[name],data,mode,uid,gid)
 row['installed_identity']=identity_record(targets[name])
 atomic(manifest,(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n').encode(),0o600)
try:
 install_managed('backend',backend.read_bytes(),0o700,control_plane_uid,control_plane_gid)
 install_managed('dispatcher',dispatcher.read_bytes(),dispatcher_install_mode,control_plane_uid,control_plane_gid)
 install_managed('writer',writer.read_bytes(),0o700,control_plane_uid,control_plane_gid)
 dispatcher_info=identity(targets['dispatcher'])
 if stat.S_IMODE(dispatcher_info.st_mode)!=dispatcher_install_mode or dispatcher_info.st_uid!=control_plane_uid or dispatcher_info.st_gid!=control_plane_gid: raise RuntimeError('dispatcher-installed-identity-drift')
 install_managed('rustdesk_profile',generated['rustdesk_profile'].encode(),0o600,control_plane_uid,control_plane_gid)
 install_managed('rclone_profile',generated['rclone_profile'].encode(),0o600,control_plane_uid,control_plane_gid)
 sudoers_stage=state/'sudoers.stage'; atomic(sudoers_stage,generated['sudoers'].encode(),0o440); validate_sudoers(sudoers_stage)
 install_managed('sudoers',sudoers_stage.read_bytes(),0o440,control_plane_uid,control_plane_gid); validate_sudoers(targets['sudoers']); sudoers_stage.unlink()
 authorized_data=('\n'.join(existing)+'\n').encode(); install_managed('authorized_keys',authorized_data,stat.S_IMODE(authorized_info.st_mode),authorized_info.st_uid,authorized_info.st_gid)
 if sum(key_blob in line.split() for line in authorized.read_text().splitlines()) != 1: raise RuntimeError('authorized-key-entry-not-unique')
except BaseException:
 for name,target in targets.items():
  row=payload['targets'][name]; previous=backup/name
  if row['had_previous']: atomic(target,previous.read_bytes(),row['previous_mode'],row['previous_uid'],row['previous_gid'])
  else: target.unlink(missing_ok=True)
 shutil.rmtree(state)
 raise
payload['status']='installed'
atomic(manifest,(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n').encode(),0o600)
validate_control_file(manifest,0o600,'control-plane-manifest')
print('{"action":"install","key_rotation_performed":false,"secret_material_present":false,"status":"PASS"}')
PY
then
  exit 2
fi
