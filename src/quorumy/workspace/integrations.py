"""Outils de recherche du moteur de réunion."""

from quorumy.workspace.core.tools import ToolSpec


def register_research(registry, backend):
    available = {"web": True}
    descriptions = {
        "web": "Recherche web actuelle avec sources citées. Utiliser pour vérifier des informations externes.",
    }
    for provider in available:

        async def run(arguments, provider=provider):
            query = arguments.get("query")
            if not isinstance(query, str) or not 1 <= len(query.strip()) <= 12000:
                raise ValueError("query doit contenir entre 1 et 12 000 caractères")
            finding = await backend.research(query, "workspace", {}, provider)
            return {
                "status": "ok",
                "summary": finding.summary,
                "results": [s.model_dump(mode="json") for s in finding.sources],
            }

        registry.register(
            ToolSpec(
                name=f"research_{provider}",
                description=descriptions[provider],
                effect="read",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string", "maxLength": 12000}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
                handler=run,
            )
        )
    return available
