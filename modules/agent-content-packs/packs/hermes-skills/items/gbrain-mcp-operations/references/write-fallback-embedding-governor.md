# GBrain write fallback — embedding governor, timeline e capture CLI

Use quando `put_page` falha ou expira durante chunk/embed, mas o GBrain continua legível.

## Sintomas observados

- `MCP call timed out after 120.0s` durante `put_page`.
- `embedding governor queue timeout before dispatch` após retries internos.
- O servidor pode continuar respondendo a `get_health`, `get_page` e timeline mesmo quando o pipeline de embed está saturado.

Não transforme isso em regra de que o MCP “não funciona”; é congestionamento transitório do write pipeline.

## Sequência segura

1. Após timeout, chame `get_page(slug)` antes de reenviar. O write pode ter concluído depois do timeout do cliente.
2. Se a página não existe e um retry curto retorna erro explícito do governor, pare de repetir o mesmo `put_page`.
3. Se já existe uma página de incidente/projeto, preserve imediatamente os fatos em `add_timeline_entry` com blocos temáticos menores.
4. Releia com `get_timeline` e confirme IDs, source, summary e detail.
5. Para criar uma página mestre separada, use o CLI oficial no host autoritativo:

```bash
/home/ubuntu/.local/bin/gbrain capture \
  --file /tmp/page.md \
  --slug systems/example \
  --type system-profile \
  --json
```

6. O arquivo precisa existir no host autoritativo. Envie por `scp` usando o alias SSH configurado, execute capture e remova o staging temporário.
7. Nunca aceite somente stdout como prova final. Releia a página com `get_page`.
8. Crie links explícitos com `add_link` e valide com `traverse_graph`.

## Semântica importante do capture

Um retorno como:

```json
{
  "status": "created_or_updated",
  "written": false,
  "source_kind": "capture-cli"
}
```

pode indicar que a página foi aceita no backend SQL, mas não houve mirror em arquivo local. `written:false` não significa necessariamente falha. `get_page` é a verificação autoritativa.

## Forma recomendada do conteúdo

Quando um documento monolítico é grande:

- crie uma página mestre compacta com estado e links;
- preserve dados extensos em timeline entries ou páginas de referência menores;
- use uma entrada por classe de evidência: inventário, decisões, telemetria, pesquisa, plano;
- não duplique writes cegamente durante timeout;
- mantenha provenance/source diferente por bloco.

## Verificação mínima

- `get_page` retorna slug, type, title e compiled_truth esperados;
- `get_timeline` retorna todos os blocos adicionados;
- `traverse_graph` mostra links na direção esperada;
- a fonte/ingestão (`capture-cli`, manual, etc.) está correta;
- dados privados permanecem em páginas/tags privadas.
