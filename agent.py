"""
agent.py — Armenian Bank Voice AI Agent
LiveKit Agents v1.5 API (AgentSession + Agent)
════════════════════════════════════════════════
STT : Deepgram Nova-3 (Armenian)
LLM : Groq llama-3.3-70b (via livekit-plugins-groq)
TTS : ElevenLabs eleven_multilingual_v2
VAD : Silero (graceful fallback if DLL fails on Python 3.14)
"""

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
    # Single bank mentioned — return only that bank's section
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
    # Comparison or unspecified — 2000 chars per bank
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

    # Try Silero VAD — skip gracefully if onnxruntime DLL fails (Python 3.14)
    try:
        from livekit.plugins import silero
        proc.userdata["vad"] = silero.VAD.load()
        proc.userdata["has_vad"] = True
        log.info("Silero VAD loaded OK")
    except Exception as e:
        log.warning("Silero VAD unavailable (%s) — turn detection via STT endpointing", e)
        proc.userdata["vad"] = None
        proc.userdata["has_vad"] = False

# ── Armenian Bank Agent class ──────────────────────────────────────────────────
class ArmenianBankAgent(Agent):
    def __init__(self, bank_data: str) -> None:
        instructions = SYSTEM_INSTRUCTIONS.format(
            bank_data=bank_data[:8000]   # trim to stay within token limits
        )
        super().__init__(instructions=instructions)

    async def on_enter(self) -> None:
        """Speak greeting when agent enters the session."""
        await self.session.say(GREETING_HY)

# ── Entrypoint ─────────────────────────────────────────────────────────────────
async def entrypoint(ctx: JobContext):
    full_bank_data: str = ctx.proc.userdata["bank_data"]
    vad = ctx.proc.userdata.get("vad")

    await ctx.connect()

    # Build session with STT + LLM + TTS
    session = AgentSession(
        vad=vad,   # None if Silero failed — Deepgram endpointing takes over
        stt=deepgram.STT(
            model="nova-3",
            language="hy",
            smart_format=True,
            punctuate=True,
            endpointing=300,   # 300ms silence = end of turn
        ),
        llm=groq_plugin.LLM(
            model="llama-3.3-70b-versatile",
        ),
        tts=elevenlabs.TTS(
            voice_id="21m00Tcm4TlvDq8ikWAM",     # Rachel — clear neutral voice
            model="eleven_multilingual_v2",        # supports Armenian
        ),
    )

    await session.start(
        room=ctx.room,
        agent=ArmenianBankAgent(bank_data=full_bank_data),
    )

    log.info("Agent started in room: %s", ctx.room.name)

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
        )
    )