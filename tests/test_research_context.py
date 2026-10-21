import httpx

from quorumy.providers import LiveBackend
from quorumy.settings import AppSettings


def test_web_searches_the_latest_human_wording():
    async def scenario():
        seen: list[str] = []

        def respond(request):
            seen.append(request.content.decode())
            return httpx.Response(
                200,
                text=(
                    '<a class="result__a" href="https://example.org/doc">Document</a>'
                    '<td class="result__snippet">Le document ABC est décrit ici.</td>'
                ),
            )

        backend = LiveBackend(
            AppSettings(_env_file=None),
            httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        )
        try:
            finding = await backend.research(
                "Ce document suffit-il ?",
                "Projet",
                {},
                "web",
                history=[
                    {
                        "role": "human",
                        "text": "Correction : ABC désigne mon document.",
                    }
                ],
            )
        finally:
            await backend.close()
        assert "ABC" in seen[0]
        assert finding.sources[0].url == "https://example.org/doc"
