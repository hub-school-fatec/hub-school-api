# HUB SCHOOL API

API Python/FastAPI para o controle pessoal do estudante. Autenticação Supabase
JWT ES256, contratos OpenAPI e regras acadêmicas testadas sem serviços externos.

**Estado:** domínio implementado e validado com repositórios fictícios exclusivos
dos testes. Persistência PostgreSQL/Supabase, RLS, Storage, envio de notificações
e operações reais de conta **não estão integrados**. Rotas dependentes retornam 503.
Não é uma entrega pronta para produção.

## Execução local

Ambiente validado: Python 3.14.3 no Windows. A partir desta pasta:

```powershell
# Somente se precisar criar um ambiente novo; não sobrescrever ambiente existente.
py -3.14 -m venv .venv

# Instalação manual após autorização do responsável pelo ambiente:
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt

# Configurar as variáveis do exemplo sem sobrescrever um .env existente.
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Dependências diretas em [requirements.txt](requirements.txt), snapshot fixado do
ambiente validado em [requirements-lock.txt](requirements-lock.txt). Nenhum pacote
foi instalado nesta implementação. O lock ainda precisa ser validado por instalação
limpa na plataforma de deploy. Não há suporte a outras versões Python certificado.

Acesse `http://127.0.0.1:8000/docs`, `/openapi.json`, `/redoc` e `/health`.
`/health` informa liveness, não disponibilidade de banco.

## Ambiente e autenticação

Veja [.env.example](.env.example). Configurar:

| Variável | Finalidade |
|---|---|
| `SUPABASE_URL` | URL HTTPS do projeto para JWKS |
| `SUPABASE_JWT_ISSUER` | Emissor exato, normalmente URL do projeto + `/auth/v1` |
| `SUPABASE_ANON_KEY` | Reservada para integração; não usada para validar JWT |
| `CORS_ORIGINS` | Lista JSON de origens do front; padrão vazio |
| `MINIMUM_ATTENDANCE` | Percentual mínimo, padrão 75, sujeito a confirmação |
| `MINIMUM_GRADE` | Média-alvo, padrão 6, sujeita a confirmação |
| `JWKS_CACHE_SECONDS` | TTL de chaves públicas, padrão 300 |
| `JWKS_TIMEOUT_SECONDS` | Timeout de obtenção JWKS, padrão 5 |
| `ATTACHMENT_MAX_BYTES` | Limite provisório, padrão 10000000 bytes |

O front faz cadastro/login/recuperação no Supabase Auth e envia o access token
como Bearer. `/auth/me` valida assinatura ES256, kid, exp, iss, aud e sub. Sem
configuração de Auth válida, rotas privadas retornam 401. Não usar service_role.
Não colocar tokens em query strings, arquivos versionados ou logs.

## Estrutura

```text
app/
  core/           configuração, segurança e erros
  dependencies/   identidade e montagem de serviços
  routers/        rotas HTTP e OpenAPI
  schemas/        entrada/saída e contratos de integração
  services/       regras, autorização e cálculos
  repositories/   interface transacional (sem adaptador real)
  integrations/   interfaces externas (sem gateways reais)
tests/            testes offline e repositório fictício
docs/             especificação original, contratos e pendências
```

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q app tests
```

Rede externa bloqueada nos testes; loopback permitido para o event loop do Windows.
Testes cobrem JWT, cache/rotação, dois estudantes, BOLA/IDOR, referências cruzadas,
regras, erros, contratos HTTP e anexos com gateway fictício. Não substituem RLS real.
Há aviso de depreciação Starlette/TestClient com HTTPX; migração para HTTPX2 não foi
feita pois exigiria avaliação e autorização para instalar dependência.

## Endpoints e integração

Recursos: semestres, docentes, disciplinas, horários, frequência, avaliações,
eventos, anotações, calendário, primeiro acesso e recorrência. Também há simulações
de aprovação/situação e contratos de anexos, prévia de lembretes e conta.

- [Inventário completo e payloads para Next.js](docs/api.md)
- [Arquitetura, segurança e persistência](docs/architecture.md)
- [Pendências para Caio, Bruno, Davi e Kayron](docs/integration-checklist.md)
- [Relatório de implementação e classificação dos requisitos](docs/implementation-report.md)
- [Documentação funcional original](docs/hub-school-documentacao.docx)

## Branches e deploy

`develop`: desenvolvimento/integração. `main`: estável, mediante testes e aprovação.
`feature/*`: opcional. Esta implementação não criou commits, pushes ou deploy.
Para teste hospedado, escolher primeiro runtime Python, configurar ambiente/CORS,
TLS e integrações. O comando Uvicorn acima é local; não expõe a API publicamente.
