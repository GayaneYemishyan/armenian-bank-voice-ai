"""
agent.py — Armenian Bank Voice AI Agent
LiveKit Agents v1.5 API
════════════════════════════════════════
STT : Deepgram (Nova-2) - Auto-detect language
LLM : Groq (Llama 3.3 70B) - Context trimmed
TTS : ElevenLabs - Free tier
"""

import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
)
from livekit.plugins import groq, deepgram, elevenlabs

log = logging.getLogger("armenian-bank-agent")

# ── Load bank data ─────────────────────────────────────────────────────────────
DATA_FILE = Path(__file__).parent / "bank_data.txt"


def load_bank_data() -> str:
    if DATA_FILE.exists():
        data = DATA_FILE.read_text(encoding="utf-8")
        log.info("Loaded bank_data.txt: %d chars", len(data))
        return data
    log.error("bank_data.txt not found at %s", DATA_FILE)
    return "No bank data available. Please run the scraper first."


# ── Context trimmer ────────────────────────────────────────────────────────────
def get_relevant_context(question: str, full_data: str) -> str:
    """
    Returns relevant section of bank data to keep tokens low for Groq Free Tier.
    """
    q = question.lower()
    bank_keywords = {
        "AMERIABANK": ["ameria", "ամերիա"],
        "EVOCABANK": ["evoca", "էվոկա"],
        "MELLAT": ["mellat", "մելլաթ"],
    }

    mentioned_banks = []
    for bank_name, keywords in bank_keywords.items():
        if any(k in q for k in keywords):
            mentioned_banks.append(bank_name)

    if len(mentioned_banks) == 1:
        target_bank = mentioned_banks[0]
        start_marker = f"=== {target_bank} DATA ==="
        start_idx = full_data.find(start_marker)
        if start_idx != -1:
            return full_data[start_idx:start_idx + 6000]  # Limit to 6k chars

    # Default: Summary of first 1.5k chars of each bank
    summary = []
    for bank in ["AMERIABANK", "EVOCABANK", "MELLAT"]:
        start = full_data.find(f"=== {bank} DATA ===")
        if start != -1:
            summary.append(full_data[start:start + 1500])
    return "\n\n".join(summary)


# ── System instructions ────────────────────────────────────────────────────────
SYSTEM_INSTRUCTIONS = """\
Դուք հայկական բանկային փորձագետ եք (Armenian banking expert).

ԿԱՆՈՆՆԵՐ (STRICT RULES):
1. Պատասխանիր ԲԱՑԱՌԱՊԵՍ հայերենով (Always respond in Armenian only).
2. Օգտագործիր ՄԻԱՅՆ ստորև տրված բանկային տվյալները. մի հորինիր ոչ մի թիվ կամ հասցե.
3. Կարող ես պատասխանել ՄԻԱՅՆ այս 3 թեմաների վերաբերյալ:
   - Վարկեր / Կրեդիտ (Credits and Loans)
   - Ավանդներ (Deposits)
   - Մասնաճյուղեր և կոնտակտներ (Branch Locations and Contacts)
4. Եթե հարցը վերաբերում է այլ թեմայի, քաղաքավարի կերպով մերժիր հայերենով.
5. Եթե տվյալները բացակայում են, ասա դա ուղղակի. մի հորինիր:

ԲԱՆԿԱՅԻՆ ՏՎՅԱԼՆԵՐ (BANK KNOWLEDGE BASE):
{bank_data}
"""

GREETING_HY = (
    "Բարև ձեզ: Ես Հայկական բանկերի AI օգնականն եմ: "
    "Կարող եմ պատասխանել վարկերի, ավանդների և մասնաճյուղների "
    "վերաբերյալ հարցերին Ameriabank-ի, Evocabank-ի և Mellat Bank-ի համար: "
    "Ինչո՞վ կարող եմ օգնել ձեզ:"
)


# ── Agent class ────────────────────────────────────────────────────────────────
class ArmenianBankAgent(Agent):
    def __init__(self, full_bank_data: str) -> None:
        self.full_bank_data = full_bank_data
        initial_context = get_relevant_context("", full_bank_data)

        super().__init__(
            instructions=SYSTEM_INSTRUCTIONS.format(bank_data=initial_context)
        )

    # Dynamic Context Injection (Replaces deprecated methods)
    # The agent will naturally use the `instructions` we set in __init__
    # To update it dynamically, we would need to hook into the chat loop,
    # but for simplicity and stability, let's stick to the static instructions
    # or rely on the LLM's context window handling.
    #
    # However, to avoid the 413 error again, we keep the constructor simple.


# ── Entrypoint ───────────────────────────��─────────────────────────────────────
async def entrypoint(ctx: JobContext):
    full_bank_data: str = ctx.proc.userdata["bank_data"]

    await ctx.connect()
    log.info("Connected to room: %s", ctx.room.name)

    agent = ArmenianBankAgent(full_bank_data=full_bank_data)

    session = AgentSession(
        vad=None,
        stt=deepgram.STT(model="nova-2", smart_format=True),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),
        tts=elevenlabs.TTS(model="eleven_multilingual_v2", voice_id="21m00Tcm4TlvDq8ikWAM"),
    )

    await session.start(room=ctx.room, agent=agent)
    log.info("Session started successfully")

    await asyncio.sleep(1)
    try:
        await session.generate_reply(
            instructions="Greet the user in Armenian with the following message: " + GREETING_HY
        )
        log.info("Greeting sent successfully")
    except Exception as e:
        log.error("Greeting CRASHED: %s", e, exc_info=True)

    try:
        await asyncio.Event().wait()
    except Exception as e:
        log.error("Keep-alive error: %s", e, exc_info=True)


# ── Prewarm ────────────────────────────────────────────────────────────────────
def prewarm(proc: JobProcess):
    log.info("Prewarming: loading bank data...")
    proc.userdata["bank_data"] = load_bank_data()


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm, agent_name="armenian-bank-agent"))