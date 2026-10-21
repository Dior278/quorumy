# Evaluate Quorumy

Install and start the project with the [README](../README.md). An account and a Hugging Face key are enough for the Text path.

## Test scenario

1. Start a Text session after the participants agree.
2. Type: “You will prepare the prototype. We are keeping an English interface.” Open Notes after they update.
3. Ask: “Quorumy, look up the official WebRTC documentation and name the source.” Open the answer and its references.
4. In Commitments, prepare the proposals, reread the quote, confirm an owner and a date, then download the calendar.
5. End the session and open it again: the data is kept, and capture stays stopped.

## Automated checks

```sh
uv run --locked python scripts/project.py check
uv run --locked --group browser playwright install chromium
uv run --locked --group browser python scripts/check_quorumy_browser.py
```

These checks use fictional data and do not need an API key. On Linux, add `--with-deps` to the Chromium install. The test server uses port 8878.

The [GitHub Actions results](https://github.com/Dior278/quorumy/actions) collect the tests, the build, the browser path, and archive generation.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Configuration or startup | Run `uv run --locked python scripts/project.py doctor`. |
| Interface missing or old | Run `bun run --cwd frontend build`, then restart. |
| Port in use | Use `uv run --locked quorumy --port 8766`. |
| AI unavailable | Check the keys, the credits, and model access. |
| Voice inaudible in the call | Follow the [audio guide](demo-video.md). |

## Prepare the handoff

```sh
uv run --locked python scripts/release.py
```

The archive `release/quorumy-source.zip` contains the sources and the documentation, without keys, sessions, or installed dependencies. If it already exists, choose another name with `--output release/quorumy-source-v2.zip`.

Attach the repository link, a short description, the team members, and a video of two minutes at most. Declare the [sources](../ATTRIBUTIONS.md) and the [contributions](CONTRIBUTIONS.md).
