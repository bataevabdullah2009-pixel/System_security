# 02 Privacy And Biometry

## Privacy By Design

SmartGuard AI MVP must be designed so privacy rules are part of the system behavior, not optional operator habits.

## Core Rules

1. Face recognition is allowed only for people added with explicit consent.
2. Unknown people must not be automatically enrolled.
3. Unknown face embeddings must not be stored.
4. Face embeddings must never be sent to Telegram.
5. Face embeddings must never be sent to external AI APIs.
6. Biometric data must be stored separately from ordinary events.
7. Revoked consent must delete embeddings and enrollment images if they were stored.
8. Audit logs may keep technical records, but not biometric vectors.

## Required Consent Fields

Each consented person must have:

- `display_name`
- `internal_id`
- consent date
- consent expiration date or open-ended status
- object or address where consent applies
- processing purpose: site security
- actor who added the record
- consent status: `active`, `revoked`, or `expired`
- document path or paper consent reference

## Face Recognition Decision States

The future face pipeline must return only:

- `known`: matched to an active consented person above threshold.
- `unknown`: no match above threshold, without saving an embedding.
- `low_quality`: face quality is insufficient for recognition.

## Defaults For Later Phases

- `face_match_threshold = 0.65`
- `min_face_quality = 0.5`
- `event_cooldown_seconds = 60`

## Notification Language

Allowed:

- "Обнаружен знакомый человек: Иван"
- "Обнаружен неизвестный человек"
- "Обнаружен человек"

Not allowed:

- Accusations such as "вор" or "преступник".
- Claims of certainty when confidence is probabilistic.

## Phase 0 Status

Phase 0 does not implement face recognition, face enrollment, embeddings, or person management. This document defines constraints for future phases.
