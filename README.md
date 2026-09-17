# Kreideheld

Kreideheld ist eine Offline-first-Anwendung für Schreinereien und Handwerksbetriebe zur Verwaltung von Restmaterialien. Ziel ist es, Reststücke mit einer Kreidenummer zu erfassen, schnell passende Lagerbestände zu finden und dabei auch ohne stabile Internetverbindung arbeiten zu können.

## Aktueller Stand

Der aktuelle Stand ist ein funktionierender Grundbau für das Projekt, aber noch kein vollständiger Produkt-Lebenszyklus. Die wichtigsten Punkte:

### Bereits umgesetzt

- Backend mit FastAPI als API-Server
- SQLAlchemy-Modelle für Tenants, Accounts, Rest-Typen und Reststücke
- CRUD-Endpunkte für Tenants, Rest-Typen und Reststücke
- Basis-Login-Flow für Tenant-Accounts
- Erste Backend-Tests für Auth und Reststück-CRUD
- Frontend-Prototyp mit Formular zur Erfassung von Reststücken im lokalen Browser
- lokale Speicherung mit localStorage statt vollständiger Offline-Sync-Schicht

### Noch nicht oder nur teilweise umgesetzt

- vollständiger Multi-Tenant-Login mit Chef- und Mitarbeiterrollen
- echte Mitarbeiter- und Tenant-Authentifizierung mit sicherem, durchgereichten Scope
- Frontend-Ansichten für Chef-Admin, Mitarbeiter und Lagerabfrage
- IndexedDB/Dexie-Offline-Speicherung
- Sync-Schicht mit Outbox und Konfliktlösung
- PWA/App-Shell für echte Offline-Erreichbarkeit
- Row-Level-Security oder andere Mandanten-Absicherungen auf Datenbankebene
- echte Produktions-Features wie Billing, Abo-Status oder Verifikation

## Produktidee

Die Anwendung soll in zwei Ebenen funktionieren:

1. Chef-Account
   - verwaltet Mandant und Richtlinien
   - legt Rest-Typen und Maße fest
   - definiert, welche Felder für welche Materialart relevant sind

2. Mitarbeiter-Account
   - kann Reststücke erfassen oder nach passenden Materialresten suchen
   - sieht nur die für den Betrieb konfigurierten Felder
   - arbeitet in der Praxis oft mobil und offline

Das Kernprinzip ist dabei: Ein Reststück bekommt eine interne Kreidenummer, die am Material selbst vermerkt wird. So kann ein Mitarbeiter das passende Teil finden, ohne das komplette Lager manuell zu durchsuchen.

## Technischer Stand

### Backend

Das Backend ist bereits als API-Server mit den wichtigsten Modulen aufgebaut:

- `app/main.py` als Einstiegspunkt
- `app/models.py` mit den zentralen Datenmodellen
- `app/routers/*.py` für Auth, Tenants, Accounts, Rest-Typen und Reststücke
- SQLAlchemy mit lokalem Entwicklungsmodell und PostgreSQL-fähiger Struktur

Die aktuellen Tests bestätigen, dass die grundlegende Auth- und CRUD-Logik in ihrer jetzigen Form lauffähig ist.

### Frontend

Das Frontend ist aktuell ein funktionaler Prototyp. Es kann Reststücke lokal im Browser erfassen, aber es ist noch kein vollständiges Produkt-Frontend mit:

- realer Tenant-Auswahl
- Mitarbeiter-Login
- Suche nach passenden Reststücken
- Datenbank-/Sync-Schicht
- Offline-Last/Push-Mechanik

## Architektur-Zielbild

Der langfristige Aufbau sieht so aus:

```
React Frontend
  ├─ lokale Speicherung (IndexedDB / Dexie)
  ├─ Outbox für ausstehende Änderungen
  └─ Sync mit FastAPI

FastAPI Backend
  ├─ Auth und Mandantenlogik
  ├─ Rest-Typen und Reststücke
  └─ API für Sync- und Query-Endpunkte

PostgreSQL
  ├─ Tenant-gebundene Daten
  ├─ sensible Datenmodelle
  └─ später mit RLS / strengerem Tenant-Scoping
```

## Aktueller Projektstatus nach Bereichen

### Fertig / stabil genug für Weiterentwicklung

- Grundstruktur des Projekts
- FastAPI-Backend und erste API-Routen
- Datenmodell für Kernobjekte
- erste Tests
- lokaler Frontend-Prototyp zur Erfassung von Reststücken

### In Arbeit / nächster Schritt

- vollständige Auth- und Rollenlogik
- saubere Tenant-Scoping-Implementierung
- weitere Frontend-Seiten und echte Bedienflüsse
- lokale Datenhaltung mit Dexie und Offline-Strategie

### Geplant / noch offen

- Sync-Endpunkte (`/sync/pull`, `/sync/push`)
- Konfliktauflösung mit Last-Write-Wins
- PWA-Setup mit Workbox
- Row-Level-Security in PostgreSQL
- Mitarbeiter-Suche nach Mindestmaßen
- Admin-Konfiguration von Rest-Typen und Maßfeldern im Frontend
- Abo- und Billing-Integration

## Entwicklungsreihenfolge

Die Reihenfolge ist bewusst so gewählt, dass die wichtigsten Grundbausteine sauber funktionieren, bevor Offline-/PWA-Komplexität hinzukommt:

1. Backend und API-Grundlagen
2. Auth und Tenant-Konzept
3. Frontend online-only, ohne Offline-Sync
4. Dexie/IndexedDB als lokale Datenquelle
5. Outbox-Sync und Konfliktlogik
6. PWA/Workbox und echte Offline-Erreichbarkeit

## Setup

### Voraussetzungen

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### PostgreSQL (falls lokal verwendet)

```bash
docker compose up -d
```

## Tests

Im Backend gibt es bereits erste Testfälle für Login und Reststück-CRUD:

```bash
cd backend
pytest -q
```

## Roadmap

- [x] Projektstruktur und Basis-Backend
- [x] Kernmodelle für Tenants, Accounts und Reststücke
- [x] erste API-Endpunkte und Tests
- [x] lokaler Frontend-Prototyp zur Erfassung von Reststücken
- [ ] vollständige Auth- und Rollenlogik
- [ ] Admin-Frontend für Rest-Typ-Konfiguration
- [ ] lokale Datenhaltung mit IndexedDB/Dexie
- [ ] Offline-Sync und Outbox
- [ ] PWA-Setup und Offline-App-Shell
- [ ] Mandanten-Absicherung mit RLS / Produktionstauglichkeit
- [ ] Billing und Betriebsverwaltung

## Kurzfazit

Das Projekt ist derzeit in der Phase eines funktionierenden Grundgerüsts: Das Backend und ein lokaler Frontend-Prototyp existieren bereits, aber die echte Produkt-Logik rund um Rollen, Offline-Synchronisation, Mandantentrennung und Produkt-Frontend ist noch offen und wird in der nächsten Entwicklungsphase umgesetzt.
