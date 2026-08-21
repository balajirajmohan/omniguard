# OmniGuard — the idea

## Problem

A robot fleet is controlled by signed credentials (JWTs). A credential can be
cryptographically valid — correctly signed, not expired — and still be
misused: stolen, replayed from a different controller, or used to request a
movement that's technically "in scope" but physically unsafe (e.g. into a
zone where a person is working). Most access-control systems stop checking
once the signature verifies. That's the gap.

## What OmniGuard does

Sits between every command and the robot. For every request it checks not
just "is this token real," but "does this specific request make sense" —
identity, robot ownership, destination, speed, device origin, and behavior
(replay, burst). The moment something looks like misuse rather than a
mistake, it doesn't just deny the one command: it revokes the credential,
quarantines the identity, and emergency-stops the robot if it's moving.

## Why now

- Machine identities (robots, service accounts, AI agents) already outnumber
  human identities in most environments, and most of them carry static,
  broadly-scoped, long-lived credentials — a growing blast radius that
  security teams are actively worried about going into 2026.
- Robotics specifically is under-secured relative to other software: the
  industry is described as prioritizing functionality and time-to-market
  over foundational security.
- Token theft/replay is one of the most common real-world credential attack
  patterns (phishing, exposed secrets, session hijack) — applying it to a
  robot instead of a web app makes the consequence physical, not just data
  loss.

## Competitive landscape (see chat history for full research)

- **Generic policy engines** (Cerbos, Ping Identity dynamic authorization,
  StrongDM) already do context-aware allow/deny on identity + action +
  resource. They are not robot-specific and have no concept of physical
  space, motion, or emergency stop.
- **Patents / academic frameworks** ("Managing robot resources," the Robot
  Security Framework) already describe token-gated robot command execution
  as a concept. The core mechanism (token → policy check → execute) is not
  novel.
- **Agentic JWT (A-JWT)** — recent research proposing a more sophisticated
  token for AI-agent delegation chains, more advanced than the plain JWT
  OmniGuard currently uses.
- **RAD Security** — builds physical security robots, not security *for*
  robots. Different niche, not a direct competitor.
- **"OmniGuard" as a name** is already used by several unrelated companies
  (home alarm systems, an access-control product, an emergency-response
  app). Fine for a hackathon demo; would need renaming for anything beyond
  that.

## The actual differentiation

None of the generic competitors can show a *live physical consequence* —
they don't control anything that moves. OmniGuard's demo can. The
differentiation isn't "we invented token-gated authorization" (we didn't) —
it's "we're the only one in this comparison set that ties the policy
decision to an actual moving machine, with a live digital twin, and shows
the emergency stop happening." See [feature.md](feature.md) for the
specific enhancements chosen to widen that gap further, and
[implementation.md](implementation.md) for how they get built into the
existing codebase.
