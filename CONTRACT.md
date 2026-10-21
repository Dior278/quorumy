# Contributing to Quorumy

Follow the [README](README.md) to install and run the project.

## Development rules

- Keep a single application and a single session engine.
- Separate interface, transport, orchestration, providers, and storage.
- Manage dependencies with uv and Bun; update their lockfiles.
- Ask for agreement before capture. A pause must stop listening and work.
- Keep quotes available and have commitments confirmed before export.
- Show provider errors; reserve fake replies for tests.
- Preserve existing sessions and cover functional fixes with tests.
- Keep keys and meeting data out of Git, the frontend, and logs.
- Credit reused code and assets in [ATTRIBUTIONS.md](ATTRIBUTIONS.md).

## Before a push

```sh
uv run --locked python scripts/project.py check
```

If API messages change, regenerate the contract before that check:

```sh
uv run --locked python scripts/export_workspace_protocol.py
bun run --cwd frontend generate:protocol
```

To work on the interface, start the backend, then `bun run --cwd frontend dev`. The frontend is available at http://127.0.0.1:5173/.
