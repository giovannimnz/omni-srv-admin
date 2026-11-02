---
name: omni-ci-fleet-orchestrator
description: "Protocolo canônico de governança, fila e orquestração de múltiplos agentes/sessões com autoridade soberana do Orchestrator, esteira de CI/CD (GitHub Actions) e controle de frota OCI/Landscape."
---

# Omni Srv Admin CI & Fleet Multi-Agent Orchestrator (Canônico)

Diretriz operacional e padrão soberano para a orquestração de múltiplos agentes, subagentes e sessões paralelas no repositório `omni-srv-admin` e em toda a Frota ATIUS (`atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `atius-srv-4`, `horistic-srv`, `aln-srv`).

## 1. Princípio da Autoridade Central Soberana (Orchestrator Role)
- **Centralização Total**: O **Orchestrator Central (`2251a1d9-3260-4bde-88e2-490063470338`)** é a **única autoridade máxima** responsável por:
  - Tomada de decisão definitiva sobre infraestrutura, rede (OCI DRG, DNS, Apache, K3s), segurança (Vault, TLS) e arquitetura da frota.
  - Administração, ordenação, despacho, acompanhamento e reordenação contínua da **Fila de Tarefas** de todos os Workers (W1, W2, etc.).
  - Aprovação de revisões de código, resolução de divergências e sincronização dos branches/worktrees.
  - **Serialização de Escrita (Writer Serialization)**: Apenas um agente modifica arquivos ou componentes sobrepostos por vez. Workers subordinados devem operar em escopos rigorosamente disjuntos.
  - **Exclusividade de Git Commit & Push**: Nenhum worker ou subagente realiza commit ou `git push` direto para o branch principal (`main`). Todas as alterações devem ser homologadas e enviadas exclusivamente pelo Orchestrator.

## 2. Regra de Ouro "Uma Execução por Vez" (Single-Run CI Verification)
- **Zero Pushes em Lote ou às Cegas**: É expressamente proibido realizar commits e pushes sequenciais sem antes aguardar o ciclo completo e obter a aprovação verde (100% SUCCESS) da execução do GitHub Actions do commit anterior.
- **Passo a Passo Mandatório**:
  1. **Validação Pré-Push Local (5 Gates Canônicos)**:
     ```bash
     python3 scripts/pre_ci_check.py
     ```
     Nenhum push é autorizado sem 5/5 Gates aprovados localmente (Git Hygiene, Python Syntax, Shell Syntax, Landscape Manifest e Test Suite).
  2. **Push Cirúrgico**: Enviar commit atômico contendo apenas as alterações validadas.
  3. **Acompanhamento Ativo em Tempo Real com `gh run watch`**:
     ```bash
     gh run watch
     # ou
     gh run list --limit 5
     ```
  4. **Aguardar Conclusão**: O pipeline deve atingir `completed / success` antes de qualquer outra tarefa ser despachada para o pipeline de entrega.

## 3. Protocolo Forense Obrigatório Pós-Falha (Root-Cause First)
- Se qualquer execução no GitHub Actions falhar (`completed / failure`), o Orchestrator DEVE imediatamente:
  1. Identificar o ID da execução: `gh run list --limit 5`
  2. Inspecionar o log detalhado da falha:
     ```bash
     gh run view <run-id> --log-failed
     ```
  3. Mapear a causa raiz exata (asserção com falha, arquivo, linha, variável de ambiente ou falso-negativo).
  4. Nunca realizar "tentativas de push às cegas" (blind pushes). Toda correção deve ter causa raiz comprovada e teste de regressão local antes do próximo push.

## 4. Governança da Frota & Landscape Control-Plane Directive
- **Regra Mandatória para Operações Multi-Servidor**: SEMPRE que qualquer operação envolver mais de um servidor da frota (`atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `atius-srv-4`, `horistic-srv`), NUNCA execute loops manuais seriais de SSH se a operação puder ser executada via **Landscape Control-Plane**:
  ```bash
  omni landscape run <script-id> --hosts all --wait --yes
  ```
- **Conectividade OCI DRG**: Tráfego Landscape trafega pela rota direta privada OCI DRG (`10.13.1.13 landscape.atius.com.br`) com latência sub-milissegundo (~0.6 ms).

## 5. CPU Guardrail & Resource Governance
- **Teto Estrito de CPU**: Builds, compilações, testes pesados e containeres nunca devem exceder 20% do total de CPU do host nos servidores `atius-srv-1`, `atius-srv-2`, `atius-srv-3` e `horistic-srv`. Em máquinas de 4 vCPUs, o limite absoluto padrão é 0.8 CPU.
- Usar contenção `omni srv1-ops resources run builds -- ...`, `systemd-run` com quota, `nice` e `ionice`.

## 6. Governança da Fila de Workers & Comunicação Ativa
- **Notificação dos Workers**: O Orchestrator comunica ativamente a todos os workers o estado da fila, as prioridades atuais e as travas de execução.
- **Estrutura de Fila**:
  - `[PENDING]`: Tarefas planejadas aguardando alocação de worker.
  - `[IN_PROGRESS]`: Tarefas atribuídas a worker específico com escopo delimitado e disjunto.
  - `[REVIEW]`: Código produzido pelo worker aguardando validação do Orchestrator.
  - `[CI_VERIFY]`: Em validação pelo Orchestrator contra o GitHub Actions (fila pausada para novos pushes).
  - `[DEPLOYED / DONE]`: Tarefa aprovada no CI verde e integrada com sucesso na frota.
- **Reordenação Dinâmica**: Caso uma falha ocorra ou uma dependência seja detectada, o Orchestrator suspende tarefas dependentes, reordena a fila e prioriza a resolução imediata do gargalo.

## 7. Contrato de Subordinação dos Workers (Worker Contract)
Todo worker operando sob a autoridade do Orchestrator deve cumprir:
1. Subordinação total às decisões do ORCH (`2251a1d9-3260-4bde-88e2-490063470338`).
2. Proibição absoluta de `git commit` ou `git push` direto na branch `main`.
3. Escopo cirúrgico e serialização de escrita (não alterar arquivos fora da sua atribuição sem autorização do ORCH).
4. Submeter entregas e relatórios ao ORCH no formato padrão de Coordenação de Frota.
