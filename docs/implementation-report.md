# Relatório de implementação — HUB SCHOOL

## 1. Branch e recuperação

Todo o trabalho ocorreu na branch local `develop`, no repositório desta pasta.
HEAD e main permaneceram no commit `00e497b56aec940fe245bfa3d11f9325cbd70952`.
O stash original permaneceu em `6312f09f211e09526aa9ad0b22241b40681193ac`.

Antes da recuperação foram inspecionados status, histórico, árvore da feature e
árvores do stash. Os destinos foram conferidos para garantir que não existiam
arquivos a sobrescrever. Foram usados `git restore --source=... --worktree` com
listas explícitas: arquivos-base do stash principal e novos arquivos do terceiro
pai. Não houve aplicação integral de stash, pop, troca de branch, merge, commit,
push, reset ou clean. A documentação Word foi recuperada como binário original.

Não foram modificados banco, RLS, Storage real, infraestrutura, front-end ou
configuração local de ambiente. Nenhuma dependência foi instalada.

## 2. Arquivos recuperados

- [app/main.py](../app/main.py)
- [app/__init__.py](../app/__init__.py)
- [app/core/config.py](../app/core/config.py)
- [app/core/security.py](../app/core/security.py)
- [app/core/__init__.py](../app/core/__init__.py)
- [app/dependencies/auth.py](../app/dependencies/auth.py)
- [app/dependencies/__init__.py](../app/dependencies/__init__.py)
- [app/routers/auth.py](../app/routers/auth.py)
- [app/routers/health.py](../app/routers/health.py)
- [app/routers/__init__.py](../app/routers/__init__.py)
- [requirements.txt](../requirements.txt)
- [.env.example](../.env.example)
- [tests/test_auth.py](../tests/test_auth.py)
- [hub-school-documentacao.docx](hub-school-documentacao.docx)

## 3. Arquivos novos

### Aplicação

- [core/errors.py](../app/core/errors.py)
- [dependencies/academic.py](../app/dependencies/academic.py)
- [repositories/base.py](../app/repositories/base.py) e [inicializador](../app/repositories/__init__.py)
- [schemas/academic.py](../app/schemas/academic.py), [planning.py](../app/schemas/planning.py) e [inicializador](../app/schemas/__init__.py)
- [services/academic.py](../app/services/academic.py), [planning.py](../app/services/planning.py), [attachments.py](../app/services/attachments.py) e [inicializador](../app/services/__init__.py)
- [routers/academic.py](../app/routers/academic.py) e [planning.py](../app/routers/planning.py)
- [integrations/contracts.py](../app/integrations/contracts.py) e [inicializador](../app/integrations/__init__.py)

### Testes e documentação

- [tests/__init__.py](../tests/__init__.py), [conftest.py](../tests/conftest.py), [fakes.py](../tests/fakes.py)
- [test_foundation.py](../tests/test_foundation.py), [test_domains.py](../tests/test_domains.py)
- [test_planning.py](../tests/test_planning.py), [test_jwks_cache.py](../tests/test_jwks_cache.py)
- [test_edges.py](../tests/test_edges.py), [test_integrations.py](../tests/test_integrations.py), [test_boundaries.py](../tests/test_boundaries.py)
- [requirements-lock.txt](../requirements-lock.txt)
- [api.md](api.md), [architecture.md](architecture.md), [integration-checklist.md](integration-checklist.md)
- Este relatório e [snapshot OpenAPI](openapi.json).

## 4. Arquivos modificados após recuperação

[README.md](../README.md), [app/main.py](../app/main.py),
[app/core/config.py](../app/core/config.py), [app/core/security.py](../app/core/security.py),
[requirements.txt](../requirements.txt), [.env.example](../.env.example) e
[tests/test_auth.py](../tests/test_auth.py).

No Git, arquivos recuperados continuam como não rastreados porque não existem no
commit atual de develop. Isso é esperado: nenhum commit nem stage foi realizado.

## 5. Arquitetura final e endpoints

Routers → schemas → serviços → interfaces de repositórios/gateways, com
autenticação e autorização reutilizáveis. Ver [decisões de arquitetura](architecture.md).
O [inventário completo de endpoints](api.md#inventário-completo-de-endpoints)
inclui todos os métodos e caminhos; OpenAPI também está disponível em runtime.

## 6. Classificação dos requisitos

As classificações se referem ao escopo indicado. Um módulo testado com fake
permanece **não integrado** em sua operação persistente real.

| Requisito/funcionalidade | Classificação | Evidência e limite |
|---|---|---|
| Base: health, docs, auth/me | IMPLEMENTADO E TESTADO | Recuperação validada antes de novos módulos |
| RF01: validação de JWT | IMPLEMENTADO E TESTADO | ES256, claims, kid, cache, rotação e falhas; login/cadastro/recuperação seguem no Auth externo |
| RF01: fluxo real de conta completo | BLOQUEADO | Supabase e integração Next.js não revalidados |
| Autorização e RN04 na API | IMPLEMENTADO E TESTADO | Dois usuários, leitura/escrita, IDs, listas e vínculos; não certifica RLS |
| RF02: semestres | IMPLEMENTADO, NÃO INTEGRADO | Schemas, rotas, serviço e regra de ativo; atomicidade real depende do adaptador/banco |
| RF03: disciplinas e horários | IMPLEMENTADO, NÃO INTEGRADO | Cadastro/consulta/edição; conversão de carga horária não inventada |
| RF04: frequência | IMPLEMENTADO, NÃO INTEGRADO | Registro/correção e unicidade por data no contrato transacional |
| RF05–RF06: cálculos de frequência | IMPLEMENTADO E TESTADO | RN01, piso, percentuais, zero aulas, limites 50/80%; dados reais dependem de persistência |
| RF07: eventos | IMPLEMENTADO, NÃO INTEGRADO | CRUD sem exclusão de regra indefinida, tipos e datas com offset |
| RF08: consulta semanal/mensal | IMPLEMENTADO, NÃO INTEGRADO | Filtro por intervalo; apresentação e cores no front |
| RF09: recorrência | IMPLEMENTADO, NÃO INTEGRADO | Projeção de horários testada; sem persistir eventos, cancelamento por feriado pendente |
| RF10: calendário | IMPLEMENTADO, NÃO INTEGRADO | Consulta global; carga oficial pela equipe não realizada |
| RF11: anotações | IMPLEMENTADO, NÃO INTEGRADO | Criação/edição/exclusão, bloqueio de exclusão com anexos |
| RF12: anexos | CONTRATO PREPARADO | Upload/listagem e validação local testados com gateway fictício; Storage/download pendentes |
| RF13–RF14: vínculos e busca | IMPLEMENTADO, NÃO INTEGRADO | Propriedade de disciplina/evento, texto e filtros testados |
| RF15–RF16: docentes | IMPLEMENTADO, NÃO INTEGRADO | Contatos particulares, vínculo e exclusão protegida |
| RF17: avaliações/médias | IMPLEMENTADO, NÃO INTEGRADO | Média ponderada parcial testada, notas pendentes explícitas |
| Primeiro acesso | IMPLEMENTADO, NÃO INTEGRADO | Retomada dos quatro recursos; sem estados de conclusão inventados |
| RF18: situação | CONTRATO PREPARADO | Critérios RN03 calculados/testados; decisão final ambígua retorna nulo |
| RF19: calculadora | IMPLEMENTADO E TESTADO | Simulação autenticada, uma avaliação restante e escala explícita |
| RF20: grupos/chat | CONTRATO PREPARADO | Schemas/interface apenas; autorização por membro e realtime não implementados |
| RF21: off-line/sincronização | BLOQUEADO | Cache no front; conflitos/versionamento não definidos |
| RF22: lembretes | CONTRATO PREPARADO | Prévia de datas testada; scheduler/envio não implementados |
| RF23: alerta de faltas | CONTRATO PREPARADO | Níveis calculados/testados; entrega/deduplicação não implementadas |
| RF24: canal | CONTRATO PREPARADO | E-mail aceito na prévia; preferências persistidas e push bloqueados |
| RNF04: exportação/exclusão | CONTRATO PREPARADO | Schemas/interfaces/rotas; retornam 503, nenhuma operação real |
| RNF05: Swagger | IMPLEMENTADO E TESTADO | Schemas, respostas, segurança e operation IDs conferidos |
| RNF02: RLS real | BLOQUEADO | Requer esquema, políticas e validação com Caio |
| RNF03: desempenho integrado | BLOQUEADO | Sem banco/front/infra para medir telas em 4G |
| RNF01/RNF06: responsividade/acessibilidade | NÃO IMPLEMENTADO | Trabalho do front, fora do escopo desta API |

Não foram implementadas funcionalidades em avaliação: fórum, avisos globais e widget.
Também não foram inventados perfil editável, política de sincronização, cascatas
ou caminhos administrativos para exclusão de conta.

## 7. Regras implementadas e segurança

- Um semestre ativo; histórico não é apagado.
- Propriedade vem do JWT, campos extras de propriedade são rejeitados.
- Validação de todos os vínculos privados antes de gravar.
- 404 uniforme para recurso alheio ou inexistente.
- Frequência em aulas, faltas <= aulas registradas e duplicidade por data rejeitada.
- RN01, média ponderada parcial e simulação de nota mínima.
- RN03 avaliada sem precedência inventada.
- Recorrência limitada ao semestre; intervalos consultados limitados.
- Prévia de lembretes com padrões 3/1 dias, sem envio implícito.
- Tamanho, nome, extensão e assinatura inicial de anexos.
- Erros HTTP e logs sem valores da exceção/payload; CORS configurável.
- Repositórios fictícios restritos a testes; 503 nas integrações ausentes.

## 8. Validação executada

1. Fundação recuperada: **7 testes originais aprovados**.
2. Fundação + smoke de health/docs/auth/OpenAPI: **8 aprovados**.
3. Suíte final: **68 testes aprovados**, sem rede externa.
4. `pip check`: nenhuma dependência quebrada.
5. `compileall -q app tests`: sucesso.
6. Diagnósticos do editor: nenhum erro reportado nos caminhos consultados.
7. `git diff --check`: sucesso; esta checagem do Git cobre alterações rastreadas.
8. Branch, HEAD, main e stash conferidos ao término.

Aviso conhecido: Starlette deprecia HTTPX no TestClient em favor de HTTPX2. Nenhuma
instalação foi feita para suprimir o aviso. Não foi executado type checker adicional,
medição de cobertura, teste de carga, teste de RLS, deploy, envio de e-mail ou acesso
real ao Supabase. Não afirmar que testes locais substituem essas validações.

## 9. Pendências e próximos passos

Ver [checklist por responsável](integration-checklist.md):

1. Caio fornece esquema aprovado, constraints, identidade/RLS e política de Storage.
2. Davi resolve regras ambíguas de notas, frequência, feriados e anexos.
3. Implementar adaptadores usando JWT do usuário, sem conexão privilegiada que
   contorne RLS; garantir atomicidade e eficiência das consultas.
4. Executar testes reais A/B com Caio em ambiente autorizado.
5. Bruno integra os [contratos](api.md), wizard, agenda, dashboard e estados 503.
6. Definir scheduler/provedor de e-mail, política de anexos e fluxo integral de conta.
7. Kayron escolhe runtime, TLS, limites, observabilidade e ambiente de teste.
8. Validar instalação limpa, desempenho, segurança integrada e demonstração ao P.O.

Comandos locais e variáveis estão no [README](../README.md). Não há necessidade
de instalar pacotes para repetir os testes no ambiente existente validado.

**Conclusão de escopo:** camada independente desenvolvida e validada no alcance
documentado; contratos e bloqueios externos explicitados. API não está pronta
para produção sem persistência, RLS e validação de integração.
