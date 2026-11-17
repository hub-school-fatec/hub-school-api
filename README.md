# HUB SCHOOL API

API acadêmica em Python/FastAPI. A autenticação usa access tokens do Supabase Auth; os dados são acessados via PostgREST e os anexos ficam no bucket privado `hub-school-anexos` do Supabase Storage. As operações usam o JWT original do usuário para que as políticas RLS do projeto sejam aplicadas. A API não usa `service_role`.

## Tecnologias e estrutura

- FastAPI e Uvicorn para HTTP e documentação OpenAPI.
- Pydantic Settings para configuração; PyJWT com suporte criptográfico para JWT ES256/JWKS.
- HTTPX para PostgREST e Storage; `python-multipart` para uploads; pytest para testes.
- `app/core/`: configuração e validação JWT.
- `app/dependencies/`: identidade autenticada com `user_id` e token original.
- `app/routers/`: rotas HTTP; `app/schemas/`: contratos Pydantic.
- `app/repositories/`: cliente PostgREST e operações por entidade; `app/services/anexos.py`: fluxo de arquivos.
- `tests/`: testes offline com respostas simuladas; `scripts/`: testes manuais que podem acessar serviços reais e **não** fazem parte da execução local recomendada.

As versões das dependências diretas estão fixadas em `requirements.txt`. Este repositório não cria tabelas nem executa migrations: exige um projeto Supabase com tabelas, RLS, permissões e bucket compatíveis já configurados.

## Instalação no Windows (PowerShell)

Requisitos: Python 3.11 ou superior, acesso ao projeto Supabase para usar rotas protegidas e um terminal na raiz `hub-school-api`. A aplicação e `/health` podem iniciar sem credenciais; as rotas protegidas precisam da configuração abaixo.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Se preferir não ativar o ambiente, substitua `python` nos comandos pelo caminho `.\.venv\Scripts\python.exe`.

## Configuração local

Use `.env.example` como referência e crie seu próprio `.env` local. O arquivo `.env` está no `.gitignore`; não o envie ao Git nem coloque tokens de usuário, senhas ou chaves administrativas na documentação.

| Variável | Uso |
| --- | --- |
| `SUPABASE_URL` | URL HTTPS base do projeto Supabase, sem caminho extra. |
| `SUPABASE_JWT_ISSUER` | Emissor exato: `<SUPABASE_URL>/auth/v1`. |
| `SUPABASE_PUBLISHABLE_KEY` **ou** `SUPABASE_ANON_KEY` | Chave pública do mesmo projeto para o cabeçalho `apikey`. |
| `CORS_ALLOWED_ORIGINS` | Lista JSON de origens explícitas do frontend, sem barra final. O padrão local já inclui `http://localhost:3000` e `http://127.0.0.1:3000`. |

Não use `service_role` ou chave secreta. `MINIMUM_ATTENDANCE`, `MINIMUM_GRADE`, `JWKS_CACHE_SECONDS`, `JWKS_TIMEOUT_SECONDS` e `ATTACHMENT_MAX_BYTES` aparecem em `.env.example`, mas **não são variáveis lidas pela configuração atual**; os limites correspondentes estão definidos no código. Alterá-las no `.env` não muda o comportamento da API.

## Execução e autenticação

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- `GET http://127.0.0.1:8000/health` é público e retorna `{"status":"ok"}`.
- `http://127.0.0.1:8000/docs` oferece o Swagger; `http://127.0.0.1:8000/openapi.json` fornece o contrato OpenAPI.
- `GET /auth/me` recebe `Authorization: Bearer <access_token>` e retorna o identificador do usuário. Não consulta a tabela `usuario`.

A API valida assinatura ES256 usando o JWKS público do projeto, `kid`, emissor, audiência `authenticated`, expiração e `sub`, com tolerância de relógio de 5 segundos. O JWKS é consultado e mantido em cache por tempo limitado. Para usar os CRUDs, o usuário autenticado também precisa das permissões e do registro correspondente exigidos pelo esquema e pelas policies do Supabase. Não há endpoint de criação de perfil `usuario` nesta API.

## Rotas principais

| Recurso | Operações |
| --- | --- |
| `/semestres`, `/docentes`, `/disciplinas` | GET lista, GET por UUID, POST, PATCH por UUID e DELETE por UUID. |
| `/horarios-aula`, `/avaliacoes`, `/frequencias` | GET lista, GET por UUID, POST, PATCH por UUID e DELETE por UUID. |
| `/eventos`, `/anotacoes` | GET lista, GET por UUID, POST, PATCH por UUID e DELETE por UUID. |
| `/calendario-academico` | GET lista, somente leitura. |
| `/anexos` | GET lista; POST `/anexos/upload` com multipart `anotacao_id` e `arquivo`; GET `/anexos/{id}`, GET `/anexos/{id}/download` e DELETE `/anexos/{id}`. |

As rotas acadêmicas exigem JWT. Consulte `/docs` para campos obrigatórios, filtros e schemas exatos. O upload aceita os formatos definidos no serviço de anexos e limita o arquivo a 10 MiB.

## Testes offline

Com a `.venv` ativa, execute na raiz do backend:

```powershell
python -m pytest tests -q -s -p no:cacheprovider
```

Os testes usam transportes simulados e não precisam acessar o Supabase real. O teste multipart de arquivo acima de 10 MiB exige um **diretório temporário gravável**: o parser grava o arquivo antes de chegar à validação da rota. Em ambiente sem permissão de escrita no diretório temporário, ele pode responder HTTP 400 e esse teste falhar; em ambiente gravável, a rota responde HTTP 422 como esperado. A última suíte offline executada em ambiente gravável teve **387 testes aprovados**. Os scripts em `scripts/` são manuais e não devem ser executados como parte da suíte offline.

## Limitações conhecidas

- `DELETE /anotacoes/{id}` retorna **HTTP 409** se a consulta autenticada encontrar anexos. Exclua cada anexo pelo endpoint próprio antes de excluir a anotação.
- A consulta de anexos e a exclusão da anotação são operações separadas. Um upload concorrente entre elas ainda pode gerar objeto órfão no Storage. Esta proteção **não é garantia absoluta**; resolver a corrida exige coordenação adicional no lado do banco/Storage.
- A exclusão individual de anexo também envolve Storage e metadados em operações separadas; falhas parciais são sinalizadas, sem transação distribuída.
- A suíte automatizada é offline. A compatibilidade de cada módulo com o esquema e as policies reais precisa de validação manual autorizada; testes de integração anteriores não substituem essa validação para todos os módulos.
