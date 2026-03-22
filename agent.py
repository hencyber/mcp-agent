"""
Systemövervakare - AI Agent

Agent som kopplar till MCP-servern och låter användaren
ställa frågor om systemet på svenska.

Kör:
    1. Starta MCP-servern: cd ../mcp_server && python server.py
    2. Starta agenten: python agent.py
"""

import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()


# Konfiguration

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_BEARER_TOKEN = os.getenv("OLLAMA_BEARER_TOKEN")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp")

# Dessa verktyg får agenten använda (5 av 7)
# search_logs och list_top_processes exkluderas pga säkerhet
ALLOWED_TOOLS = [
    "get_cpu_usage",
    "get_memory_info",
    "get_disk_usage",
    "get_network_info",
    "get_system_uptime",
]


# Middleware - bearbetar output innan den når agenten

@wrap_tool_call
async def process_tool_output(request, handler):
    """Middleware som loggar och bearbetar verktygsoutput.
    Lägger till tidsstämpel och trunkerar lång output.
    """
    tool_name = request.tool_call.get("name", "okänt")
    tool_args = request.tool_call.get("args", {})
    timestamp = datetime.now().strftime("%H:%M:%S")

    print(f"\n--- Middleware [{timestamp}] ---")
    print(f"  Verktyg: {tool_name}")
    print(f"  Argument: {tool_args}")

    # Kör verktyget
    result = await handler(request)

    # Bearbeta output
    content = getattr(result, "content", None)
    if isinstance(content, str) and content:
        # Trunkera om det är för långt
        if len(content) > 500:
            content = content[:500] + "\n... [trunkerad]"

        # Lägg till tidsstämpel
        content = f"[Hämtad: {timestamp}]\n{content}"
        result.content = content
        print(f"  Output bearbetad ({len(content)} tecken)")

    elif isinstance(content, list) and content:
        # Ibland kommer det som en lista med TextContent-objekt
        text_parts = []
        for item in content:
            if hasattr(item, "text"):
                text_parts.append(item.text)
        if text_parts:
            merged = "\n".join(text_parts)
            if len(merged) > 500:
                merged = merged[:500] + "\n... [trunkerad]"
            result.content = f"[Hämtad: {timestamp}]\n{merged}"
            print(f"  Output bearbetad ({len(result.content)} tecken)")
        else:
            print(f"  Output vidarebefordrad")
    else:
        print(f"  Output vidarebefordrad")

    print("---\n")
    return result


# Modell

def get_model():
    """Skapa Ollama-modellen."""
    if not OLLAMA_BEARER_TOKEN:
        raise ValueError("OLLAMA_BEARER_TOKEN saknas i .env")

    return ChatOllama(
        model="llama3.1:8b",
        base_url=OLLAMA_BASE_URL,
        client_kwargs={
            "headers": {"Authorization": f"Bearer {OLLAMA_BEARER_TOKEN}"}
        },
    )


# Huvudfunktion

async def run():
    """Kör agenten."""

    print("\nSystemövervakare - AI Agent")
    print("Kopplar till MCP-server...\n")

    # Koppla till MCP-servern
    mcp_client = MultiServerMCPClient(
        {
            "system_monitor": {
                "transport": "http",
                "url": MCP_SERVER_URL,
            },
        }
    )

    # Hämta verktyg
    all_tools = await mcp_client.get_tools()

    print(f"Verktyg från MCP-servern ({len(all_tools)} st):")
    for t in all_tools:
        tillåten = "ja" if t.name in ALLOWED_TOOLS else "nej"
        print(f"  - {t.name} (tillåten: {tillåten})")

    # Filtrera - agenten ska bara ha tillgång till en del av verktygen
    filtered_tools = [t for t in all_tools if t.name in ALLOWED_TOOLS]
    print(f"\nFiltrerade verktyg: {len(filtered_tools)} st\n")

    # Skapa modell och agent
    model = get_model()

    agent = create_agent(
        model=model,
        tools=filtered_tools,
        middleware=[process_tool_output],
        system_prompt=(
            "# Roll\n"
            "Du är en systemövervakare som hjälper användaren att förstå "
            "sin dators status.\n\n"
            "# Språk\n"
            "Svara alltid på svenska.\n\n"
            "# Uppgifter\n"
            "- Visa CPU-användning med verktyget get_cpu_usage\n"
            "- Visa minnesanvändning med get_memory_info\n"
            "- Visa diskanvändning med get_disk_usage\n"
            "- Visa nätverksstatistik med get_network_info\n"
            "- Visa systemuptime med get_system_uptime\n\n"
            "# Regler\n"
            "- Använd ALLTID verktygen för att hämta data, gissa aldrig\n"
            "- Presentera resultaten tydligt med formatering\n"
            "- Ge korta kommentarer om systemets status\n\n"
            "# Svarsformat\n"
            "- Använd punktlistor och tydliga rubriker\n"
            "- Inkludera siffror och enheter\n"
            "- Håll svaren korta och informativa"
        ),
    )

    # Kör
    print("Klar! Skriv din fråga (eller 'avsluta' för att stänga)\n")

    while True:
        try:
            user_input = input("Fråga: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("avsluta", "quit", "exit", "q"):
            break

        print()

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_input}]}
        )

        # Visa svaret
        final_message = result["messages"][-1]
        if hasattr(final_message, "content"):
            print(f"\nSvar: {final_message.content}")

    print("\nAvslutar.")


if __name__ == "__main__":
    asyncio.run(run())
