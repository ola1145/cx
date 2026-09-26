# VoiceSession Interface (seam) — v0.1

**Protected seam.** After Stage 0, changes only through an owner-approved contract-diff PR.
The voice lane codes against THIS interface so implementations are **swappable and scorable**.

Nova 2 Sonic is the **primary** implementation. The harness can bench Gemini Live, OpenAI
Realtime and Grok Voice behind the same interface for the scoped A/B.

## The session carries three streams

The interface carries **audio + tool calls + transcripts** — that is what makes an
implementation both swappable (same surface) and scorable (same observable outputs).

## Operations

```
open(config: VoiceSessionConfig) -> VoiceSession
VoiceSession.sendAudio(chunk: AudioChunk) -> void
VoiceSession.onTranscript(cb: (t: Transcript) => void) -> void
VoiceSession.onToolCall(cb: (c: ToolCall) => void) -> void
VoiceSession.emitToolResult(result: ToolResult) -> void
VoiceSession.close() -> SessionSummary
```

## Types (shape only; frozen shapes populated by contract-diff PR)

- `VoiceSessionConfig`: `{ tenantId, model: "nova2-sonic"|"gemini-live"|"openai-realtime"|"grok-voice", voice? }`
- `AudioChunk`: `{ bytes, sampleRateHz, seq }`
- `Transcript`: `{ role: "user"|"agent", text, tsMs, final }`
- `ToolCall`: `{ id, name, args }`
- `ToolResult`: `{ id, ok, data?, error? }`
- `SessionSummary`: `{ durationMs, turns, evalScore? }`

## Contract rules

- Implementation is selected by `model`; the surface never changes with it (REQ-0003).
- The **model eval harness** scores each session against fixtures; scores are recorded,
  not self-reported.
- Call recordings and transcripts are **customer PII**: redacted from logs and model
  traces, never pasted into agent context.
