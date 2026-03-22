# Flödesdiagram

Diagram som visar hur agenten, middleware och MCP-servern hänger ihop.

```mermaid
flowchart LR
    U[Användare]
    A[Agent<br/>LangGraph + Ollama]
    MW[Middleware<br/>wrap_tool_call]
    MCP[MCP Server<br/>FastMCP, 7 verktyg]

    U -- fråga --> A
    A -- verktygsanrop --> MW
    MW -- anrop --> MCP
    MCP -- rådata --> MW
    MW -- bearbetad data<br/>+tidsstämpel --> A
    A -- svar --> U
```

Agenten har bara tillgång till 5 av 7 verktyg.
`search_logs` och `list_top_processes` filtreras bort i agent.py.
