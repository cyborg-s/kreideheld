# Kreideheld

Kreideheld ist eine Offline-first-Anwendung für Schreinereien und Handwerksbetriebe. Sie soll Restmaterialien mit einer Kreidenummer erfassbar und auffindbar machen – auch dann, wenn die Internetverbindung in der Werkstatt nicht stabil ist.

Der aktuelle Stand ist ein Entwicklungsstand, **keine produktionsfertige SaaS-Anwendung**. Die Account-, Passwort- und Session-Grundlagen sind implementiert; Offline-Sync, vollständige Ressourcen-Absicherung und das Produkt-Frontend folgen später.

## Projektstatus

### Implementiert

- FastAPI-REST-Backend mit SQLAlchemy und Pydantic
- SQLite für die lokale Entwicklung; PostgreSQL-Treiber und Docker-Compose-Konfiguration sind vorhanden
- Alembic-Migrationen für das Schema
- Tenant-, Account-, Resttyp- und Reststück-Modelle sowie erste CRUD-Routen
- Account-Modell mit Rollen, öffentlicher Login-ID, Argon2id-Passwort-Hash und Passwortwechselstatus
- Account-Authentifizierung, serverseitige Sessions und HttpOnly-Session-Cookie
- `current_account` als serverseitig aus der Datenbank geladener Request-Kontext
- RBAC und Tenant-Isolation für die **Account-Erstellung**
- pytest-Suite mit isolierter In-Memory-SQLite-Datenbank (`90 passed`, zuletzt verifiziert)
- React-/TypeScript-/Vite-Frontend als Prototyp

### In Entwicklung / teilweise implementiert

- Ressourcenrouten für Resttypen und Reststücke existieren, benötigen aber noch vollständiges, konsistentes Tenant-Scoping und eine Autorisierungsprüfung
- Das Frontend enthält vorhandene React-, Dexie-, React-Query- und PWA-Abhängigkeiten, ist aber noch nicht vollständig mit dem Backend, der Authentifizierung und einer Sync-Schicht integriert
- PostgreSQL ist als späterer produktionsnaher Datenbankbetrieb vorbereitet, die lokale Entwicklung verwendet derzeit SQLite

### Geplant

- OWNER-/Tenant-Registrierung
- Passwortwechsel und globale Durchsetzung von `password_change_required`
- Offline-Datenhaltung, Outbox-Sync und Konfliktauflösung
- PWA-/App-Shell-Ausbau
- Produktions- und Deployment-Hardening

## Architekturüberblick

```text
React / TypeScript / Vite (Prototyp)
              |
           REST API
              |
           FastAPI
              |
          Services
              |
         SQLAlchemy ORM
              |
 SQLite lokal / PostgreSQL später
```

- **Pydantic** beschreibt und validiert HTTP-Request- und Response-Schemas.
- **SQLAlchemy** bildet Modelle ab und verwendet gebundene Parameter für Datenbankzugriffe.
- **Alembic** versioniert Produktions- und Entwicklungsdatenbankschemas.
- **pytest** testet Services und HTTP-Routen gegen eine isolierte In-Memory-Datenbank.

## Tenant und Account-Modell

Ein Tenant ist ein Unternehmen. Ein Tenant kann mehrere Accounts besitzen:

```text
Tenant
  └── Accounts
```

Ein Account besitzt derzeit:

```text
interne UUID
tenant_id
account_id       # öffentliche Login-ID, z. B. AB-123456
name
email            # optional; für ADMIN erforderlich
role
password_hash
password_change_required
created_at
updated_at
```

Die interne UUID ist der technische Primärschlüssel. `account_id` ist die für Menschen bestimmte öffentliche Login-ID im Format `XX-123456`; sie ist keine geheime Kennung.

Verfügbare Rollen:

- `OWNER`
- `ADMIN`
- `EMPLOYEE`

## Account-Onboarding und RBAC

Der geschützte Account-Erstellungsflow folgt diesem Ablauf:

```text
Session-Cookie
  → current_account
  → Rollenprüfung
  → current_account.tenant_id
  → AccountOnboardingService
  → neuer Account + einmaliges Initialpasswort
```

Die aktuell implementierte Matrix lautet:

| Handelnder Account | Darf erstellen |
| --- | --- |
| OWNER | ADMIN, EMPLOYEE |
| ADMIN | EMPLOYEE |
| EMPLOYEE | niemanden |

Ein OWNER kann über diesen Onboarding-Flow nicht erstellt werden. Die spätere OWNER-/Tenant-Registrierung ist noch nicht implementiert.

Der Client kann beim Account-POST weder `tenant_id`, `password_change_required`, Passwort-Hash noch Creator-Rolle bestimmen. Der neue Account erhält seinen Tenant ausschließlich aus `current_account.tenant_id` und `password_change_required=True`.

Die erfolgreiche Onboarding-Antwort enthält bewusst nur `account_id`, Name, E-Mail, Rolle, Passwortwechselstatus und das **einmalige** `temporary_password`. Sie enthält keinen Hash, keine Tenant-ID, keine interne UUID und keine Sessiondaten. Das normale `AccountRead` enthält niemals ein Initialpasswort.

## Passwortarchitektur

`PasswordService` kapselt Hashing, Verify und Rehash mit **Argon2id** über `argon2-cffi`:

| Einstellung | Wert |
| --- | --- |
| Memory Cost | 64 MiB |
| Time Cost | 3 |
| Parallelism | 4 |
| Salt | 16 Byte |
| Hash | 32 Byte |

Selbst gewählte Passwörter müssen mindestens 12 Zeichen besitzen und mindestens drei von vier Kategorien enthalten: Kleinbuchstaben, Großbuchstaben, Zahlen und Sonderzeichen.

Automatisch erzeugte Initialpasswörter sind exakt 12 Zeichen lang, erfüllen garantiert alle vier Kategorien und verwenden `secrets`. Die leicht verwechselbaren Zeichen `0`, `O`, `1`, `l` und `I` werden nicht verwendet. Das Klartextpasswort wird nur bei der Anlage zurückgegeben; anschließend wird ausschließlich sein Argon2id-Hash gespeichert.

## Login und Sessions

### Login

```text
POST /auth/login
```

Request:

```json
{"identifier": "AB-123456", "password": "…"}
```

- OWNER und ADMIN können sich mit Account-ID oder E-Mail anmelden.
- EMPLOYEE kann sich nur mit Account-ID anmelden.
- Client-Rolle, Client-Tenant-ID und `login_type` sind nicht Teil des Schemas.
- Ungültige Anmeldungen erhalten immer eine generische `401 Unauthorized`-Antwort; unbekannte Accounts und falsche Passwörter werden nicht unterschieden.

### Serverseitige Session

```text
Login
  → AccountAuthenticationService
  → SessionService
  → zufälliger Sessiontoken
  → SHA-256-Hash in der Datenbank
  → HttpOnly-Cookie im Browser
```

Die Session-Tabelle enthält interne UUID, `account_id`, `token_hash`, `created_at`, `expires_at` und `revoked_at`. Der Token wird mit `secrets.token_urlsafe(32)` erzeugt (256 Bit Zufallsentropie) und nur als SHA-256-Hash gespeichert. Passwörter benötigen dagegen den bewusst langsamen Argon2id-Hash, weil sie menschlich gewählt und damit viel schwächer sein können.

Cookie-Einstellungen:

| Eigenschaft | Wert |
| --- | --- |
| Name | `kreideheld_session` |
| HttpOnly | `True` |
| SameSite | `Lax` |
| Path | `/` |
| Max-Age | 8 Stunden |
| Secure | `False` bei `DEBUG=True`, sonst `True` |

Sessiontoken erscheinen weder in JSON noch in Account-Daten oder `localStorage`.

### current_account

Bei einem Folge-Request wird das Cookie nicht als Identitätsquelle vertraut:

```text
Request
  → Session-Cookie
  → Token hashen
  → gültige, nicht abgelaufene und nicht widerrufene Session laden
  → aktuellen Account aus der Datenbank laden
  → current_account
```

Rolle, Tenant und Passwortwechselstatus stammen daher aus dem aktuellen Account-Datensatz, nicht aus Cookie-Inhalt.

## Datenbankschema und Migrationen

Alembic verwaltet das Schema. Der aktuelle Head ist `20260923_04`.

| Revision | Zweck |
| --- | --- |
| `20260923_01` | historische SQLite-Baseline |
| `20260923_02` | Account-Identity- und Rollenmodell |
| `20260923_03` | verpflichtendes `password_hash` |
| `20260923_04` | serverseitige Sessions |

```powershell
cd backend
.\venv\Scripts\python.exe -m alembic current
.\venv\Scripts\python.exe -m alembic heads
.\venv\Scripts\python.exe -m alembic upgrade head
```

Normale Entwicklungsdatenbanken werden über Alembic migriert, nicht über `Base.metadata.create_all()`. `create_all()` bleibt ausschließlich Teil der isolierten In-Memory-Testumgebung.

## Tests

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest -q
```

Die Tests verwenden eine isolierte In-Memory-SQLite-Datenbank. Die lokale Entwicklungsdatenbank `backend/kreideheld.db` wird nicht verändert. Abgedeckt sind unter anderem:

- Passwortservice, Passwortpolicy und Initialpasswortgenerator
- Account-Onboarding und Authentifizierungsservice
- Session-Erzeugung, Ablauf und Widerruf
- Login, Cookie und `current_account`
- RBAC, Tenant-Injection und Response-Sicherheit bei Account-Erstellung
- erste Reststück-Routen
- Migrationen auf temporären Datenbankkopien

SQLAlchemy ORM bzw. gebundene Parameter behandeln Nutzereingaben als Daten. Beispielsweise bleibt `O'Brien; DROP TABLE accounts;` ein normaler Name; Zeichenfilter sind kein SQL-Injection-Schutz.

## Noch offen / vor Produktion erforderlich

- `GET /accounts` ist derzeit noch ungeschützt.
- `password_change_required=True` wird noch nicht global erzwungen; Passwortwechsel fehlt.
- Logout und Passwort-Reset fehlen.
- Ein vollständiger CSRF-Schutz für Cookie-basierte Zustandsänderungen fehlt.
- Rate Limiting und Login-Lockout fehlen.
- 2FA fehlt.
- OWNER-/Tenant-Registrierung fehlt.
- Tenant-Isolation muss für weitere Ressourcenrouten konsequent geprüft und erweitert werden.
- PostgreSQL-Produktionskonfiguration, Deployment und weiteres Production-Hardening fehlen.
- Frontend-Backend-Integration, Offline-Sync, Outbox, Konfliktlösung und PWA-Ausbau fehlen.

## Entwicklungsworkflow

```text
Feature Branch
  → kleine fachliche Änderung
  → Tests
  → Review
  → Alembic-Prüfung
  → Commit
  → Push
```

Aktuelle Entwicklungsarbeit erfolgt auf `feature/backend-auth`.
