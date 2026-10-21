# Quorumy

A meeting companion. It keeps the thread, searches, spots inconsistencies, and speaks only when given the floor. When something is urgent, it raises a hand.

## Start

Requirements: [uv](https://docs.astral.sh/uv/getting-started/installation/), [Bun](https://bun.sh/docs/installation), and [Node.js 24](https://nodejs.org/en/download). uv installs Python if needed.

```sh
git clone https://github.com/Dior278/quorumy.git
cd quorumy
uv run --locked python scripts/project.py setup
uv run --locked quorumy
```

The server listens on every interface, port **8765**. Open the machine’s address, for example http://127.0.0.1:8765/.

Create an account with a [Hugging Face key](https://huggingface.co/settings/tokens) allowed to call Inference Providers. The default model is `Qwen/Qwen2.5-7B-Instruct:cheapest`. You can replace it with any chat model on the router, using `:cheapest`, `:fastest`, or `:preferred`.

The key stays on the server. Quorumy speaks with Kokoro (`hexgrad/Kokoro-82M`) and listens with Whisper, both through that key. The voice follows the meeting language. French is the default meeting language (`ff_siwis`).

To limit access to this machine: `QUORUMY_AUTH=off uv run --locked quorumy --host 127.0.0.1`.

## During the meeting

Start after the participants agree. Quorumy takes notes and can search while the conversation continues. It answers when addressed (“Quorumy, your turn”). Otherwise it raises a hand: the icon blinks red when the point is urgent. Someone then gives it the floor.

Commitments are reread and confirmed before export. Confirmed ones return at the next meeting. If a number or a decision contradicts them, Quorumy raises a red hand. Sessions are stored on the server.

## Check

```sh
uv run --locked python scripts/project.py doctor
uv run --locked python scripts/project.py check
```

`doctor` checks the configuration; `check` runs the tests and the build without an API key.

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Contributing](CONTRACT.md)
- [Evaluate the project](docs/EVALUATION.md)
- [Sources and authors](ATTRIBUTIONS.md)
