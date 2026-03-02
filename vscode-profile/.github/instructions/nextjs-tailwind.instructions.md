---
description: 'Next.js + Tailwind development standards and instructions'
applyTo: '**/*.tsx, **/*.ts, **/*.jsx, **/*.js, **/*.css'
---


# Instruções de Desenvolvimento Next.js + Tailwind

Instruções para aplicações Next.js de alta qualidade com estilização Tailwind CSS e TypeScript.

## Contexto do Projeto

- Última versão do Next.js (App Router)
- TypeScript para segurança de tipos
- Tailwind CSS para estilização

## Padrões de Desenvolvimento

### Arquitetura
- App Router com componentes server e client
- Agrupe rotas por funcionalidade/domínio
- Implemente error boundaries adequados
- Use React Server Components por padrão
- Aproveite otimização estática sempre que possível

### TypeScript
- Strict mode ativado
- Definições de tipos claras
- Tratamento de erros com type guards
- Zod para validação de tipos em tempo de execução

### Estilização
- Tailwind CSS com paleta de cores consistente
- Padrões de design responsivo
- Suporte a dark mode
- Siga boas práticas de container queries
- Mantenha estrutura HTML semântica

### Gerenciamento de Estado
- React Server Components para estado do servidor
- React hooks para estado do cliente
- Estados de loading e erro adequados
- Atualizações otimistas quando apropriado

### Busca de Dados
- Server Components para queries diretas ao banco
- React Suspense para loading states
- Tratamento de erros e lógica de retry
- Estratégias de invalidação de cache

### Segurança
- Validação e sanitização de entradas
- Checagens de autenticação adequadas
- Proteção CSRF
- Implementação de rate limiting
- Rotas de API seguras

### Performance
- Otimização de imagens com next/image
- Otimização de fontes com next/font
- Prefetch de rotas
- Code splitting adequado
- Otimização do tamanho do bundle

## Processo de Implementação
1. Planeje a hierarquia de componentes
2. Defina tipos e interfaces
3. Implemente lógica server-side
4. Construa componentes client
5. Adicione tratamento de erros
6. Implemente estilização responsiva
7. Adicione estados de loading
8. Escreva testes
