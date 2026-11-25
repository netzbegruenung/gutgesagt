# Gut gesagt Architecture Documentation

## Overview

Gut gesagt is a progressive content platform with semantic search capabilities for green political activism. The application runs in multiple environments with different configurations.

## Environment Overview

### 1. Local Development
- **Purpose**: Active development with hot-reload
- **Access**: http://localhost:4200 (frontend), http://localhost:5054 (BFF), http://localhost:8000 (API)
- **Infrastructure**: Services run locally, only Qdrant and PostgreSQL in Docker (`docker-compose.local-dbs.yml`)
- **Authentication**: E-mail login against `managed-users.json` (`test.user@example.com`/`Liebe>Hass!`)

### 2. Docker Development
- **Purpose**: Testing containerized deployment locally
- **Access**: http://localhost:8080 (frontend via nginx proxy; `docker-compose.dev.yml` publishes container port 80 on host port 8080)
- **Infrastructure**: All services in Docker containers
- **Authentication**: E-mail login against `managed-users.json` (`test.user@example.com`/`Liebe>Hass!`)

### 3. Test Environment
- **Purpose**: Integration testing and demos
- **Access**: https://gutgesagt-test.netzbegruenung.de
- **Infrastructure**: Docker containers on verdigado's internal infrastructure
- **Authentication**: Whatever the BFF configuration enables (`GET /api/auth/modes`); since the realm
  move on 20 November 2026 only the own Keycloak realm `gutgesagt`, like production. The accounts are
  not part of this repository. The login selection shows only the enabled ways (#600)
- **Management**: Rolled out manually on verdigado's internal infrastructure; details are documented internally

### 4. Production Environment
- **Purpose**: Live system for Netzbegrünung members
- **Access**: https://gutgesagt.netzbegruenung.de (contentgruen.de redirects here)
- **Infrastructure**: Docker containers on verdigado's internal infrastructure
- **Authentication**: Own Keycloak realm `gutgesagt`, Netzbegrünung as identity provider
  (`docs/KEYCLOAK_REALM.md`)
- **Management**: Rolled out on verdigado's internal infrastructure; details are documented internally

## Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Browser                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Nginx (Prod/Test)                   │
│                  OR Direct Access (Local/Docker)                │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
┌─────────────────────┐ ┌─────────────┐ ┌──────────────────┐
│  Frontend (Angular) │ │  BFF (.NET) │ │ Semantic Search  │
│  Port: 8080/4200    │ │ Port: 5054  │ │   (FastAPI)      │
│                     │ │             │ │  Port: 8000      │
│  Container nginx    │ │   YARP      │ │                  │
│  serves static      │ │   Proxy     │ │  E5 embeddings   │
└─────────────────────┘ └─────────────┘ └──────────────────┘
                                │               │
                                └───────┬───────┘
                                        ▼
                    ┌──────────────────────────────────────┐
                    │  Qdrant (Vector DB)  │  PostgreSQL     │
                    │  Port: 6333          │  (application   │
                    │                      │   data)         │
                    │                      │  Port: 5433→5432│
                    └──────────────────────────────────────┘

Host ports are shown. In Docker, PostgreSQL is published on host port 5433 and
listens on 5432 inside the container.
```

## Component Details

### Frontend (Angular)
- **Technology**: Angular 20+, Angular Material UI
- **Deployment**:
  - **Local**: Angular CLI dev server (webpack) on port 4200
  - **Docker/Test/Prod**: nginx container serving static files on port 80
- **Environment Config**:
  - `environment.ts` - Active configuration
  - `environment.local.ts` - Local development (baseUrl: empty, `ng serve` proxies to the BFF via `proxy.conf.json`)
  - `environment.docker.ts` - Docker mode (baseUrl: empty for proxy)
  - `environment.prod.ts` - Production (uses placeholders replaced at runtime)

### BFF (Backend-for-Frontend)
- **Technology**: .NET 9.0, YARP reverse proxy
- **Purpose**:
  - Authentication handling (Keycloak or Direktanmeldung)
  - API gateway/proxy to semantic search service
  - User context injection via headers
- **Configuration**:
  - `USE_KEYCLOAK` - Enable/disable Keycloak SSO
  - `BACKEND_URL` - Semantic search service URL
  - `FRONTEND_URL` - Frontend URL for redirects

### Semantic Search Service
- **Technology**: Python FastAPI, Qdrant vector database, E5 multilingual embeddings
- **Databases**:
  - Qdrant for vector embeddings and content storage
  - PostgreSQL for application metadata (usage tracking)
- **Features**:
  - Unified content storage with type filtering
  - Semantic similarity search using 768-dimensional E5 embeddings, stored as the named vector
    `e5_base` and queried with `query_points`, so that further models can sit next to it (#395)
  - "Alles zum Thema" (#754): a search input of one to three words that matches a Stichwort or the
    name of a Thema (`domain/themen.json`, normalised in `domain/themen_abgleich.py`, no model)
    adds `passende_themen` to the search response, at most two, each with the most used Aussagen
    of the Thema (`services/themen_aussagen_service.py`); `GET /api/v1/search/thema/{schluessel}`
    lists all of them, open to visitors like the search. It runs after the hits and does not
    change them or their order; the search text is matched in memory only, neither stored nor
    logged.
  - Asynchronous data seeding
  - RESTful API with OpenAPI docs
- **Architecture**:
  - Repository pattern for data access
  - Service layer for business logic
  - Dependency injection for testability

### PostgreSQL
- **Purpose**: Application data — votes, usage tracking, search tracking, moderation reports,
  Sperren with Sperrgrund and Widerspruch (`sperren`), and per person the usage last shown in the Rückmeldung (`gesehene_nutzung`); for the entdoppelte Nutzung the check values of the current day (`nutzung_heute`, HMAC only), the pair check values of the last seven days (`muster_pruefwerte`, HMAC only) and the Muster-Hinweise for admins (`muster_hinweise`, #352); for „Ja, gepostet“ after copying the check values of the current calendar week (`gepostet_pruefwerte`, HMAC only) and one number per past week (`gepostet_wochen`, #643, switch `SEMANTIC_SEARCH_GEPOSTET_AKTIV`, default off); for the Teams the Mitgliedschaften without any reference to the invitation (`team_mitgliedschaften`), the counter per team and Saison (`team_nummern`), the answer on showing teams at the name (`team_oeffentlich`) and admin settings such as the current Saison (`einstellungen`), switch `SEMANTIC_SEARCH_TEAMS_AKTIV`, default off.
  Content and its vector embeddings live in Qdrant, not in PostgreSQL.
- **Image**: `postgres:16-alpine` (service `postgres-app`, container `gutgesagt-app-postgres`)
- **Access**:
  - Local/Docker: localhost:5433 (container port 5432)
  - Test/Prod: Internal Docker network

> The schema is defined by the SQLAlchemy models
> (`app/infrastructure/database/models.py`); the semantic service creates missing tables
> with `create_all` on start. `mvp/backend/postgres-app/init.sql` additionally creates
> `usage_tracking` and `usage_events` on an empty volume and must match the models
> exactly (checked by `tests/integration/test_migrationen.py`). It is baked into the
> `gutgesagt-postgres-app` image used by test and production, and bind-mounted by the
> local compose files. Existing databases get schema changes from
> `mvp/backend/postgres-app/migrations/`: the semantic service applies them on start,
> after `create_all`, and records each in the table `migrationsprotokoll`
> (`app/infrastructure/database/migrationen.py`).

## Nginx Configuration

Both frontend configurations (`nginx.conf`, `nginx.docker.conf`) share
`nginx.protokoll.conf`: the access log carries the path without query string and no
referrer, and no line for searches or the results page (#275, see
`docs/LOESCHKONZEPT.md`).

Link previews (#360): for `/beitrag/<id>` and `/result` both configurations serve
`index.html` with SSI. An internal subrequest goes straight to
`gutgesagt-semantic-search:8000/api/v1/linkvorschau/...` on the Docker network (resolved at
request time via Docker's DNS; 1 s each for lookup, connect and read), and the returned
`og:title`, `og:description` and `og:url` replace the block `linkvorschau_allgemein` in
`index.html`. On 204 (gesperrt, gelöscht, unknown), any status other than 200, an error or a
timeout the general block stays. The search text travels only in the header `X-Suchtext`, not
in a URL, and subrequests are not logged. The BFF blocks `/api/v1/linkvorschau` at the edge
(`EndpointPolicy.Blocked`). Every other path gets `index.html` unchanged.

### Local Development
- **No nginx** - Direct access to services

### Docker Development
- **Frontend Container nginx** (`nginx.docker.conf`):
  - Serves Angular static files
  - Proxies `/api/*`, `/login`, `/logout` to BFF container
  - Single entry point on port 80

### Test Environment
- **Frontend Container nginx**: Serves static files
- **External nginx**: Routes traffic to containers

### Production Environment
- **Frontend Container nginx**: Serves static files
- **External nginx** (part of the operated infrastructure):
  - TLS termination
  - Routes gutgesagt.netzbegruenung.de → frontend container
  - Routes bff.gutgesagt.netzbegruenung.de → BFF container
  - Keycloak integration

## Authentication Flow

### Direktanmeldung (development only)
Login with e-mail address and password from a users file. It does not depend on the
environment: it is on whenever `ENABLE_MANAGED_AUTH` is true (the default) and the BFF finds a
non-empty users file. Local and Docker development log in this way. Since the realm move on
20 November 2026 it is off in test and production: the former Beta-Zugänge moved into the
Keycloak realm (#488, `docs/KEYCLOAK_REALM.md`, „Beta-Zugänge umziehen“).

1. User enters e-mail address and password in frontend ("Direktanmeldung")
2. Frontend POSTs to BFF `/api/auth/login/managed`
3. BFF validates against `managed-users.json` (bcrypt hashes; example users in
   `mvp/config/managed-users.example.json`, e.g. `test.user@example.com`/`Liebe>Hass!`)
4. BFF sets session cookie
5. BFF returns user info

`managed-users.json` is gitignored. `mvp/run-local.sh` creates it from the example file for
the Docker dev stack; for the local mode copy it by hand (`docs/DEV-SETUP.md`). Without the
file the Direktanmeldung is off.

The old dummy login (`POST /login`, user id `test-user-id-1`) is gone since #488;
`DUMMY_AUTH_USERNAME`/`DUMMY_AUTH_PASSWORD` have no effect any more.

### Keycloak (Production)
1. User accesses protected resource
2. BFF redirects to Keycloak login
3. User authenticates with Keycloak
4. Keycloak redirects back with token
5. BFF validates token and creates session
6. BFF injects user context in API calls

On every request with the session cookie the BFF also checks that its issuer is the configured
realm (`Keycloak:Authority`) and ends sessions from another realm, e.g. after a realm switch
(`BFF/Services/KontoPruefung.cs`, `AnmeldeAussteller.cs`).

### Session checks answer visitors with 200, not 401
`GET /api/check-session` and `GET /api/user-info` always answer 200; whether someone is logged
in is the field `isAuthenticated` (`false` for visitors, also right after the BFF ended a
session). The frontend asks on every page view (`AppComponent`, the guards) and reads only the
field (`src/app/auth/sitzung.ts`). Reason: test and production sit behind the verdigado IPv4
gateway, whose fail2ban bans an IP for 10 minutes after 20 responses 401 in 5 minutes
(`haproxy-auth-flood`; 50 × 404 for `haproxy-probing`). In a hall WLAN hundreds of visitors
share one IP (BDK), so a 401 for every visitor would lock out the whole hall. Real 401s stay
where a login is needed and missing: the auth gate in front of the proxy (`EndpointPolicy`).

## Deployment Configurations

### Docker Compose Files
- **docker-compose.dev.yml**: Full stack for local Docker development
- **docker-compose.local-dbs.yml**: Qdrant + PostgreSQL only, for local component-based development
- **docker-compose.prd.yml**: Placeholder; the production compose file is managed outside this repository

Container names are the same in dev, test and production: `gutgesagt-app-postgres`,
`gutgesagt-semantic-search`, `gutgesagt-qdrant`.

### Container Registry
- Test/Prod images: `git.verdigado.com/netzbegruenung-images/*`
- Local: Built from source

## Data Flow

1. **User Request** → Frontend (Angular/nginx)
2. **API Call** → BFF (authentication & routing)
3. **Business Logic** → Semantic Search Service
4. **Data Storage** → Qdrant (content + vectors) and PostgreSQL (application data)
5. **Response** → Back through the chain

## Environment Variables

### Frontend
- `PRODUCTION` - Production mode flag
- `API_BASE_URL` - BFF endpoint (empty for proxy mode)
- `USE_KEYCLOAK` - Authentication mode

### BFF
- `ASPNETCORE_ENVIRONMENT` - Development/Production
- `USE_KEYCLOAK` - true/false
- `BACKEND_URL` - Semantic search service URL
- `FRONTEND_URL` - Origin the SPA is served from. Drives the OIDC redirect *and* the CORS
  allowlist, so each environment trusts only its own frontend. **Required** outside
  `Development`; startup fails if it is missing.
- `CORS_ALLOWED_ORIGINS` - Optional, comma-separated extra CORS origins for cases where more
  than one hostname serves the SPA. Unset in all current environments.
- `ADMIN_USER_IDS` - Optional, comma-separated user ids that get admin rights in addition to
  anyone carrying an admin claim (`AdminPolicy`). Values are compared to the same string the
  BFF forwards as `X-User`, i.e. the Keycloak `sub` claim or the `userId` field from
  `managed-users.json` - not e-mail addresses, not usernames. Comparison is ordinal and
  case-sensitive, matching how the Python service compares `SEMANTIC_SEARCH_ADMIN_USERS`;
  set both to the same value so one entry means one person on both sides. Unset means no
  extra admins and is not an error - the claim alone decides, as before. Whitespace around
  entries is trimmed.

  The id to enter is the `userId` field of `GET /api/user-info`, read while that person is
  logged in: it is exactly the string this check compares, whereas reading a `sub` claim by
  hand is a detour - .NET's inbound claim mapping renames `sub` to `nameidentifier` before
  the application sees it. The list is parsed once at startup, so changing it only takes
  effect after the BFF container is restarted. Never put an id from
  `managed-users.example.json` on the list: their passwords are documented in this
  repository.

  It exists because the claim route needs a Keycloak protocol mapper: `OnTokenValidated`
  copies token claims unchanged, so a flat `isAdmin`/`role` claim has to come from the realm
  configuration, which lives outside this repository.

- `STARTKONTEN` - Optional, comma-separated user ids of Startkonten (`GLOSSARY.md`), compared
  like `ADMIN_USER_IDS`. Only for these function accounts the BFF also sends the unshortened
  name in `X-User-Full-Name` ("Redaktion Gut gesagt" instead of "Redaktion G."); the full name
  of a person never leaves the BFF. Set it to the same value as `SEMANTIC_SEARCH_STARTKONTEN`,
  which the search service checks as well. Unset: every name stays shortened.

### Semantic Search

All settings use the `SEMANTIC_SEARCH_` prefix (see `app/core/config.py`):

- `SEMANTIC_SEARCH_QDRANT_URL` - Qdrant endpoint
- `SEMANTIC_SEARCH_QDRANT_COLLECTION` - Qdrant collection name
- `SEMANTIC_SEARCH_APP_DATABASE_URL` - PostgreSQL connection string
- `SEMANTIC_SEARCH_DATA_PATH` - Seed data path
- `SEMANTIC_SEARCH_METADATA_PATH` - Persistent metadata storage path
- `SEMANTIC_SEARCH_LOG_LEVEL` - DEBUG/INFO
- `SEMANTIC_SEARCH_TAGESDECKEL_BEITRAEGE` - Tagesdeckel (GLOSSARY.md): Beiträge, Aussagen and
  Einwürfe a person may create per UTC day (default 20; admins and Startkonten exempt). Above it
  the creating routes answer 429 with `"error": "TAGESDECKEL"` (`middleware/tagesdeckel.py`).
- `SEMANTIC_SEARCH_<LIMIT>_RATE_LIMIT_ANFRAGEN` - requests per window of the rate limits without
  login, counted per Anschluss (`utils/rate_limiter.py`). In a venue WLAN all visitors share one
  address, so operations raise them there. `<LIMIT>` and default: `AEHNLICHE_AUSSAGEN` 60 and
  `SUCHAUSSAGE` 60 (10 min), `FEEDBACK` 5, `MELDUNG` 5, `EINLADUNG` 30, `EINLADUNG_PRUEFEN` 60
  (15 min each). The windows are fixed: the privacy policy names the periods that follow from them.
  `SEMANTIC_SEARCH_TEAM_BEITRETEN_RATE_LIMIT_ANFRAGEN` (default 20 in 15 min) limits
  `POST /api/v1/einladungen/beitreten` per logged-in person instead of per Anschluss, so joins in a
  venue WLAN do not use up the budget for redeeming without an account.
- `SEMANTIC_SEARCH_DIESELBE_AUSSAGE_NLI` - NLI-Stufe (#387): `aus`, `schatten` (for the
  same-Aussage check the similarity threshold decides and the NLI model only counts along) or
  `an` (default since #575, as on test and production: the NLI model decides whether a new text
  is the same Aussage). In `schatten` and `an` the model also drops contradicting Aussagen from
  the "Antwort auf" suggestions; ~1.2 GB extra RAM, threads as `SEMANTIC_SEARCH_EMBEDDING_THREADS`. Thresholds `SEMANTIC_SEARCH_NLI_*` and
  `SEMANTIC_SEARCH_AUSSAGE_VORSCHLAG_*`, measured in `tests/regression/MESSSET.md`.
- `SEMANTIC_SEARCH_NLI_BESTAETIGER` - Bestätiger, a second NLI model for the same-Aussage check
  (`true`/`false`, default `false`; no effect with the NLI-Stufe `aus`). It only judges
  candidates the first model barely misses without contradicting, and the first model keeps a
  veto (`SEMANTIC_SEARCH_NLI_BESTAETIGER_VETO_AB`, default 0.1). Up to ~2.2 GB extra RAM.
  Both models together wait at most the same 3 s for their locks as the first model alone;
  each computes with `SEMANTIC_SEARCH_EMBEDDING_THREADS`, so two searches can use both models
  at once. The Bestätiger is preloaded after the first model, not in parallel.
  Measured in `tests/regression/MESSSET.md` and `SUCHTESTSET.md` (Zerfaserung).
- `SEMANTIC_SEARCH_SUCHE_POLARITAET_NLI` - polarity penalty of the search (#574): `aus` (word
  lists in `utils/negation_detector.py`), `schatten` (default: word lists decide, the NLI model
  judges in the background, only counters in the log) or `an` (the first NLI model decides: an
  Aussage that contradicts the query in both directions with at least
  `SEMANTIC_SEARCH_SUCHE_POLARITAET_WIDERSPRUCH_AB`, default 0.9, is penalised and its answers
  do not come back via the direct path). Questions, keyword queries (under three words) and an
  unavailable or busy model (2 s) fall back to the word lists. Same model object as the
  NLI-Stufe, so no extra RAM while the NLI-Stufe is not `aus` (otherwise this switch loads the
  model itself); measured in `tests/regression/SUCHTESTSET.md`.
- `SEMANTIC_SEARCH_SUCHE_BEZUG_AB` - for a query of three words or more, an Aussage below this
  embedding similarity (default 0.87) is no hit (`services/search/bezug.py`); its answers come
  via the direct path only with their own raw similarity of at least
  `SEMANTIC_SEARCH_SUCHE_BEZUG_DIREKT_AB` (0.86). For a statement query (no
  question) `SEMANTIC_SEARCH_SUCHE_BEZUG_NLI` (default `true`) also asks the first NLI model
  about Aussagen up to `SEMANTIC_SEARCH_SUCHE_BEZUG_SICHER_AB` (0.92): they count only with
  entailment of at least `SEMANTIC_SEARCH_SUCHE_BEZUG_FOLGERUNG_AB` (0.2) in one direction; the
  search waits for it (2 s at most, then they count). Measured in
  `tests/regression/SUCHTESTSET.md`, section Bezug.
- `SEMANTIC_SEARCH_SUCHE_INHALTSTOR` - for a query of three words or more (default `true`),
  a hit in the uncertain band counts only if query and hit share a content word: a lemma of
  the query's nouns or proper nouns in the Aussage, the contribution's title or text, or on
  the direct path the Aussagen it answers (`antwort_ids`) (`services/search/inhaltstor.py`).
  Band: Aussage similarity from `…_INHALTSTOR_AB` (0.82) to below `…_INHALTSTOR_AUSSAGE_BIS`
  (0.92), direct raw score above 0.82 to below `…_INHALTSTOR_DIREKT_BIS` (0.90). spaCy model
  of Gegenlesen; open without nouns or before the model is loaded. Measured in
  `tests/regression/SUCHTESTSET.md`, section Inhaltstor.
- `SEMANTIC_SEARCH_HERKUNFT_PRUEFEN_AKTIV` - upper bound of the Schalter `herkunft_pruefen`
  (#759, default `true`: no personal data); takes effect only when an admin switches it on.
  Then the service fetches the links of all visible Herkünfte once a night between 02:00 and
  06:00 UTC (`services/herkunft_pruefen.py`, one request per second at most, HEAD then GET,
  headers only, ports 80, 443, 8080 and 8443 only)
  and lists dead or moved ones for admins (table `herkunft_pruefung`). Outbound HTTP(S) from the
  semantic service to arbitrary hosts; only http/https, every resolved address must be global,
  also after redirects, IPv4 embedded in IPv6 included (`utils/sicherer_abruf.py`). No proxy
  from the environment is used. Switched off, the hourly task empties the table once.
- `SEMANTIC_SEARCH_ANTWORTEN_HINWEIS_AKTIV` - upper bound of the Schalter `antworten_hinweis`
  (#760, default `false` until the privacy policy names it; nothing is stored); takes effect
  only when an admin switches it on too.
  Then the Besuch (`POST /api/v1/usage/users/me/besuch`) also returns
  `antworten_auf_eigene_aussagen` (answers by others to one's own Aussagen, linked in the last
  7 days; `null` while off) and `GET /api/v1/usage/users/me/aussagen` lists one's own Aussagen
  with their answers (404 while off), `services/antworten_hinweis.py`.
- `SEMANTIC_SEARCH_TEAMS_AKTIV` - upper bound of the Schalter `teams` (Teams over
  invitations, GLOSSARY.md "Team", "Teamlink", "Mitgliedschaft", "Saison"; default `false`: a
  Mitgliedschaft may reveal political leaning and place, so it needs its own consent, the DSFA
  addendum and the privacy policy section "Teams"); takes effect only when an admin switches it
  on too (`services/team_service.py`, `domain/teams.py`). While off, team fields of invitations
  are ignored, every invitation is a plain account link, and `POST /api/v1/einladungen/beitreten`
  answers 404. `GET /api/v1/teams/meine` answers 404 only when the person has no Mitgliedschaft;
  existing ones are still listed (`teams_aktiv: false`, no public toggle) so that leaving a team
  stays as easy as joining (Art. 7(3) GDPR). While on:
  - Admin: `GET /api/v1/einladungen` adds `team` `{name, motiv, saison, art, zustimmung_am,
    mitglieder}` per invitation (`mitglieder` is only a count; no member list, export or API on
    other people's memberships exists, admins included), plus `teams_aktiv`, `aktuelle_saison`,
    `motive` and `teamname_hinweis`; `POST` and `PATCH /api/v1/einladungen` accept `team_name`
    (at most 40 characters, requires `team_motiv`), `team_motiv` (one of the Meilenstein motifs),
    `team_saison` (at most 20, default the current Saison), `team_art` (`anlass`, the default,
    or `gruppe`, GLOSSARY.md "Team") and `team_zustimmung_am` (date the written consent of the
    group's leadership was given; required with `gruppe`, not in the future, rejected with
    `anlass`). Stored at the invitation (`einladungen.team_art`, `team_zustimmung_am`,
    migration `2026-11-26-teams-nach-gruppe.sql`) as evidence for admins only, no names; the
    Mitgliedschaft carries neither. A `PATCH` with `team_name` replaces the whole team: without
    `team_art` it becomes `anlass` and the date is cleared, like a missing `team_motiv` is
    rejected. With `gruppe` the team name is exactly the group's public name (no place or
    year, the Saison is separate); the greeting uses it as {gruppe}. Renaming a team
    everywhere (invitations, memberships, number counter) after a group withdraws its
    consent: `mvp/scripts/manual/team_umbenennen.sql`, only into a neutral name (requires
    `-v art=anlass`, aborts otherwise; renaming into another group needs new consent of the
    members).
  - Redeeming: `POST /api/v1/einladungen/pruefen` returns `team` with the greeting, the next
    number, `art` (with `gruppe` the greeting shows the sentence that the team is named after the
    group with its consent; `zustimmung_am` is never sent here) and the consent wording
    `team-2026-11-26` plus both button texts. For a logged-in
    member it returns `team` with `eigene_nummer` even when the invitation is no longer
    redeemable ("schon dabei"); everyone else gets no team then.
    `POST /api/v1/einladungen/einloesen` stores a Mitgliedschaft only with
    `team_einwilligung: true` plus `team_einwilligung_kennung` (the wording id shown; unknown, earlier
    or missing: 422) and only when Keycloak creates a new account. New consents accept only the
    ids in `EINWILLIGUNG_GELTEND` (the current one); earlier ids stay in `EINWILLIGUNG_WORTLAUTE`
    for existing memberships, which keep them.
  - Joining while logged in: `POST /api/v1/einladungen/beitreten` `{code, einwilligung: true,
    einwilligung_kennung, oeffentlich?, oeffentlich_kennung?}` counts against the invitation's
    limit once; a second join returns the existing number (`neu: false`). Own rate limit per
    person (see above).
  - Own teams only: `GET /api/v1/teams/meine` (all Saisons, newest first),
    `DELETE /api/v1/teams/meine/{id}` ("Team verlassen", deletes at once, also with the switch
    off; the number is never reassigned) and `PUT /api/v1/teams/oeffentlich` (second consent
    `team-oeffentlich-2026-11-25`; withdrawing always works).
  - Admin setting `aktuelle_saison` (table `einstellungen`, default the current UTC year):
    `GET /api/v1/moderation/schalter` lists it under `einstellungen`,
    `PUT /api/v1/moderation/schalter/einstellungen/{name}` `{wert}` changes it.
- `SEMANTIC_SEARCH_TEAM_FORTSCHRITT_AKTIV` / `SEMANTIC_SEARCH_TEAM_QUESTS_AKTIV` - upper bounds
  of the Schalter `team_fortschritt` (#784) and `team_quests` (#792), default `false`; switch on
  only after DSFA addendum V29 and the legal OK. `team_fortschritt` works only with `teams`,
  `team_quests` only with `team_fortschritt`. While on, the endpoints for Beiträge, Stimmen and
  "Ja, gepostet" raise the weekly counter `team_wochen` (team, Saison, week, no Kennung), and
  `GET /api/v1/teams/meine` carries `wirkung` (last closed week, rounded texts, from 5 members)
  and `quest` per own team of the current Saison (`services/team_fortschritt_service.py`). The
  first `GET /api/v1/teams/meine` of a week writes that week's quest (`team_quests`). The weekly
  check values for deduplication live in process memory, so this assumes one uvicorn worker
  (as "Ja, gepostet" does); a restart mid-week can count something twice (too high, never too
  low). `team_wochen` and `team_quests` go with the team (docs/LOESCHKONZEPT.md). Deleting a
  team does not exist yet (invitations can only be switched off or changed, memberships go one
  by one); when it comes, the rows must go with it via `TeamFortschrittRepository.team_loeschen`
  (pass the caller's session to keep one transaction).
  `tests/unit/test_team_loeschung_nimmt_zaehler_mit.py` fails on Python, SQL and shell code that
  deletes `einladungen` or `team_nummern` in the usual forms without them (not on table names
  built at run time).
- `SEMANTIC_SEARCH_TEAMS_OEFFENTLICH_AKTIV` - upper bound of the Schalter `teams_oeffentlich`
  (default `false`; stays off on production until the data protection officer has advised).
  Own bound, deliberately not coupled to `SEMANTIC_SEARCH_ABZEICHEN_SICHTBAR_AKTIV`; works only
  together with `teams`, and an admin has to switch it on too. While on, logged-in viewers get
  `autor_teams` `[{name, motiv, motiv_name}]` at a post, the teams of the current Saison of
  authors who gave the second consent (no number); visitors never. While off, the second
  question is not asked, `GET /api/v1/teams/meine` reports `oeffentlich_verfuegbar: false` and
  `autor_teams` stays `null`.
- `DOCKER_CONTAINER` - set to `true` inside containers to enforce strict path validation

#### Schalter für das Spielgefühl (#782 to #793)

One Schalter per building block for the BDK, registered in `SPIEL_SCHALTER`
(`services/schalter_service.py`). Upper bound `SEMANTIC_SEARCH_<NAME>_AKTIV`, default `false`
everywhere; like every Schalter it also needs the admin value (Admin, "Schalter"), which is off
without an entry. The building blocks arrive in their own PRs; until then a switch changes
nothing. "public" means `GET /api/v1/funktionen` reports the effective value without login.
Team progress (#784) and team quests (#792) get their switches later.

| Schalter | Upper bound | Default | Public | Condition for switching on (issue) |
|----------|-------------|---------|--------|------------------------------------|
| `saison_ziel` | `SEMANTIC_SEARCH_SAISON_ZIEL_AKTIV` | off | yes | none; privacy policy sentence ships with #782 (see below) |
| `gartenansicht` | `SEMANTIC_SEARCH_GARTENANSICHT_AKTIV` | off | yes | none (#783) |
| `kopiert_erfolg` | `SEMANTIC_SEARCH_KOPIERT_ERFOLG_AKTIV` | off | yes | none (#785) |
| `konter_probe` | `SEMANTIC_SEARCH_KONTER_PROBE_AKTIV` | off | yes | none (#786) |
| `luecke_zu_gross` | `SEMANTIC_SEARCH_LUECKE_ZU_GROSS_AKTIV` | off | yes | none; while on (or while the browser holds the entry), the privacy policy shows the paragraph on the browser entry `gutgesagt-ton-bei-erfolgen`, DSFA V21 names it (#787) |
| `einwilligung_im_gewinn` | `SEMANTIC_SEARCH_EINWILLIGUNG_IM_GEWINN_AKTIV` | off | yes | none, wordings stay (#788) |
| `naechster_schritt` | `SEMANTIC_SEARCH_NAECHSTER_SCHRITT_AKTIV` | off | yes | none; privacy policy sentences ship with #789 |
| `wirkungs_echo` | `SEMANTIC_SEARCH_WIRKUNGS_ECHO_AKTIV` | off | no | DSFA addendum V31 (#790) |
| `danke_knopf` | `SEMANTIC_SEARCH_DANKE_KNOPF_AKTIV` | off | yes | DSFA addendum V31 (#791) |
| `danke_ohne_konto` | `SEMANTIC_SEARCH_DANKE_OHNE_KONTO_AKTIV` | off | yes | V31 and visitor marker (#495); works only with `danke_knopf` |
| `rangliste` | `SEMANTIC_SEARCH_RANGLISTE_AKTIV` | off | no | legal OK (wording, DSFA V28, privacy policy) and Punkte on (#793); works only with `punkte` |

#### Saisons and Gemeinschaftsziel (#782)

Table `saisons` (name, first and last day, goal in Widerspruchs-Wochen; no personal data),
rules in `domain/saisons.py`, `repositories/saison_repository.py` (overlap check under a table
lock, so at most one season runs on any day) and `services/saison_service.py`. With `saison_ziel`
effective, the running season replaces the setting "aktuelle Saison" for teams
(`einstellungen_service.aktuelle_saison()`); in a gap between two seasons the last ended season
stays the current one until the next begins, before the first season the setting applies. The
count is the sum of the existing weekly numbers of "Ja, gepostet" (`gepostet_wochen`) over the
closed weeks of the season; a boundary week shared by two seasons counts only for the season that
contains its Monday (`domain.saisons.wochen_der_saison`); nothing new is stored.

- `GET /api/v1/saisons/aktuell` (anonymous at the BFF): `{"balken": {name, ziel, erreicht}}`,
  `{"balken": null}` without a running season or below the threshold, 404 while the switch is off.
- `GET|POST /api/v1/moderation/saisons`, `PUT|DELETE /api/v1/moderation/saisons/{id}` (admins):
  list with state, create, change (running: only goal and end), delete (only before the start).
- Threshold for the public bar: `SEMANTIC_SEARCH_SAISON_ZIEL_SCHWELLE_WOCHEN` (default 3) closed
  weeks in a row with at least `SEMANTIC_SEARCH_SAISON_ZIEL_SCHWELLE_MENSCHEN` (default 25) people
  each, reached once at any time. The privacy notice names these numbers (section „Rückmeldung
  ‚Ja, gepostet‘“, wording by the legal review 25.11.): whoever changes either variable must update
  that sentence in `datenschutz.component.html` in the same change.
- For later building blocks (Rangliste per season): `SaisonService.alle()`, `.laufende(heute)`
  and the dataclass `domain.saisons.Saison` (`id`, `name`, `beginn`, `ende`, `ziel`, `wochen()`).

## Startup Scripts

### Local Development
- `run-local.bat/.sh` - Starts services locally with PostgreSQL in Docker
- Services run with hot-reload for development

### Docker Development
- `run-docker.bat/.sh` - Starts all services in Docker
- Uses docker-compose.dev.yml

### Utilities
- `mvp/scripts/setup/check-environment.sh/.bat` - Checks prerequisites
- `mvp/scripts/utils/switch-to-docker.sh/.bat` and `switch-to-local.sh/.bat` - Switch the active frontend environment config
- `mvp/scripts/utils/clean-all.sh/.bat` - Removes containers, volumes and build artifacts
- `scripts/safe-commit.bat/.sh` - Handles pre-commit hooks

## Network Architecture

### Local
- Direct connections between services
- No network isolation

### Docker
- Bridge network `mvp_default`
- Service discovery by container name
- Isolated from host network

### Production
- Docker overlay network
- External nginx for ingress
- Internal service mesh

## Security Considerations

### Local/Test
- Locally Direktanmeldung with the example accounts from `managed-users.example.json`; test signs
  in through the Keycloak realm like production
- No TLS (HTTP only)
- Open CORS for development

### Production
- Keycloak SSO authentication
- TLS termination at nginx
- Restricted CORS policy
- Network isolation
- Secrets managed outside this repository

### Known gap: seeding router
- `/api/v1/seeding/*` (`api/v1/seeding.py`) has no auth dependency. It is closed by the BFF
  edge block (`BFF/Proxy/EndpointPolicy.cs`, `Blocked`) and by port 8000 not being published
  on the hosts. `require_admin` would add nothing yet: it trusts `X-Is-Admin`, which anyone
  who reaches port 8000 can set, because the identity headers are not signed (#26).
  **Secure the seeding router once #26 is implemented.**

## Monitoring & Logging

### Current State
- Basic console logging
- Docker logs for containers
- No centralized logging yet
- Health check of the semantic search service: `GET /api/v1/health` (PostgreSQL, Qdrant,
  disk, memory)
- Betriebskennzahlen of the semantic search service: `GET /metrics` (Prometheus text
  format; requests per route template and status class, search duration; no personal
  data). Blocked at the BFF (`EndpointPolicy.Blocked`), scraped on the internal network
- What is monitored and how: `docs/DEPLOYMENT.md`, "Monitoring"; scraping and alerting
  are run by the operators

### Planned
- OpenTelemetry integration
- Centralized log aggregation

## Build & CI/CD

### Local
- Manual builds
- Hot-reload development

### Test/Production
- Woodpecker checks every pull request on Forgejo (`.woodpecker/ci.yaml`, required status
  for `main`, see `docs/CI.md`)
- Image builds after a green `ci` run: Woodpecker (`.woodpecker/build.yaml` on `main`,
  `release.yaml` on `v*` tags); the GitHub mirror runs no CI
- Container registry at git.verdigado.com (`netzbegruenung-images`)
- Test: runs the floating `:main` tag, rolled out manually by the operators
- Production: pins a release version (`:X.Y.Z`) by digest; how it updates: `docs/DEPLOYMENT.md`, "Updating Production"

## Storage & Persistence

### Development
- PostgreSQL in Docker with local volume
- Data persists between restarts

### Production
- PostgreSQL with persistent volumes
- Backup & restore with rotation (`mvp/scripts/backup/`), scheduled on verdigado's internal infrastructure
- Migrations applied by the semantic service on start (`mvp/backend/postgres-app/migrations/README.md`)
