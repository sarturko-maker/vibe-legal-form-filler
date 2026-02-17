# Roadmap: Vibe Legal Form Filler

## Milestones

- v1.0 Cross-Platform Transport -- Phases 1-4 (shipped 2026-02-17)
- v2.0 Performance Optimization -- Phases 5-6 (shipped 2026-02-17)
- v2.1 Gemini Consolidation -- Phases 8-11 (shipped 2026-02-17)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, ...): Planned milestone work
- Decimal phases (5.1, 5.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>v1.0 Cross-Platform Transport (Phases 1-4) -- SHIPPED 2026-02-17</summary>

- [x] **Phase 1: Transport Setup** - Add HTTP transport mode via --http flag, preserve stdio
- [x] **Phase 2: Protocol Implementation** - Add MCP HTTP protocol compliance (headers, errors, version negotiation)
- [x] **Phase 3: HTTP Integration Testing** - Comprehensive HTTP transport test suite with real server startup
- [x] **Phase 4: Cross-Platform Verification** - Verify compatibility with Gemini CLI and Antigravity, document setup

</details>

<details>
<summary>v2.0 Performance Optimization (Phases 5-6) -- SHIPPED 2026-02-17</summary>

- [x] **Phase 5: Fast Path Foundation** - Add answer_text field, formatting extraction function, validation, backward compatibility
- [x] **Phase 6: Fast Path Implementation** - Server builds insertion OOXML inline during write_answers for all insertion modes

</details>

<details>
<summary>v2.1 Gemini Consolidation (Phases 8-11) -- SHIPPED 2026-02-17</summary>

- [x] **Phase 8: Resolution Infrastructure** - pair_id→xpath resolution via re-extraction for write_answers, cross-check validation (completed 2026-02-17)
- [x] **Phase 9: Ergonomics & Tolerance** - file_path echo, improved error messages, SKIP convention, mode defaults (completed 2026-02-17)
- [x] **Phase 10: Verification Parity** - verify_output accepts pair_id without xpath, cross-check logic (completed 2026-02-17)
- [x] **Phase 11: Documentation & QA** - CLAUDE.md pipeline updates, test coverage, regression validation (completed 2026-02-17)

</details>

## Progress

**Execution Order:**
- v1.0: Phases 1 → 2 → 3 → 4 (complete)
- v2.0: Phases 5 → 6 (complete)
- v2.1: Phases 8 → 9 → 10 → 11 (complete)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Transport Setup | v1.0 | 1/1 | Complete | 2026-02-17 |
| 2. Protocol Implementation | v1.0 | 1/1 | Complete | 2026-02-16 |
| 3. HTTP Integration Testing | v1.0 | 2/2 | Complete | 2026-02-16 |
| 4. Cross-Platform Verification | v1.0 | 2/2 | Complete | 2026-02-17 |
| 5. Fast Path Foundation | v2.0 | 2/2 | Complete | 2026-02-17 |
| 6. Fast Path Implementation | v2.0 | 1/1 | Complete | 2026-02-17 |
| 8. Resolution Infrastructure | v2.1 | 2/2 | Complete | 2026-02-17 |
| 9. Ergonomics & Tolerance | v2.1 | 1/1 | Complete | 2026-02-17 |
| 10. Verification Parity | v2.1 | 1/1 | Complete | 2026-02-17 |
| 11. Documentation & QA | v2.1 | 1/1 | Complete | 2026-02-17 |
