# Pendências e validação integrada

## Caio — banco e RLS

1. Entregar esquema aprovado das 12 entidades MVP e 3 da Entrega 2: tipos, null,
   defaults, FKs, índices e cascatas. Confirmar docente opcional no wizard.
2. Resolver propriedade direta/indireta: o texto fala em usuario_id em toda tabela,
   mas a tabela de campos omite essa coluna em várias entidades.
3. Garantir um semestre ativo por usuário e unicidade de frequência por
   disciplina/data, com transação atômica e controle de concorrência.
4. Definir RLS de leitura/escrita e impedir mudança de dono, inclusive por FKs.
5. Definir acesso global somente leitura ao calendário e carga pela equipe.
6. Definir política de histórico e exclusão para cada recurso.
7. Configurar Storage privado, limites, tipos, inspeção de arquivos, download,
   expiração de URLs e remoção coordenada de objetos/metadados.
8. Definir persistência de antecedências, preferências, idempotência de envio e
   identidade autorizada do scheduler. Sem service_role para contornar RLS.
9. Definir exclusão integral de Auth, banco e Storage; retomada após falhas e
   exportação completa. API não usará credencial administrativa implicitamente.
10. Escolher adaptador seguro; validar propagação do JWT ao Supabase.

### Testes reais de RLS, somente em ambiente autorizado com Caio

Estes testes **não foram executados** e não devem ser habilitados contra produção.
Preparar dois usuários de teste autorizados A/B e seus recursos, sem credenciais
privilegiadas. Usar JWTs próprios diretamente na API de dados/Storage e pela API:

- A lê/altera A e B lê/altera B.
- A não lê/altera/exclui B, e reciprocamente, por lista, ID e filtros.
- Tentativas de trocar usuario_id e inserir FKs de outro usuário são rejeitadas.
- Conferir frequência, horário, avaliação e anexo pela cadeia de propriedade.
- Testar concorrência em semestre ativo e frequência duplicada.
- Calendário legível para ambos; escrita de estudante rejeitada.
- Anexo privado não acessível por caminho adivinhado ou URL expirada.
- Tokens ausentes/expirados não permitem acesso; usuário excluído segue o fluxo
  de revogação/sessão aprovado, considerando validade de JWT já emitido.
- Grupos futuros: não membro não lê, escreve nem assina canal; remoção revoga acesso.
- Limpar somente dados de teste explicitamente autorizados.

## Davi — regras pendentes

- Confirmar frequência de 75% e média 6 conforme regulamento.
- Converter carga horária para total de aulas; definir unidades e arredondamento.
- Confirmar escala de notas, tratamento definitivo de pendências e precedência RN03.
- Definir exceções de recorrência, feriados, reposição, fuso e horários noturnos.
- Confirmar limite de anexos (10 MB provisórios) e formatos de imagem.
- Definir se há marcador de conclusão do wizard; nenhum foi inventado.
- Definir regras do chat, perfil editável e protocolo de sincronização.

## Bruno — Next.js

Usar [contratos HTTP](api.md) e `/openapi.json`. Login/cadastro/recuperação via
Supabase Auth; enviar Bearer para API. Não enviar usuario_id nem id na escrita.
Tratar 401 como sessão inválida, 404 sem distinguir propriedade, 409 como conflito,
422 como erro de formulário e 503 como integração indisponível.

Salvar cada recurso do wizard e retomar `/primeiro-acesso`; não presumir marcador
de conclusão. Consumir percentuais nulos como dados insuficientes. Usar intervalo
na agenda, juntar calendário/recorrência e não marcar aulas como canceladas só por
ser feriado. A prévia de lembretes não comprova que um e-mail foi agendado.

## Kayron — infraestrutura

- Escolher hospedagem Python/ASGI; nenhuma infraestrutura foi criada.
- TLS, origens CORS explícitas, variáveis seguras, limites de corpo no proxy,
  timeout, observabilidade sem conteúdo privado e monitoramento.
- Provedor de e-mail, domínio, scheduler, retries/deduplicação e métricas de entrega.
- Definir escaneamento de anexos e processamento seguro dos arquivos.
- Instalar dependências fixadas em ambiente limpo e validar compatibilidade da
  plataforma. Validação local foi em Python 3.14.3 no Windows.
- `/health` é liveness; readiness de banco/Storage precisa de desenho após integração.
- Medir RNF03 (<2s nas telas em 4G) com front, dados e serviços reais.
- Corrigir depreciação do TestClient/HTTPX mediante aprovação de eventual nova
  dependência. Nenhum pacote foi instalado durante este trabalho.

Não há deploy, integração real, benchmark, varredura externa de vulnerabilidades
ou certificação LGPD nesta entrega. O requisito de exportação/exclusão foi tratado
como contrato de produto, sem afirmar conformidade jurídica.
