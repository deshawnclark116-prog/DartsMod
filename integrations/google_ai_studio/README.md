# DartsMod × Google AI Studio (Gemini)

Connect the DartsMod prediction engine to Gemini so you can ask, in plain English,
"Who wins Humphries vs MVG in a World Championship final?" and Gemini answers using
a live Monte Carlo simulation.

## How it fits together

```
You (chat)  ─►  Gemini  ─►  decides to call `simulate_darts_match(args)`
                                        │
                          your code executes the call
                                        ▼
                            POST /simulate  ─►  DartsMod API
                                        │
                          result handed back to Gemini
                                        ▼
Gemini  ─►  natural-language answer with the probabilities
```

> **Important:** Gemini (in AI Studio or via the API) does **not** call your HTTP
> server itself. It emits a *function call* — a name plus arguments — and your
> code runs the actual request to the DartsMod API. The `gemini_client.py` script
> here does exactly that for you.

## Option A — Run it with the Gemini SDK (recommended)

This is the real integration and takes ~2 minutes.

1. **Get a key:** https://aistudio.google.com → *Get API key*.
2. **Start the DartsMod API** (see the main README to deploy a public URL):
   ```bash
   uvicorn dartsmod.api:api --port 8000
   ```
3. **Install and run the client:**
   ```bash
   pip install -r integrations/google_ai_studio/requirements.txt
   export GEMINI_API_KEY="your-key"
   export DARTSMOD_API_URL="http://localhost:8000"   # or your deployed URL
   python integrations/google_ai_studio/gemini_client.py
   ```

Gemini will call `simulate_darts_match`, the script runs the simulation via the
API, and Gemini replies with the winner, odds and likely scoreline. Point it at
any matchup by editing the `prompt` in `gemini_client.py` (or wrap `main()` in
your own chat loop).

The SDK builds the tool declaration automatically from the function's signature
and docstring — no JSON to maintain.

## Option B — The AI Studio web playground

Use this to *see* Gemini choose the tool, though you execute the call yourself.

1. Open https://aistudio.google.com and start a new chat prompt.
2. In the right-hand panel, enable **Tools → Function calling** and add a new
   function, pasting the contents of [`function_declaration.json`](./function_declaration.json).
3. Ask a darts question. Gemini responds with a **function call** (the name and
   arguments) instead of a final answer.
4. Run that call against your API and give the result back:
   ```bash
   curl -X POST "$DARTSMOD_API_URL/simulate" -H 'content-type: application/json' -d '{
     "player_1": {"name": "Luke Humphries", "scoring_average": 102.5, "double_prob": 0.42},
     "player_2": {"name": "Michael van Gerwen", "scoring_average": 99.8, "double_prob": 0.40},
     "format": "world_championship_final", "sims": 20000
   }'
   ```
   Paste the JSON back as the function response; Gemini then writes the final answer.
5. When you're happy, click **Get code** in AI Studio to export the SDK version —
   which is essentially Option A.

## Files

| File                        | Purpose                                                        |
|-----------------------------|----------------------------------------------------------------|
| `gemini_client.py`          | Runnable Gemini ↔ DartsMod bridge (automatic function calling) |
| `function_declaration.json` | Tool schema to paste into the AI Studio playground             |
| `requirements.txt`          | `google-genai` + `requests`                                    |

## Notes

- The tool exposes flat, scalar parameters (player names, averages, double
  probabilities, format) because that is what Gemini's function calling handles
  most reliably. The client maps them onto the API's structured request body.
- If the user doesn't give a stat, sensible defaults apply (98 average, 0.40
  doubles), and Gemini is told this in the parameter descriptions.
- Swap the model with `export GEMINI_MODEL=gemini-2.5-pro` for stronger reasoning.
