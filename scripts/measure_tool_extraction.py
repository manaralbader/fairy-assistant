"""Measures the create_custom_order validate → retry → repair loop's pass
rate, split by language and by simulator tier. Rerunnable and diffable — this
is the source of any "X% pass rate, split by language" figure that ends up in
BENCHMARKS.md or EVALUATION_REPORT.md; nothing there should ever quote a
number this script can't reproduce.

Every case here goes through the real schema (fairy.tools.schemas) and the
real bounded loop (fairy.tools.loop.run_tool_loop) — the only simulated part
is the "model" doing the extracting (fairy.llm.sim, see ADR 002). One case per
language is deliberately over the 300-character inspiration-note limit, to
prove the over-specification guard actually fires and that repair can't talk
its way around a hard schema limit — that's not a bug in the results below,
it's what makes the guard real.

    python scripts/measure_tool_extraction.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fairy.llm.interfaces import Message  # noqa: E402
from fairy.llm.sim import SimClient  # noqa: E402
from fairy.tools.loop import run_tool_loop  # noqa: E402
from fairy.tools.registry import TOOLS  # noqa: E402
from fairy.tools.session import Session  # noqa: E402
from fairy.tools.store import demo_store  # noqa: E402

_OVER_LENGTH_EN = (
    "I want the bracelet made exactly like this: start with a lavender bead, "
    "then a gold bead, then a silver bead, repeat that pattern eleven times, "
    "then switch to a seafoam green bead for exactly four beads, then two "
    "cream beads, then wrap the wire clockwise six times before the clasp, "
    "then a final lilac bead placed off-centre by two millimetres exactly."
)

_OVER_LENGTH_AR = (
    "أبغى السوار بالضبط كذا: أول حبة لافندر، بعدها حبة ذهبي، بعدها حبة فضي، "
    "كرر هذا النمط أحد عشر مرة بالضبط ولا حبة أكثر ولا أقل من هذا العدد، "
    "بعدها بدّل إلى حبة أخضر بحري لأربع حبات بالضبط لا أكثر ولا أقل، بعدها "
    "حبتين كريمي متتاليتين، بعدها لف السلك مع عقارب الساعة ست مرات كاملة قبل "
    "المشبك مباشرة، وأخيرًا حبة أرجوانية واحدة توضع خارج المركز بمقدار "
    "مليمترين بالضبط لا أكثر ولا أقل من ذلك أبدًا مهما حصل."
)

EN_CASES = [
    "I'd love a lavender and gold bracelet, keeping it small.",
    "Can you make me a necklace inspired by seafoam waves? Medium budget works.",
    "I want a big statement piece, silver and lilac, for a wedding, my number is 0555123456.",
    "Just a simple pair of cream earrings, nothing fancy, small budget please.",
    "A layered set in blush pink, like the one I saw on your page, medium budget.",
    "Something in sky blue and silver, a small bracelet.",
    "I want a statement necklace, gold and lavender, for a big event.",
    "A cream and gold bracelet please, small budget, call me at 0501112222.",
    _OVER_LENGTH_EN,
]

AR_CASES = [
    "أبغى سوار لافندر وذهبي بميزانية بسيطة.",
    "ممكن قلادة مستوحاة من الأخضر البحري بميزانية متوسطة؟",
    "أبغى قطعة فخمة فضية وأرجوانية لحفل زفاف رقمي ٠٥٥٥١٢٣٤٥٦.",
    "بس أقراط كريمي بسيطة بميزانية صغيرة.",
    "طقم من طبقات باللون الوردي متل الي شفته بصفحتكم، ميزانية متوسطة.",
    "شي بلون سماوي وفضي، سوار صغير.",
    "أبغى قلادة فخمة، ذهبي ولافندر، لمناسبة كبيرة.",
    "سوار كريمي وذهبي لو سمحت، ميزانية بسيطة، رقمي ٠٥٠١١١٢٢٢٢.",
    _OVER_LENGTH_AR,
]


def _authorized_session(phone: str = "0501234321") -> Session:
    session = Session()
    otp = session.request_otp(phone)
    session.authorize(phone, otp)
    return session


def measure(tier: str) -> dict[str, list[dict]]:
    tool_schema = [TOOLS["create_custom_order"].json_schema]
    results: dict[str, list[dict]] = {"en": [], "ar": []}
    for language, cases in (("en", EN_CASES), ("ar", AR_CASES)):
        for case in cases:
            client = SimClient(tier=tier)
            outcome = run_tool_loop(
                client,
                [Message(role="user", content=case)],
                session=_authorized_session(),
                store=demo_store(),
                tools=tool_schema,
                max_iterations=2,  # one attempt, one repair
            )
            results[language].append(
                {
                    "case": case[:60],
                    "first_pass": outcome.log[0]["outcome"] == "ok",
                    "final_pass": any(entry["outcome"] == "ok" for entry in outcome.log),
                }
            )
    return results


def summarize(results: dict[str, list[dict]]) -> str:
    lines = ["language,n,first_attempt_pass_rate,final_pass_rate_after_repair"]
    for language, rows in results.items():
        n = len(rows)
        first_rate = sum(r["first_pass"] for r in rows) / n
        final_rate = sum(r["final_pass"] for r in rows) / n
        lines.append(f"{language},{n},{first_rate:.0%},{final_rate:.0%}")
    return "\n".join(lines)


if __name__ == "__main__":
    for tier in ("commercial", "open_weight"):
        print(f"=== tier: {tier} ===")
        print(summarize(measure(tier)))
        print()
