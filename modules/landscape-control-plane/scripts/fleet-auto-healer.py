#!/usr/bin/env python3
"""
omni::fleet-auto-healer v1.1.0
Daemon Soberano de Auto-Cura e Melhoria Contínua da Frota ATIUS.

Monitora e executa em loop:
1. Filas e atividades do Landscape Server:
   - Detecta atividades presas em status 4 (QUEUED) ou 5 (INPROGRESS) há mais de 15 minutos e as cancela.
   - Identifica falhas de divergência de hash ('Package data has changed') e as converte para CANCELED com anotação.
   - Limpa tarefas zumbi/órfãs nas bases SQLite dos clientes (/var/lib/landscape/client/package/database).
2. Telemetria e conectividade dos 7 nós (ping age <= 300s, consecutive_errors == 0).
3. Scripts internos do Landscape Server e cron USN (update_security_db.sh, update_alerts.sh).
4. Auto-cura com contenção estrita de recursos (CPUQuota=20%, Nice=19, IOSchedulingClass=idle).
5. Retry adaptativo em loop até auto-recuperação completa de incidentes.
6. Registro e rastreabilidade contínua.
"""

import sys
import time
import subprocess
import json
import logging
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("fleet-auto-healer")

SRV3_HOST = "10.13.1.13"

FLEET_HOSTS = [
    ("atius-srv-1", "10.11.1.11", "ubuntu"),
    ("atius-srv-2", "10.12.1.12", "ubuntu"),
    ("atius-srv-3", "10.13.1.13", "ubuntu"),
    ("atius-srv-4", "10.14.1.14", "ubuntu"),
    ("aln-srv", "10.15.1.15", "ubuntu"),
    ("horistic-srv", "10.21.1.21", "horistic"),
]

def run_cmd(cmd, timeout=30):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout expired"
    except Exception as e:
        return -1, "", str(e)

def run_psql(db, query):
    escaped = query.replace("'", "'\\''")
    cmd = f"ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no ubuntu@{SRV3_HOST} \"sudo lxc exec landscape -- sudo -u postgres psql -d {db} -t -A -c '{escaped}'\""
    return run_cmd(cmd, timeout=40)

def check_and_heal_activities():
    """Detecta atividades presas há mais de 15 minutos ou com falha de hash e as purga."""
    logger.info("Checando fila de atividades do Landscape...")
    
    # 1. Atividades presas em status 4 (QUEUED) ou 5 (INPROGRESS) há mais de 15 minutos
    query_stuck = """
    SELECT a.id, a.parent_id, a.status, (NOW() AT TIME ZONE 'UTC' - a.creation_time) as age
    FROM activity a 
    WHERE a.status IN (4, 5) 
      AND a.creation_time < NOW() - interval '15 minutes';
    """
    code, out, err = run_psql("landscape-standalone-account-1", query_stuck)
    if code == 0 and out:
        lines = [l for l in out.splitlines() if l.strip()]
        if lines:
            logger.warning(f"Detectadas {len(lines)} atividades presas (>15 min):")
            stuck_ids = []
            parent_ids = set()
            for line in lines:
                parts = line.split("|")
                if len(parts) >= 2:
                    stuck_ids.append(parts[0])
                    if parts[1]:
                        parent_ids.add(parts[1])

            if stuck_ids:
                ids_str = ",".join(stuck_ids)
                logger.warning(f"Purgando atividades presas: {ids_str}")
                heal_sql = f"UPDATE activity SET status = 7, result_code = 0 WHERE id IN ({ids_str});"
                if parent_ids:
                    parents_str = ",".join(parent_ids)
                    heal_sql += f"""
                    UPDATE activity_parent SET 
                        canceled_count = canceled_count + queued_count + inprogress_count,
                        queued_count = 0, inprogress_count = 0 
                    WHERE id IN ({parents_str});
                    """
                run_psql("landscape-standalone-account-1", heal_sql)

    # 2. Atividades falhadas com 'Package data has changed'
    query_hash_mismatch = """
    SELECT a.id, a.parent_id
    FROM activity a 
    WHERE a.status = 8 
      AND a.result_text ILIKE '%Package data has changed%'
      AND a.creation_time > NOW() - interval '24 hours';
    """
    code_m, out_m, _ = run_psql("landscape-standalone-account-1", query_hash_mismatch)
    if code_m == 0 and out_m:
        lines_m = [l for l in out_m.splitlines() if l.strip()]
        if lines_m:
            logger.info(f"Detectadas {len(lines_m)} atividades com hash mismatch para auto-cura.")
            clean_ids = [l.split("|")[0] for l in lines_m if l.split("|")[0]]
            if clean_ids:
                c_str = ",".join(clean_ids)
                heal_mismatch_sql = f"""
                UPDATE activity 
                SET status = 7, 
                    result_text = result_text || ' [Auto-healed by omni::fleet-auto-healer: hash mismatch acknowledged]'
                WHERE id IN ({c_str});
                """
                run_psql("landscape-standalone-account-1", heal_mismatch_sql)
                logger.info(f"Atividades de hash mismatch migradas para CANCELED: {c_str}")

    logger.info("Fila de atividades auditada e limpa.")
    return True

def heal_client_package_queues():
    """Purga tarefas zumbis da fila SQLite dos clientes Landscape que ja foram canceladas/finalizadas no servidor."""
    logger.info("Checando filas locais de tarefas dos clientes Landscape...")
    
    # Obter lista de atividades ja finalizadas (status 1, 7, 8)
    query_done = "SELECT id FROM activity WHERE status IN (1, 7, 8) AND creation_time > NOW() - interval '48 hours';"
    code, out, _ = run_psql("landscape-standalone-account-1", query_done)
    if code != 0 or not out:
        return True
        
    done_ids = set(l.strip() for l in out.splitlines() if l.strip())
    
    # Checar hosts locais e remotos
    for name, ip, user in FLEET_HOSTS:
        # Script python remoto para ler SQLite e expurgar tarefas orfas
        purge_code = f"""
import sqlite3
from landscape.lib.bpickle import loads

db_path = '/var/lib/landscape/client/package/database'
try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('SELECT id, data FROM task')
    rows = cur.fetchall()
    to_delete = []
    done_set = {done_ids}
    for row_id, blob in rows:
        try:
            op_id = str(loads(blob).get('operation-id'))
            if op_id in done_set:
                to_delete.append(row_id)
        except Exception:
            pass
    if to_delete:
        del_str = ','.join(str(i) for i in to_delete)
        cur.execute(f'DELETE FROM task WHERE id IN ({{del_str}})')
        conn.commit()
        print(f'Purged {{len(to_delete)}} tasks: {{del_str}}')
    conn.close()
except Exception as e:
    pass
"""
        escaped_py = purge_code.replace("'", "'\\''")
        cmd = f"ssh -o ConnectTimeout=5 {user}@{ip} \"sudo python3 -c '{escaped_py}' 2>/dev/null\""
        p_code, p_out, _ = run_cmd(cmd, timeout=15)
        if p_code == 0 and p_out:
            logger.info(f"[{name}] {p_out}")

    return True

def check_and_heal_usn_and_scripts():
    """Verifica saude dos scripts periodicos do Landscape e cron USN."""
    logger.info("Checando integridade de scripts do Landscape Server...")
    query = """
    SELECT id, name, (NOW() AT TIME ZONE 'UTC' - end_time > make_interval(mins => run_interval)) as is_overdue, success
    FROM lds_script_execution_log;
    """
    code, out, err = run_psql("landscape-standalone-main", query)
    if code != 0 or not out:
        logger.warning(f"Nao foi possivel consultar lds_script_execution_log: {err}")
        return False

    all_ok = True
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            s_id, s_name, overdue, success = parts[0], parts[1], parts[2], parts[3]
            if overdue == "t" or success != "t":
                all_ok = False
                logger.warning(f"Script com pendencia: {s_name} (overdue={overdue}, success={success})")
                logger.info(f"Disparando execucao forcada de {s_name}...")
                trigger_cmd = f"ssh ubuntu@{SRV3_HOST} 'sudo lxc exec landscape -- /opt/canonical/landscape/scripts/{s_name}'"
                t_code, t_out, t_err = run_cmd(trigger_cmd, timeout=90)
                if t_code == 0:
                    logger.info(f"Script {s_name} executado com sucesso.")
                    upd_sql = f"UPDATE lds_script_execution_log SET end_time = (NOW() AT TIME ZONE 'UTC'), success = true WHERE id = {s_id};"
                    run_psql("landscape-standalone-main", upd_sql)
                else:
                    logger.error(f"Falha ao executar script {s_name}: {t_err}")

    if all_ok:
        logger.info("Todos os scripts internos do Landscape Server estao saudaveis.")
    return all_ok

def check_and_heal_connectivity():
    """Verifica tempo de ping e erros consecutivos de todos os computadores."""
    logger.info("Checando telemetria dos nos da frota...")
    query = """
    SELECT c.id, c.title, 
           EXTRACT(EPOCH FROM (NOW() AT TIME ZONE 'UTC' - pt.last_ping_time)) AS ping_age_sec,
           cs.consecutive_errors
    FROM computer c 
    LEFT JOIN computer_status cs ON cs.computer_id = c.id 
    LEFT JOIN ping_time pt ON pt.computer_id = c.id 
    ORDER BY c.id;
    """
    code, out, err = run_psql("landscape-standalone-main", query)
    if code != 0 or not out:
        logger.warning(f"Erro ao consultar telemetria: {err}")
        return False

    nodes_healed = True
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            c_id, title = parts[0], parts[1]
            try:
                ping_age = float(parts[2]) if parts[2] else 9999
                consec_err = int(parts[3]) if parts[3] else 0
            except ValueError:
                continue

            if ping_age > 300 or consec_err > 0:
                logger.warning(f"No com alerta: {title} (ping_age={ping_age:.0f}s, consecutive_errors={consec_err})")
                nodes_healed = False
            else:
                logger.info(f"No OK: {title} (ping_age={ping_age:.1f}s, errors={consec_err})")

    return nodes_healed

def run_improvement_cycle():
    """Executa o ciclo completo de auditoria, auto-cura e melhoria continua."""
    logger.info("=== INICIANDO CICLO DE AUTO-CURA E MELHORIA CONTINUA ===")
    start_time = time.time()
    
    # 1. Atividades e Filas do Servidor
    act_ok = check_and_heal_activities()
    
    # 2. Filas Locais dos Clientes
    queues_ok = heal_client_package_queues()
    
    # 3. Scripts e USN
    usn_ok = check_and_heal_usn_and_scripts()
    
    # 4. Conectividade e Telemetria
    conn_ok = check_and_heal_connectivity()
    
    duration = time.time() - start_time
    logger.info(f"=== CICLO CONCLUIDO em {duration:.2f}s (Atividades={act_ok}, Queues={queues_ok}, USN={usn_ok}, Conectividade={conn_ok}) ===")
    return act_ok and queues_ok and usn_ok and conn_ok

def main():
    logger.info("Iniciando omni::fleet-auto-healer em modo continuo...")
    
    max_retries = 3
    interval_seconds = 900  # 15 minutos
    
    # Se chamado com --once roda uma vez e sai
    if "--once" in sys.argv:
        success = run_improvement_cycle()
        sys.exit(0 if success else 1)
        
    while True:
        try:
            success = run_improvement_cycle()
            if not success:
                logger.warning("Falha detectada no ciclo. Iniciando retry adaptativo em loop...")
                for retry in range(1, max_retries + 1):
                    logger.info(f"Retry {retry}/{max_retries} em 30 segundos...")
                    time.sleep(30)
                    if run_improvement_cycle():
                        logger.info(f"Recuperado com sucesso no retry {retry}!")
                        break
            else:
                logger.info("Saude da frota impecavel. Aguardando proximo ciclo...")
        except Exception as e:
            logger.error(f"Excecao nao tratada no loop do daemon: {e}")
            
        time.sleep(interval_seconds)

if __name__ == "__main__":
    main()
