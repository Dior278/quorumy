# Contribuer à Quorumy

Suivre le [README](README.md) pour installer et lancer le projet.

## Règles de développement

- Garder une application et un moteur de session uniques.
- Séparer interface, transport, orchestration, fournisseurs et stockage.
- Gérer les dépendances avec uv et Bun ; mettre à jour leurs fichiers de verrouillage.
- Demander l’accord avant la capture. Une pause doit arrêter l’écoute et les travaux.
- Garder les citations consultables et faire valider les engagements avant export.
- Afficher les erreurs des fournisseurs ; réserver les réponses fictives aux tests.
- Préserver les sessions existantes et couvrir les corrections fonctionnelles par des tests.
- Garder les clés et les données de réunion hors de Git, du frontend et des journaux.
- Créditer le code et les ressources réutilisés dans [ATTRIBUTIONS.md](ATTRIBUTIONS.md).

## Avant un push

```sh
uv run --locked python scripts/project.py check
```

Si les messages de l’API changent, régénérer le contrat avant ce contrôle :

```sh
uv run --locked python scripts/export_workspace_protocol.py
bun run --cwd frontend generate:protocol
```

Pour travailler sur l’interface, lancer le backend puis `bun run --cwd frontend dev`. Le frontend est accessible sur http://127.0.0.1:5173/.
