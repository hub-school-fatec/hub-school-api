# Contratos HTTP — HUB SCHOOL

## Estado e convenções

Implementação local na branch `develop`, sem integração de persistência. A origem
dos requisitos é o [documento do projeto](hub-school-documentacao.docx).
O OpenAPI executável está em `/openapi.json`, Swagger em `/docs` e ReDoc em `/redoc`.

Todas as operações abaixo exigem `Authorization: Bearer <access_token>`, exceto
`GET /health`. Login, cadastro e recuperação de senha continuam no Supabase Auth,
usado pelo Next.js. A API nunca recebe senha nem aceita `usuario_id` nos payloads
acadêmicos. Identificadores são strings opacas; o tipo físico aguarda Caio.

As rotas dependentes de repositório retornam **503** até integração. Nenhum
repositório em memória é usado pela aplicação. Os exemplos podem ser exercitados
pelos testes com substituição explícita das dependências.

## Inventário completo de endpoints

| Caminho | Métodos | Uso |
|---|---|---|
| `/health` | GET | Processo disponível, não comprova banco/RLS |
| `/auth/me` | GET | Identidade validada (`user_id`) |
| `/semestres` | GET, POST | Listar/criar semestre |
| `/semestres/{record_id}` | GET, PUT | Consultar/substituir semestre |
| `/docentes` | GET, POST | Contatos privados |
| `/docentes/{record_id}` | GET, PUT, DELETE | Consultar/editar/excluir contato sem vínculos |
| `/disciplinas` | GET, POST | Listar/criar disciplina |
| `/disciplinas/{record_id}` | GET, PUT | Consultar/substituir disciplina |
| `/horarios` | GET, POST | Horários semanais |
| `/horarios/{record_id}` | GET, PUT | Consultar/substituir horário |
| `/frequencias` | GET, POST | Frequência agregada por disciplina/data |
| `/frequencias/{record_id}` | GET, PUT | Consultar/corrigir frequência |
| `/avaliacoes` | GET, POST | Avaliações, pesos e notas |
| `/avaliacoes/{record_id}` | GET, PUT | Consultar/substituir avaliação |
| `/eventos` | GET, POST | Agenda do estudante |
| `/eventos/{record_id}` | GET, PUT | Consultar/substituir evento |
| `/anotacoes` | GET, POST | Texto, busca e vínculos |
| `/anotacoes/{record_id}` | GET, PUT, DELETE | Consultar/editar/excluir anotação sem dependências |
| `/disciplinas/{record_id}/resumo-frequencia` | GET | RN01 e alertas |
| `/disciplinas/{record_id}/media` | GET | Média parcial ponderada |
| `/primeiro-acesso` | GET | Dados salvos do assistente |
| `/calendario-academico` | GET | Calendário global, somente leitura |
| `/aulas-recorrentes` | GET | Projeção dos horários dentro do semestre |
| `/calculos/aprovacao` | POST | RF19, simulação sem persistência |
| `/calculos/situacao` | POST | Critérios RN03, sem precedência inventada |
| `/eventos/{event_id}/previa-lembretes` | POST | Datas de lembrete, não agenda/envia |
| `/anotacoes/{note_id}/anexos` | GET, POST | Contrato de listagem/upload privado |
| `/conta/exportacao` | GET | Exportação integral, integração bloqueada |
| `/conta` | DELETE | Exclusão integral, integração bloqueada |

Documentação adicional servida pelo framework: GET `/docs`, `/docs/oauth2-redirect`,
`/redoc` e `/openapi.json`. Não são endpoints de dados privados.

## Payloads para Bruno

POST recebe os campos abaixo; PUT substitui o recurso inteiro, com os mesmos
campos. `id` é devolvido na resposta e não deve ser enviado na escrita. Campos
desconhecidos, inclusive propriedade, são rejeitados com 422.

| Recurso | Campos |
|---|---|
| semestre | `nome`, `data_inicio`, `data_fim`, `ativo` |
| docente | `nome`, `email`, `telefone?`, `observacoes` (padrão vazio) |
| disciplina | `semestre_id`, `docente_id?`, `nome`, `sigla`, `total_aulas` |
| horário | `disciplina_id`, `dia_semana`, `hora_inicio`, `hora_fim`, `sala` |
| frequência | `disciplina_id`, `data`, `aulas_no_dia`, `faltas` |
| avaliação | `disciplina_id`, `nome`, `peso`, `nota?` |
| evento | `disciplina_id?`, `tipo`, `titulo`, `inicio`, `fim` |
| anotação | `disciplina_id?`, `evento_id?`, `titulo`, `corpo` |

`?` significa opcional/nulo. Datas: `YYYY-MM-DD`. Instantes de eventos exigem
offset ou `Z`. Horários semanais são locais, sem offset, com segunda=0 até domingo=6;
esses são contratos de transporte, a mapear para o esquema físico confirmado.
Intervalos de horário atravessando meia-noite ainda não são representados.
Decimais em respostas podem ser strings JSON; o front deve convertê-los para
exibição, sem assumir arredondamento institucional.

Listagens acadêmicas: `offset` >= 0, `limit` entre 1 e 100 (padrão 50), ordenadas
por `id`. Filtros `disciplina_id`, `semestre_id`, `evento_id` somente quando o campo
existe no recurso. `texto` busca em nome/título/corpo sem diferenciar maiúsculas.
Eventos aceitam filtro `tipo`, `inicio` e `fim` e retornam interseção de intervalos: fim do evento
> início consultado e início do evento < fim consultado. Agenda semanal/mensal é
a mesma consulta com intervalos escolhidos pelo front; cores são responsabilidade da UI.

Calendário: `inicio`/`fim` em datas, inclusivos. Aulas recorrentes: ambas as datas
obrigatórias, intervalo de até 366 dias. A projeção é limitada às datas do semestre,
não grava eventos e não desconta feriados automaticamente.

### Primeiro acesso

`GET /primeiro-acesso` retorna `semestres`, `disciplinas`, `horarios`, `docentes`.
O front usa os POSTs/PUTs dos recursos para salvar e retoma esses dados quando
necessário. Não há campo `concluido`, etapas extras ou transação de wizard inventada.
Docente pode ser associado posteriormente à disciplina; isso permite a ordem
documentada do assistente. Confirmar a nulabilidade física com Caio.

### Cálculos

`POST /calculos/aprovacao`:

```json
{"avaliacoes_lancadas":[{"nota":8,"peso":1}],"peso_proxima":1,"nota_maxima":10}
```

Com meta configurada em 6, retorna nota mínima 4, `impossivel: false`, média máxima
9 e meta 6. É simulação com **uma avaliação restante**; escala máxima é explícita.
Não consulta ou altera notas reais. Nota mínima é limitada inferiormente a zero.

`POST /calculos/situacao` recebe `presenca_percentual`, `faltas`, `limite_faltas` e,
opcionalmente, `media`, `media_maxima_possivel`, `nota_minima_proxima`. Retorna todos
os `criterios_acionados`; `situacao` é nula se nenhum ou mais de um critério se
aplicar. `requer_definicao` sinaliza essa limitação. Não é certificado acadêmico.

Média da disciplina inclui apenas avaliações com nota lançada, informa contagens
lançadas/pendentes e retorna nulo sem notas. Presença/faltas percentuais são nulos
sem aulas dadas. Faltas restantes nunca são negativas. Limite usa piso matemático.

### Notificações e anexos

Prévia: `{"antecedencia_dias":[3,1],"canal":"email"}`. Aceita apenas prova,
trabalho e apresentação; remove antecedências duplicadas. Retorna datas inclusive
passadas, pois é uma prévia, não uma promessa de envio. Push, preferências
persistidas, scheduler, deduplicação e provedor não estão integrados.

Upload: POST com corpo `application/octet-stream` e query `nome_arquivo`.
Limite decimal provisório de 10 MB, configurável; formatos aceitos: PDF, PNG, JPEG,
GIF, WebP. Extensão e assinatura são conferidas; isso **não substitui** inspeção
antimalware ou decodificação completa. SVG e outros formatos não estão habilitados.
O cliente não fornece caminho de Storage. Sem gateway, retorna 503. Download,
exclusão de anexos e URLs assinadas aguardam política de Storage.

### Conta

Exportação tem envelope `usuario_id`, `gerado_em`, `dados`; o conjunto completo
exige banco, Auth e Storage. DELETE `/conta` usa corpo
`{"confirmar_exclusao":true}`. Ambos retornam 503 até existir fluxo aprovado.
Nenhuma exclusão parcial é apresentada como sucesso.

## Erros

- 401: autenticação ausente/inválida, com `WWW-Authenticate: Bearer`.
- 404: recurso inexistente ou pertencente a outro usuário, sem revelar qual caso.
- 409: semestre ativo duplicado, frequência duplicada ou exclusão com vínculos.
- 413/415: tamanho/formato de anexo.
- 422: validação; erros incluem localização e tipo, sem ecoar dados enviados.
- 503: persistência/integração não disponível.
- 500: mensagem genérica; logs não incluem exceção nem payload.

Criação retorna 201; consulta/PUT retorna 200; exclusão concluída retorna 204.
Não há DELETE de semestres, disciplinas, horários, frequência, avaliações ou
eventos enquanto suas regras de histórico/cascata não forem definidas.
