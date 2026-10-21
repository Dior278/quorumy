"""Regenerate the frontend contract without starting providers or reading secrets."""

import json
from pathlib import Path

from fastapi import FastAPI

from quorumy.workspace.api.schemas import BootstrapResponse, ProtocolDocument

app = FastAPI()


@app.get("/v1/bootstrap", response_model=BootstrapResponse)
def bootstrap():
    pass


@app.get("/v1/protocol", response_model=ProtocolDocument)
def protocol():
    pass


if __name__ == "__main__":
    Path("frontend/openapi.json").write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
