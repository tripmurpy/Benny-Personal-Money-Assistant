# Project Context

**Updated:** 2026-08-13

Benny is a private Telegram bot scoped only to AI-assisted income and expense capture.

## Supported features

- Natural-language text capture.
- Receipt image extraction.
- Voice transcription and capture.
- Natural clarification and light finance conversation around capture.
- Natural-language expense reports with backend-resolved date ranges.
- User confirmation before every AI-derived write.
- Separate Supabase tables for income and expenses.
- Idempotent retry, undo, and edit after capture.
- Private access through `ADMIN_CHAT_ID`.

## Explicitly out of scope

Budgets, goals, reminders, PDF export, dashboards, coaching, RAG, general-purpose chat, and spending recommendations.

## Safety contract

- Never report success before Supabase confirms the write.
- Never replace a pending confirmation with a new input or accept a stale confirmation button.
- Show OCR text and voice transcripts before an AI-derived write.
- Reject mixed income/expense batches.
- Scope mutations by `user_id`.
- Keep secrets in environment files and never in tracked source.
