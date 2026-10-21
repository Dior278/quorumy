# Quorumy

Un coéquipier de réunion. Il garde le fil, cherche, repère les incohérences, et ne parle que lorsque la parole lui est donnée. S’il a quelque chose d’urgent, il lève la main.

## Démarrer

Prérequis : [uv](https://docs.astral.sh/uv/getting-started/installation/), [Bun](https://bun.sh/docs/installation) et [Node.js 24](https://nodejs.org/en/download). uv installe Python si nécessaire.

```sh
git clone https://github.com/Dior278/quorumy.git
cd quorumy
uv run --locked python scripts/project.py setup
uv run --locked quorumy
```

Le serveur écoute sur toutes les interfaces, port **8765**. Ouvrez l’adresse de la machine, par exemple http://127.0.0.1:8765/.

Créez un compte avec une [clé Hugging Face](https://huggingface.co/settings/tokens) autorisée à appeler les Inference Providers. Le modèle par défaut est `Qwen/Qwen2.5-7B-Instruct:cheapest`. Vous pouvez le remplacer par n’importe quel modèle de chat du routeur, avec `:cheapest`, `:fastest` ou `:preferred`.

La clé reste sur le serveur. Quorumy parle avec Kokoro (`hexgrad/Kokoro-82M`) et écoute avec Whisper, les deux via cette clé. La voix suit la langue de la réunion : française par défaut (`ff_siwis`).

Pour limiter l’accès à cette machine : `QUORUMY_AUTH=off uv run --locked quorumy --host 127.0.0.1`.

## Pendant la réunion

Démarrez après accord des participants. Quorumy prend des notes et peut lancer une recherche pendant que la conversation continue. Il répond quand on s’adresse à lui (« Quorumy, à toi »). Sinon il lève la main : l’icône clignote en rouge quand le point est urgent. Quelqu’un lui donne alors la parole.

Les engagements se relisent et se confirment avant l’export. Ceux qui sont confirmés reviennent à la réunion suivante. Si un chiffre ou une décision les contredit, Quorumy lève la main en rouge. Les sessions sont enregistrées sur le serveur.

## Vérifier

```sh
uv run --locked python scripts/project.py doctor
uv run --locked python scripts/project.py check
```

`doctor` vérifie la configuration ; `check` lance les tests et la compilation sans clé API.

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Contribuer](CONTRACT.md)
- [Évaluer le projet](docs/EVALUATION.md)
- [Sources et auteurs](ATTRIBUTIONS.md)
