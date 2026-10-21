# Architecture

Quorumy utilise un frontend React, un serveur FastAPI et un moteur d’agents. Le serveur sert aussi l’interface compilée.

```mermaid
flowchart TD
  UI[React : texte et audio] <-->|HTTP et WebSocket| API[FastAPI]
  API <--> Engine[WorkspaceEngine]
  Engine --> Agents[Réponses, recherches, notes et tableau]
  Agents <--> Services[Modèles IA et outils externes]
  Engine <--> DB[(SQLite)]
  Engine --> Actions[Engagements et exports]
```

## Organisation du code

| Dossier ou fichier | Rôle |
| --- | --- |
| `frontend/src/` | Interface, capture audio, lecture vocale et connexion au serveur |
| `src/quorumy/workspace/api/` | Routes HTTP, messages WebSocket et contrôle d’accès |
| `src/quorumy/workspace/runtime.py` | Consentement, sessions et engagements |
| `src/quorumy/workspace/core/` | Orchestration, réponses, recherches, notes et tableau |
| `src/quorumy/workspace/adapters/` | Voix, routage, connecteurs et stockage SQLite |
| `src/quorumy/workspace/integrations.py` | Enregistrement des outils de recherche |
| `src/quorumy/providers.py` | Recherche web |
| `src/quorumy/minutes.py` | Citations, validation des actions et exports |
| `tests/`, `scripts/` | Tests, installation, diagnostics et préparation de la remise |

## Déroulement d’un échange

1. L’utilisateur démarre une session avec accord des participants. Le texte saisi ou transcrit rejoint la conversation.
2. Le moteur détermine s’il faut mémoriser, répondre ou lancer une recherche. Les recherches peuvent avancer pendant que la conversation continue.
3. Les résultats alimentent les réponses, les notes et le tableau. La voix est diffusée progressivement et peut être interrompue.
4. Les engagements proposés citent les échanges d’origine. L’utilisateur confirme le responsable et la date avant l’export calendrier. Les engagements confirmés reviennent à la réunion suivante. Un chiffre ou une décision qui les contredit lève la main rouge, même si le modèle ne répond pas.
5. La pause arrête la capture et annule les travaux. Une session rouverte ou reconnectée reste en pause jusqu’à confirmation.

`WorkspaceEngine` étend le moteur Quorumy. Le modèle Hugging Face du compte route les tours, rédige et résume. Whisper transcrit et Kokoro parle, avec la même clé. La recherche web n’exige pas d’autre clé.

Le navigateur surveille séparément le microphone et l’onglet de réunion. Quorumy ne parle que si la parole lui est donnée. Sinon il lève la main, en rouge lorsqu’un point est urgent.

## Mémoire et configuration

- L’état actif contient la transcription, les notes, les cartes et les tâches.
- `.data/quorumy.sqlite3` conserve les sessions et leur journal. L’audio brut n’y est pas enregistré.
- Chaque agent reçoit le contexte utile à son rôle. Le stockage local n’est pas chiffré et ce contexte est transmis aux fournisseurs sollicités.
- `.data/config.json` règle les modèles et les fournisseurs. Les clés restent dans l’environnement, `.env` ou `.Secrets`.
- `QUORUMY_DATABASE_PATH` permet de déplacer la base. Pour une sauvegarde manuelle, arrêter le serveur avant de la copier.

## Contrat et accès

Le serveur écoute sur `127.0.0.1:8765`. Une session active et un onglet de contrôle sont autorisés par serveur. Les messages sont définis dans `workspace/api/schemas.py`, puis exportés en OpenAPI et TypeScript.

Dans un appel externe, Quorumy capture l’audio de la réunion ; la réunion doit partager l’onglet Quorumy avec son audio pour diffuser ses réponses. Voir le [guide audio](docs/demo-video.md).
