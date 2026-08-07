# Kreideheld

Kreideheld ist eine Offline-first SaaS-Webanwendung für Schreinereien und andere
Handwerksbetriebe zur Verwaltung von Restmaterial (Massivholz, Plattenmaterial,
Rollenware). Jedes Reststück wird über eine vom System vergebene, vierstellige
Kreidenummer identifiziert, die händisch auf das physische Material geschrieben
wird. Mitarbeiter können anhand von Mindestmaßen passende Reste finden, ohne das
Lager manuell durchsuchen zu müssen.

## Inhaltsverzeichnis

- [Konzept](#konzept)
- [Architektur-Überblick](#architektur-überblick)
- [Tech-Stack](#tech-stack)
- [Projektstruktur](#projektstruktur)
- [Datenmodell](#datenmodell)
- [Multi-Tenancy](#multi-tenancy)
- [Offline-Sync-Konzept](#offline-sync-konzept)
- [Setup](#setup)
- [Entwicklungs-Workflow](#entwicklungs-workflow)
- [Roadmap](#roadmap)

## Konzept

Ein Betrieb (Chef-Account) registriert sich per E-Mail und verwaltet darüber
ein eigenes Mandanten-Konto. Der Chef legt Mitarbeiter-Unteraccounts an, die
über eine systemseitig vergebene Kennung ohne eigene Registrierung einloggen.

Der Chef definiert in den Einstellungen frei, welche Rest-Typen es in seinem
Betrieb gibt (z. B. "Massivholz", "Plattenmaterial", "Kantenband") und welche
Maßfelder für jeden Typ erfasst werden sollen (Stärke/Höhe, Länge, Breite,
Restmeter). Zusätzlich stellt er ein, ob Maße in Millimeter oder Zentimeter
angezeigt werden sollen – gespeichert wird intern immer in Millimeter.

Mitarbeiter sehen ausschließlich die vom Chef konfigurierte Eingabemaske und
haben keinen Zugriff auf Preisinformationen.

## Architektur-Überblick

```
┌─────────────────┐        REST/JSON         ┌──────────────────┐
│  React Frontend  │ ◄──────────────────────► │  FastAPI Backend  │
│  (Vite + TS)     │                          │                    │
│                  │                          └─────────┬──────────┘
│  ┌────────────┐  │                                    │
│  │ IndexedDB  │  │  Offline-Cache & Outbox            │
│  │ (Dexie.js) │  │                                    ▼
│  └────────────┘  │                          ┌──────────────────┐
│                  │                          │   PostgreSQL      │
│  Workbox / PWA   │                          │  (shared DB,      │
│  (App-Shell-     │                          │   tenant_id auf   │
│   Caching)       │                          │   jeder Zeile)    │
└─────────────────┘                          └──────────────────┘
```

Das Frontend arbeitet offline-first: Lesezugriffe kommen primär aus IndexedDB,
Schreibzugriffe landen zunächst lokal und in einer Outbox-Tabelle, die bei
bestehender Verbindung mit dem Backend synchronisiert wird.

## Tech-Stack

| Bereich              | Technologie                          | Begründung |
|----------------------|---------------------------------------|------------|
| Backend-Framework    | FastAPI (Python)                     | Async-nativ, automatische OpenAPI-Doku, passt zu bestehender Python-Erfahrung |
| ORM / Migrationen    | SQLAlchemy + Alembic                 | Ausgereift, explizite Kontrolle über Schema-Änderungen |
| Datenbank            | PostgreSQL                            | Relational, robust, gute Unterstützung für UUIDs und JSONB |
| Auth                 | JWT (python-jose), Passlib           | Zustandslose Auth, passend für Mobile/PWA-Clients |
| Frontend-Build       | Vite                                  | Schneller Dev-Server, moderner Standard gegenüber CRA |
| Frontend-Framework   | React + TypeScript                    | Typsicherheit, breite Marktrelevanz |
| Lokale Datenhaltung  | Dexie.js (IndexedDB-Wrapper)          | Promise-basierte, angenehme API für Offline-Speicherung |
| Server State         | TanStack Query                        | Caching, Retry-Logik, Ladezustände |
| PWA / Offline-Shell  | vite-plugin-pwa (Workbox)             | Standardweg, Workbox mit Vite zu verbinden |
| Containerisierung    | Docker Compose (für PostgreSQL)       | Reproduzierbare lokale Datenbank ohne native Installation |

## Projektstruktur

```
kreideheld/
├── docker-compose.yml          # PostgreSQL-Container für lokale Entwicklung
├── backend/
│   ├── venv/                   # Python Virtual Environment (nicht versioniert)
│   ├── app/
│   │   ├── main.py             # FastAPI-Einstiegspunkt
│   │   ├── config.py           # Settings (liest .env)
│   │   ├── database.py         # Engine, Session, Base
│   │   ├── models.py           # SQLAlchemy-Models
│   │   ├── schemas.py          # Pydantic-Schemas (Request/Response)
│   │   ├── auth.py             # JWT, Passwort-Hashing, Tenant-Scoping
│   │   └── routers/            # API-Endpunkte, ein Modul pro Ressource
│   ├── alembic/                # Datenbank-Migrationen
│   ├── requirements.txt
│   └── .env                    # DATABASE_URL etc. (nicht versioniert)
├── frontend/
│   ├── src/
│   │   ├── db/                 # Dexie-Schema, Sync-Logik
│   │   ├── api/                # API-Client (Axios/Fetch-Wrapper)
│   │   ├── components/
│   │   ├── pages/
│   │   └── context/            # z. B. Einheiten-Kontext (mm/cm)
│   ├── public/
│   ├── vite.config.ts          # inkl. vite-plugin-pwa Konfiguration
│   └── package.json
└── README.md
```

## Datenmodell

Zentrale Tabellen (siehe `backend/app/models.py` für die vollständige Definition):

- **`tenants`** – ein Datensatz pro Chef-Account/Betrieb. Enthält E-Mail,
  Passwort-Hash, Einheiten-Einstellung (mm/cm) und Abo-Status.
- **`accounts`** – Mitarbeiter-Unteraccounts, gehören zu genau einem Tenant,
  identifiziert über ein systemseitig vergebenes Kürzel (z. B. `MA1`).
- **`rest_typ_definitionen`** – vom Chef frei benannte Rest-Typen inklusive
  Konfiguration, welche Maßfelder (Stärke/Höhe, Länge, Breite, Restmeter)
  angezeigt werden und ob die Maßsuche eine gedrehte Eingabe akzeptiert.
- **`material_catalog`** – Materialarten/Holzarten, jeweils einem Rest-Typ
  zugeordnet.
- **`reste`** – die eigentlichen Lagerbestände. Maße werden ausschließlich in
  Millimeter gespeichert; die Kreidenummer ist nur innerhalb eines Tenants
  eindeutig.

Alle synchronisierbaren Tabellen führen `updated_at`, `deleted_at` (Soft
Delete) und, wo relevant, `synced_at` mit, um Offline-Synchronisation und
Last-Write-Wins-Konfliktauflösung zu ermöglichen.

## Multi-Tenancy

Es wird eine gemeinsame Datenbank mit Mandantentrennung über `tenant_id`
verwendet (Shared-Database-Ansatz), nicht separate Datenbanken pro Chef. Das
ist der in SaaS-Anwendungen übliche Ansatz und deutlich wartungsärmer als
Datenbank- oder Schema-pro-Mandant-Lösungen.

**Wichtige Regel:** Jede Datenbankabfrage auf mandantenspezifische Tabellen
muss nach `tenant_id` filtern. Die `tenant_id` wird serverseitig aus dem
JWT-Token extrahiert (nie aus Client-Eingaben übernommen) und über eine
FastAPI-Dependency in jeden Router injiziert. Als zusätzliche Absicherung ist
mittelfristig Row-Level-Security (RLS) auf PostgreSQL-Ebene vorgesehen.

## Offline-Sync-Konzept

- **Lesen:** Das Frontend liest primär aus IndexedDB (Dexie). Nach jedem
  erfolgreichen API-Call wird die lokale Kopie aktualisiert.
- **Schreiben:** Änderungen werden sofort lokal gespeichert und zusätzlich in
  eine `pendingChanges`-Tabelle (Outbox-Pattern) geschrieben.
- **Sync:** Sobald eine Verbindung besteht, verarbeitet eine Sync-Routine die
  Outbox über zwei Endpunkte:
  - `GET /sync/pull?since=<timestamp>` – alle serverseitigen Änderungen seit
    dem letzten Abgleich.
  - `POST /sync/push` – alle lokal ausstehenden Änderungen.
- **Konfliktauflösung:** Last-Write-Wins anhand `updated_at`. IDs werden
  clientseitig als UUID erzeugt, um Kollisionen bei parallelem Offline-Anlegen
  zu vermeiden.

## Setup

### Voraussetzungen

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose

### PostgreSQL starten

```bash
docker compose up -d
```

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Datenbank-URL ggf. anpassen
alembic upgrade head
uvicorn app.main:app --reload
```

API-Dokumentation ist danach unter `http://localhost:8000/docs` erreichbar.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend läuft standardmäßig unter `http://localhost:5173`.

## Entwicklungs-Workflow

Das Projekt wird bewusst in dieser Reihenfolge aufgebaut, um nicht mehrere
Fehlerquellen gleichzeitig debuggen zu müssen:

1. Backend + PostgreSQL: CRUD-Endpunkte, online-only, über `/docs` getestet
2. Frontend online-only: alle Screens funktional gegen die API, ohne
   IndexedDB oder Sync-Logik
3. IndexedDB als Lesecache (Dexie)
4. Outbox-Pattern für Schreibvorgänge inkl. Sync-Routine
5. PWA/Workbox zuletzt: App-Shell-Caching für Offline-Erreichbarkeit der
   Anwendung selbst

## Roadmap

- [ ] Basis-Schema und Migrationen (Tenants, Accounts, Rest-Typen, Reste)
- [ ] Auth: Chef-Login (E-Mail/Passwort), Mitarbeiter-Login (Tenant-Code + Kürzel)
- [ ] CRUD-Endpunkte für Reste und Materialkatalog (online-only)
- [ ] Konfigurierbare Rest-Typ-Verwaltung im Chef-Frontend
- [ ] Einheiten-Umrechnung (mm/cm) im Frontend
- [ ] IndexedDB-Integration (Dexie)
- [ ] Sync-Endpunkte (`/sync/pull`, `/sync/push`) und Outbox-Logik im Client
- [ ] PWA-Konfiguration mit vite-plugin-pwa
- [ ] Row-Level-Security in PostgreSQL als zusätzliche Mandanten-Absicherung
- [ ] Abo-/Billing-Anbindung für Chef-Accounts
