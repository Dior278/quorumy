"""Quorumy : un moteur, une API, une interface."""

import argparse

from .workspace.api.app import create_app

app = create_app()


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="Quorumy, coéquipier de réunion")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Adresse d’écoute. 0.0.0.0 rend Quorumy accessible sur le réseau.",
    )
    parser.add_argument("--ssl-certfile", default=None)
    parser.add_argument("--ssl-keyfile", default=None)
    args = parser.parse_args()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        ws_max_size=131072,
        ssl_certfile=args.ssl_certfile,
        ssl_keyfile=args.ssl_keyfile,
    )


if __name__ == "__main__":
    main()
