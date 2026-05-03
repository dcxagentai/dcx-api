"""
CONTEXT:
This file builds the shared Gemini system instruction for private DCX market-topic AI replies.
It exists so the initial topic seed response and later topic chat responses use one consistent
voice, product posture, and factual boundary.

FLOW/SYSTEM:
- WhatsApp, email, or app messages can create private market topics.
- A topic seed prompt creates the topic record and first assistant turn.
- Later topic-chat prompts append user and assistant turns to that same private topic.

CONTRACT:
  preconditions: []
  postconditions:
    - Returns one non-empty Gemini system instruction string.
  side_effects: []
  idempotent: true
  retry_safe: true
  async: false

NARRATIVE:
  WHY this exists:
    - Topic creation and topic chat are two different Gemini tasks, but they should sound like the
      same DCX AI product surface.
  WHEN TO USE it:
    - Use it for Gemini calls that write private market-topic seed or chat assistant text.
  WHEN NOT TO USE it:
    - Do not use it for contact-message collation, trade projection, translation, or public forum comments.
  WHAT CAN GO WRONG:
    - If this instruction becomes too detailed, it can crowd out the task-specific prompt.
  WHAT COMES NEXT:
    - Later versions can split product truth, safety, and market-analysis posture into versioned
      provider configuration once model orchestration grows.

TESTS:
  - test_builds_shared_market_topic_system_instruction

ERRORS: []

CODE:
"""

from __future__ import annotations


def build_dcx_gemini_market_topic_system_instruction() -> str:
    return """
- A user is asking you about this topic.
- The user is likely a trader so understands market, economic, business, trade concepts.
- Your goal is to increase their understanding and comprehension of the topic.
- Consider the topic in its broadest, deepest systemic context.
- Consider that topic and broader context in relation to the way the user has presented the topic, if any.
- Do not fear uncertainty if certainty has not yet been found or demonstrated.
- Be analytical and forensic when considering and contrasting facts and elements.
- Google Search is available in topic chats. Use it when the user's message asks for current, latest, recent, time-sensitive, or source-sensitive facts; otherwise answer from the topic context and conversation history.
- You may discuss market, legal, compliance, logistics, and risk context involving sanctions, illicit trade, fraud, prohibited materials, terrorism, organised crime, drugs, or smuggling, but never facilitate evasion, sourcing, routing, procurement, concealment, operational planning, or illegal activity.
- Refuse sexually explicit material, pornography, and any abuse, exploitation, sexualization, or manipulation of children. Redirect the conversation back to legitimate market, trade, logistics, compliance, or risk analysis where possible.
- Make no claims about DCX services, offers, products, discounts, sales, pricing
""".strip()
