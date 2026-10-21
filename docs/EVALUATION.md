# Évaluer Quorumy

Installer et démarrer le projet avec le [README](../README.md). Un compte et une clé Hugging Face suffisent pour le parcours en mode Texte.

## Scénario de test

1. Démarrer une session Texte après accord des participants.
2. Saisir : « Renard préparera le prototype. Nous retenons une interface en français. » Consulter les Notes après leur actualisation.
3. Demander : « Quorumy, recherche la documentation officielle de WebRTC et indique la source. » Consulter la réponse et ses références.
4. Dans Engagements, préparer les propositions, relire la citation, confirmer un responsable et une date, puis télécharger le calendrier.
5. Terminer et rouvrir la session : les données sont conservées, la capture reste arrêtée.

## Contrôles automatiques

```sh
uv run --locked python scripts/project.py check
uv run --locked --group browser playwright install chromium
uv run --locked --group browser python scripts/check_quorumy_browser.py
```

Ces contrôles utilisent des données fictives et ne nécessitent pas de clé API. Sous Linux, ajouter `--with-deps` à l’installation de Chromium. Le serveur de test utilise le port 8878.

Les [résultats GitHub Actions](https://github.com/Dior278/quorumy/actions) regroupent les tests, la compilation, le parcours navigateur et la génération de l’archive.

## Dépannage

| Problème | Action |
| --- | --- |
| Configuration ou démarrage | Lancer `uv run --locked python scripts/project.py doctor`. |
| Interface absente ou ancienne | Exécuter `bun run --cwd frontend build`, puis redémarrer. |
| Port occupé | Utiliser `uv run --locked quorumy --port 8766`. |
| IA indisponible | Vérifier les clés, les crédits et l’accès aux modèles. |
| Voix inaudible dans l’appel | Suivre le [guide audio](demo-video.md). |

## Préparer la remise

```sh
uv run --locked python scripts/release.py
```

L’archive `release/quorumy-source.zip` contient les sources et la documentation, sans clés, sessions ni dépendances installées. Si elle existe déjà, choisir un autre nom avec `--output release/quorumy-source-v2.zip`.

Joindre le lien du dépôt, une description courte, les membres de l’équipe et une vidéo de deux minutes maximum. Déclarer les [sources](../ATTRIBUTIONS.md) et les [contributions](CONTRIBUTIONS.md).
