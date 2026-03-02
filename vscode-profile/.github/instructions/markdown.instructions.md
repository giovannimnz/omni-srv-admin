---
description: 'Documentation and content creation standards'
applyTo: '**/*.md'
---


## Regras de Conteúdo Markdown

As seguintes regras de conteúdo markdown são aplicadas nos validadores:

1. **Títulos**: Use níveis de título apropriados (H2, H3, etc.) para estruturar seu conteúdo. Não utilize H1, pois ele será gerado automaticamente com base no título.
2. **Listas**: Use marcadores ou listas numeradas. Garanta indentação e espaçamento corretos.
3. **Blocos de Código**: Use blocos cercados por crases para trechos de código. Especifique a linguagem para realce de sintaxe.
4. **Links**: Use a sintaxe markdown correta para links. Certifique-se de que os links são válidos e acessíveis.
5. **Imagens**: Use a sintaxe markdown correta para imagens. Inclua texto alternativo para acessibilidade.
6. **Tabelas**: Use tabelas markdown para dados tabulares. Garanta formatação e alinhamento adequados.
7. **Comprimento de Linha**: Limite o comprimento das linhas a 400 caracteres para melhor leitura.
8. **Espaçamento em Branco**: Use espaçamento adequado para separar seções e melhorar a leitura.
9. **Front Matter**: Inclua o front matter YAML no início do arquivo com os campos de metadados obrigatórios.

## Formatação e Estrutura

Siga estas diretrizes para formatar e estruturar seu conteúdo markdown:

- **Títulos**: Use `##` para H2 e `###` para H3. Garanta o uso hierárquico dos títulos. Recomenda-se reestruturar se houver H4 e fortemente para H5.
- **Listas**: Use `-` para marcadores e `1.` para listas numeradas. Indente listas aninhadas com dois espaços.
- **Blocos de Código**: Use três crases (```) para criar blocos de código. Especifique a linguagem após as crases para realce de sintaxe (ex: `csharp`).
- **Links**: Use `[texto do link][URL]` para links. Certifique-se de que o texto seja descritivo e a URL válida.
- **Imagens**: Use `![texto alternativo](URL da imagem)` para imagens. Inclua uma breve descrição no texto alternativo.
- **Tabelas**: Use `|` para criar tabelas. Garanta alinhamento e cabeçalhos adequados.
- **Comprimento de Linha**: Quebre linhas a cada 80 caracteres para melhorar a leitura. Use quebras suaves para parágrafos longos.
- **Espaçamento em Branco**: Use linhas em branco para separar seções e melhorar a leitura. Evite excesso de espaços.

## Requisitos de Validação

Garanta conformidade com os seguintes requisitos de validação:

- **Front Matter**: Inclua os seguintes campos no front matter YAML:

  - `post_title`: Título do post.
  - `author1`: Autor principal do post.
  - `post_slug`: Slug da URL do post.
  - `microsoft_alias`: Alias Microsoft do autor.
  - `featured_image`: URL da imagem de destaque.
  - `categories`: As categorias do post. Devem estar listadas em ../categories.txt.
  - `tags`: As tags do post.
  - `ai_note`: Indique se IA foi utilizada na criação do post.
  - `summary`: Um breve resumo do post. Recomende um resumo com base no conteúdo quando possível.
  - `post_date`: Data de publicação do post.

- **Regras de Conteúdo**: O conteúdo deve seguir as regras de markdown acima.
- **Formatação**: O conteúdo deve estar formatado e estruturado conforme as diretrizes.
- **Validação**: Execute as ferramentas de validação para checar conformidade com as regras e diretrizes.
