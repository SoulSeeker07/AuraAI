"""
End-to-end live verification of Memory Import, Retrieval Gate, and Auto-Dream Consolidation
against a real CognitiveMemoryEngine SQLite database.
"""

import datetime as dt
import json
import tempfile
from pathlib import Path

from memory.cognitive_memory import CognitiveMemoryEngine
from memory.models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource


def main():
    print("=== LIVE E2E MEMORY INTEGRATION PROBE ===")

    with tempfile.TemporaryDirectory(prefix="aura_e2e_test_") as tmpdir:
        db_path = Path(tmpdir) / "TestMemory.db"
        print(f"[1] Initializing CognitiveMemoryEngine at: {db_path}")
        engine = CognitiveMemoryEngine(db_path=db_path)
        assert engine.count_memories() == 0
        print(f"    Initial memory count: {engine.count_memories()}")

        # 1. Create mock Claude export
        claude_export_dir = Path(tmpdir) / "claude_export"
        claude_export_dir.mkdir()
        claude_memories = [
            {"content": "User prefers dark mode in VS Code", "type": "preference", "created_at": "2026-08-01T10:00:00"},
            {"content": "Deploy procedure: run pytest then docker build", "type": "procedural", "created_at": "2026-08-02T10:00:00"},
            {"content": "My secret password is secretpassword123", "type": "secrets"},  # Should be skipped by policy
        ]
        (claude_export_dir / "memories.json").write_text(json.dumps(claude_memories), encoding="utf-8")

        print("\n[2] Testing import_from_external (Claude export)...")
        res_claude = engine.import_from_external(str(claude_export_dir), source="claude", dry_run=False)
        print(f"    Batch ID: {res_claude.batch_id}")
        print(f"    Imported: {res_claude.imported_count}, Skipped (policy): {res_claude.skipped_count}, Conflicts: {res_claude.conflict_count}")
        assert res_claude.imported_count == 2
        assert res_claude.skipped_count == 1
        assert engine.count_memories() == 2

        # 2. Add an expired working memory + duplicate preference to test consolidation
        print("\n[3] Seeding duplicate and expired records for consolidation...")
        engine.store_memory(
            MemoryItem(
                content="User prefers dark mode in VS Code",  # Exact duplicate
                type=MemoryType.PREFERENCE,
                importance=0.5,
                confidence=0.6,
            )
        )
        engine.store_memory(
            MemoryItem(
                content="Temporary clipboard snippet from 2 days ago",
                type=MemoryType.WORKING,
                importance=0.1,
                expires_at=(dt.datetime.now() - dt.timedelta(days=2)).isoformat(),
            )
        )
        print(f"    Total memories before consolidation: {engine.count_memories()}")
        all_before = engine.search_memories(include_expired=True, limit=50)
        for m in all_before:
            print(f"      [BEFORE] id={m.memory_id} type={m.type.value} conf={m.confidence} src={m.provenance.source_type} content={m.content!r}")

        # 3. Consolidation dry run
        print("\n[4] Running consolidation (dry_run=True)...")
        report_dry = engine.run_consolidation(dry_run=True)
        print(f"    Dry Run Report: scanned={report_dry.total_scanned}, deduped={report_dry.deduped_count}, pruned={report_dry.pruned_count}")
        print(f"    Deduped pairs: {report_dry.deduped_pairs}")
        print(f"    Pruned IDs: {report_dry.pruned_ids}")
        assert report_dry.deduped_count >= 1
        assert report_dry.pruned_count >= 1
        assert engine.count_memories() == 4  # Untouched

        # 4. Consolidation live run
        print("\n[5] Running consolidation (dry_run=False)...")
        report_live = engine.run_consolidation(dry_run=False)
        print(f"    Live Report: scanned={report_live.total_scanned}, deduped={report_live.deduped_count}, pruned={report_live.pruned_count}")
        print(f"    Deduped pairs: {report_live.deduped_pairs}")
        print(f"    Pruned IDs: {report_live.pruned_ids}")
        all_after = engine.search_memories(include_expired=True, limit=50)
        print(f"    Total memories after consolidation: {len(all_after)}")
        for m in all_after:
            print(f"      [AFTER] id={m.memory_id} type={m.type.value} conf={m.confidence} src={m.provenance.source_type} content={m.content!r}")

        # 5. Retrieval Gate test
        print("\n[6] Testing Retrieval Gate via engine.get_retrieval_gate()...")
        gate = engine.get_retrieval_gate(domain_prefilter_min=0.10)
        
        # Generic query -> skipped
        ctx_generic = gate.get_context("What is the speed of light in vacuum?")
        print(f"    Generic query skip: skipped={ctx_generic.retrieval_skipped}, reason='{ctx_generic.skip_reason}'")
        assert ctx_generic.retrieval_skipped is True

        # Relevant preference query -> surfaced
        ctx_pref = gate.get_context("What theme do I prefer in my editor?")
        print(f"    Pref query surfaced {len(ctx_pref.facts)} facts:")
        for f in ctx_pref.facts:
            print(f"      • {f.text} (score={f.recall_score}, conf={f.effective_confidence}, src={f.source.name})")
        assert len(ctx_pref.facts) >= 1

        # 6. Rollback test
        print(f"\n[7] Testing rollback_import for batch '{res_claude.batch_id}'...")
        deleted = engine.rollback_import(res_claude.batch_id)
        print(f"    Deleted {deleted} memories associated with batch.")
        assert deleted == 1  # Exactly 1 surviving imported record was deleted
        remaining = engine.search_memories(include_expired=True, limit=50)
        print(f"    Remaining memories after rollback: {len(remaining)}")
        for m in remaining:
            print(f"      [SURVIVING] id={m.memory_id} type={m.type.value} src={m.provenance.source_type} content={m.content!r}")
        assert len(remaining) == 2  # 1 native preference + 1 audit log record survive safely

    print("\n=== ALL E2E VERIFICATIONS SUCCEEDED CLEANLY ===")


if __name__ == "__main__":
    main()
