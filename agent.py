"""
agent.py — Armenian Bank Voice AI Agent
LiveKit Agents v1.5 API
════════════════════════════════════════
STT : Deepgram Nova-3 (Armenian)
LLM : Groq llama-3.3-70b (via livekit-plugins-groq)
TTS : ElevenLabs eleven_multilingual_v2
"""

import asyncio
import logging
import os
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
)
from livekit.plugins import deepgram, elevenlabs
from livekit.plugins import groq as groq_plugin

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

# ── Context trimmer — keeps tokens under Groq free limit ──────────────────────
def get_relevant_context(question: str, full_data: str) -> str:
    q = question.lower()
    bank_keywords = {
        "AMERIABANK": ["ameria", "ամերիա"],
        "EVOCABANK":  ["evoca", "էվոկա"],
        "MELLAT":     ["mellat", "մելլաթ"],
    }
    mentioned = [
        b for b, kws in bank_keywords.items()
        if any(k in q for k in kws)
    ]
    if len(mentioned) == 1:
        lines = full_data.split("\n")
        capture, section = False, []
        for line in lines:
            if mentioned[0] in line.upper() and "===" in line:
                capture = True
            elif "===" in line and capture and section:
                break
            if capture:
                section.append(line)
        if section:
            return "\n".join(section)[:5000]
    parts = []
    for bank in ["AMERIABANK", "EVOCABANK", "MELLAT"]:
        idx = full_data.upper().find(bank)
        if idx != -1:
            parts.append(full_data[idx:idx + 2000])
    return "\n\n---\n\n".join(parts)

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
6. Կարճ, հստակ նախադասություններ. սա ձայնային ինտերֆեյս է:

ԲԱՆԿԱՅԻՆ ՏՎՅԱԼՆԵՐ (BANK KNOWLEDGE BASE):
{bank_data}

END OF KNOWLEDGE BASE"""

GREETING_HY = (
    "Բարև ձեզ: Ես Հայկական բանկերի AI օգնականն եմ: "
    "Կարող եմ պատասխանել վարկերի, ավանդների և մասնաճյուղների "
    "վերաբերյալ հարցերին Ameriabank-ի, Evocabank-ի և Mellat Bank-ի համար: "
    "Ինչո՞վ կարող եմ օգնել ձեզ:"
)

# ── Prewarm ────────────────────────────────────────────────────────────────────
def prewarm(proc: JobProcess):
    log.info("Prewarming: loading bank data...")
    proc.userdata["bank_data"] = load_bank_data()

    try:
        from livekit.plugins import silero
        proc.userdata["vad"] = silero.VAD.load()
        log.info("Silero VAD loaded OK")
    except Exception as e:
        log.warning("Silero VAD unavailable (%s) — using Deepgram endpointing", e)
        proc.userdata["vad"] = None

# ── Agent class ────────────────────────────────────────────────────────────────
class ArmenianBankAgent(Agent):
    def __init__(self, bank_data: str) -> None:
        instructions = SYSTEM_INSTRUCTIONS.format(
            bank_data=bank_data[:8000]
        )
        super().__init__(instructions=instructions)

# ── Entrypoint ─────────────────────────────────────────────────────────────────
async def entrypoint(ctx: JobContext):
    full_bank_data: str = ctx.proc.userdata["bank_data"]
    vad = ctx.proc.userdata.get("vad")

    await ctx.connect()
    log.info("Connected to room: %s", ctx.room.name)

    session = AgentSession(
        vad=vad,
        stt=deepgram.STT(
            model="nova-3",
            language="hy",
            smart_format=True,
            punctuate=True,
            endpointing_ms=300,
        ),
        llm=groq_plugin.LLM(
            model="llama-3.3-70b-versatile",
        ),
        tts=elevenlabs.TTS(
            voice_id="21m00Tcm4TlvDq8ikWAM",
            model="eleven_multilingual_v2",
        ),
    )

    try:
        await session.start(
            room=ctx.room,
            agent=ArmenianBankAgent(bank_data=full_bank_data),
        )
        log.info("Session started successfully")
    except Exception as e:
        log.error("Session start failed: %s", e)
        return

        # Wait for session to be fully ready then generate greeting
    await asyncio.sleep(2)

    try:
        await session.generate_reply(
            instructions="Greet the user in Armenian with the following message: " + GREETING_HY
        )
        log.info("Greeting sent successfully")
    except Exception as e:
        log.error("Greeting CRASHED: %s", e, exc_info=True)

    log.info("Reached keep-alive")
    try:
        await asyncio.Event().wait()
    except Exception as e:
        log.error("Keep-alive error: %s", e, exc_info=True)

# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name="armenian-bank-agent",
        )
    )