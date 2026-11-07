# Arquitetura e decisões

## Fluxo

Next.js → JWT ES256 → dependência de autenticação → router/schema → serviço →
interface de repositório/gateway. Persistência e integrações reais permanecem
indisponíveis. Repositório fictício existe exclusivamente em `tests/fakes.py`.

- `core`: ambiente, JWT, cache JWKS, tratamento seguro de erros.
- `dependencies`: identidade validada e montagem dos serviços.
- `schemas`: payloads, respostas e contratos futuros.
- `services`: autorização, vínculos, cálculos e regras.
- `repositories`: contrato transacional de persistência privada.
- `integrations`: interfaces de conta, Storage, notificações e chat.
- `routers`: transporte HTTP, respostas tipadas, Swagger.

O registro compartilhado de rotas elimina repetição do CRUD e usa schemas
concretos no OpenAPI. Não há ORM, migrations, filas, Redis ou dependências novas.

## Segurança

JWT exige ES256, kid, assinatura, exp, iss, aud=authenticated e sub não vazio.
O cliente JWKS é reutilizado, com TTL de 300s e timeout de 5s por padrão. PyJWT
2.15.1 possui cooldown de atualização para kid desconhecido; uma chave recém
rotacionada pode ser rejeitada até esse intervalo terminar. Testes cobrem esse
comportamento, expiração do cache e rotação, sem acesso à rede externa.

Identidade nunca vem do payload. Repositórios recebem o usuário autenticado e
devem filtrar todas as operações. O serviço confere a propriedade de respostas e
de cada referência antes de escrever. Recursos alheios produzem 404. O contrato
normaliza `usuario_id` em registros privados, inclusive tabelas de propriedade
indireta; isso não significa adicionar colunas ao banco.

`transaction(user_id)` deve garantir rollback e serialização de conflitos por
proprietário. Regras de semestre ativo e frequência única não podem depender só
de uma consulta antes de gravar: o adaptador e as restrições do banco devem tornar
a operação atômica. O teste concorrente prova apenas o contrato do fake.

Erros internos não expõem traceback no HTTP nem são registrados com seus valores.
Isso reduz diagnóstico operacional: observabilidade futura deve usar categorias
e identificadores de requisição sem dados privados. CORS usa lista explícita.

## Persistência

Nenhum ORM foi escolhido. Primeiro avaliar PostgREST/Supabase com o JWT do próprio
usuário, mantendo RLS. PostgreSQL direto só após definição de papéis, propagação de
identidade e transações por Caio. Nunca presumir que conexão privilegiada respeita
o usuário final. O adaptador deverá receber o token validado por dependência
request-scoped; a interface acadêmica recebe apenas a identidade necessária às regras.

As migrations serão versionadas quando aprovadas e executadas por Caio. Não há SQL
ou migrations nesta entrega. A interface atual retorna coleções privadas ao serviço;
antes de produção, o adaptador deve evoluir filtros/paginação/agregações para o
banco e validar desempenho com volumes reais. RNF03 não foi demonstrado.

## Decisões limitadas ao contrato local

- IDs opacos até confirmação dos tipos físicos.
- Horários semanais locais; instantes de evento exigem timezone.
- Docente opcional durante o assistente, a confirmar no esquema.
- Limites de texto/paginação protegem a API; não são regras acadêmicas oficiais.
- Média parcial exclui notas ainda não lançadas e explicita a quantidade pendente.
- Percentuais sem aulas retornam nulo, não inventam presença de 100%.
- Feriados não cancelam aulas automaticamente; recorrência é uma projeção.
- RN03 ambígua retorna critérios em vez de prioridade inventada.
- Não há precedência de situação, arredondamento institucional, conversão hora/aula
  ou estados de conclusão inventados.
- Semestre ativo adicional produz 409; o cliente desativa o anterior antes de ativar
  outro. Não foi inventada ativação automática nem apagamento de histórico.
- Exclusão de contato com disciplinas ou anotação com anexos produz 409.

## Entrega 2 e integrações

RF19 tem cálculo local operacional. RF18 avalia critérios documentados, mas a
classificação definitiva permanece pendente. Grupos/mensagens possuem schemas e
interface, sem rotas que finjam autorização por associação. Papéis, convite,
moderação, revogação e transporte realtime precisam de definição.

RF21 não tem protocolo inventado: cache é do front e conflitos, versionamento,
tombstones e reenvio precisam de contrato conjunto. Exportação/exclusão integral,
preferências de notificação, perfil editável e Storage aguardam integração ou
definição. Não foram adicionados campos de banco para representar esses estados.
