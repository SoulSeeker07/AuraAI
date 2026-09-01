"""
Evaluation of Dual Disambiguation Heuristics for Semantic Feature Detection:
1. Canonical Verb Antonym / Complement Check
2. Signature I/O Shape & Type Inversion Check
"""

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


# ── Heuristic 1: Antonym / Complement Verb Pairs ─────────────────────────────

COMPLEMENTARY_VERB_PAIRS = {
    ("load", "save"),
    ("read", "write"),
    ("serialize", "deserialize"),
    ("encode", "decode"),
    ("encrypt", "decrypt"),
    ("pack", "unpack"),
    ("import", "export"),
    ("get", "set"),
    ("start", "stop"),
    ("connect", "disconnect"),
    ("subscribe", "unsubscribe"),
    ("publish", "consume"),
    ("push", "pull"),
    ("lock", "unlock"),
    ("show", "hide"),
    ("open", "close"),
    ("mount", "unmount"),
    ("enable", "disable"),
}

# Build bidirectional lookup
ANTONYM_MAP: dict[str, str] = {}
for v1, v2 in COMPLEMENTARY_VERB_PAIRS:
    ANTONYM_MAP[v1] = v2
    ANTONYM_MAP[v2] = v1


def extract_primary_verb(func_name: str) -> str:
    """Extract leading verb from snake_case function name."""
    parts = func_name.lower().split("_")
    return parts[0] if parts else func_name.lower()


def is_antonym_pair(name_a: str, name_b: str) -> tuple[bool, str]:
    verb_a = extract_primary_verb(name_a)
    verb_b = extract_primary_verb(name_b)

    if ANTONYM_MAP.get(verb_a) == verb_b:
        return True, f"Antonym verbs: '{verb_a}' <-> '{verb_b}'"
    return False, ""


# ── Heuristic 2: Signature I/O Shape & Type Inversion ─────────────────────────

@dataclass
class SignatureShape:
    func_name: str
    param_types: list[str]
    return_type: str | None


def parse_sig_shape(sig_text: str) -> SignatureShape:
    """Extract argument types and return type using AST."""
    try:
        # Wrap in dummy body for AST parsing
        tree = ast.parse(f"{sig_text}\n    pass")
        func_def = tree.body[0]
        if not isinstance(func_def, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return SignatureShape(func_name="", param_types=[], return_type=None)

        param_types = []
        for arg in func_def.args.args:
            if arg.arg in ("self", "cls"):
                continue
            if arg.annotation:
                param_types.append(ast.unparse(arg.annotation).strip())
            else:
                param_types.append("Any")

        ret_type = ast.unparse(func_def.returns).strip() if func_def.returns else None
        return SignatureShape(func_name=func_def.name, param_types=param_types, return_type=ret_type)
    except Exception:
        name_match = re.match(r"(?:async\s+)?def\s+([a-zA-Z0-9_]+)", sig_text)
        name = name_match.group(1) if name_match else ""
        return SignatureShape(func_name=name, param_types=[], return_type=None)


def check_signature_relationship(sig_a: SignatureShape, sig_b: SignatureShape) -> str:
    """
    Classifies relationship based on I/O signature shape:
    - 'INVERTED_IO' (Input types of A match output of B, and output of A matches inputs of B, with distinct return types)
    - 'MATCHING_IO_SHAPE' (Matching return type and compatible parameter structure)
    - 'ASYMMETRIC' (Different signature shape)
    """
    params_a = set(sig_a.param_types)
    params_b = set(sig_b.param_types)
    ret_a = sig_a.return_type
    ret_b = sig_b.return_type

    # 1. Type Inversion requires different return types (e.g. dict->str vs str->dict, or Path->ndarray vs ndarray->Path)
    if ret_a and ret_b and ret_a != ret_b:
        ret_a_in_b = ret_a in params_b or any(ret_a in p for p in params_b)
        ret_b_in_a = ret_b in params_a or any(ret_b in p for p in params_a)
        if ret_a_in_b or ret_b_in_a:
            return "INVERTED_IO (Inverse / Companion Function)"

    # 2. Matching I/O shape (identical return type, matching parameter count)
    if ret_a == ret_b and len(sig_a.param_types) == len(sig_b.param_types):
        return "MATCHING_IO_SHAPE (Candidate Duplicate)"

    # 3. Soft matching if return types both exist and param count is identical
    if ret_a is not None and ret_b is not None and len(sig_a.param_types) == len(sig_b.param_types):
        return "MATCHING_IO_SHAPE (Candidate Duplicate)"

    return "ASYMMETRIC_SHAPE"


# ── Run Evaluation on All Test Pairs ─────────────────────────────────────────

def run_evaluation():
    print("=" * 80)
    print("Evaluating Disambiguation Filters: Embeddings + Verb Antonym + Signature I/O")
    print("=" * 80)

    model = SentenceTransformer("all-MiniLM-L6-v2")

    test_pairs = [
        # --- True Duplicates ---
        (
            "True Duplicate",
            (
                "def authenticate_user(username: str, token: str) -> bool:\n"
                "    \"\"\"Authenticate a user given their username and auth token.\"\"\""
            ),
            (
                "def verify_credentials(user_identifier: str, access_token: str) -> bool:\n"
                "    \"\"\"Verify user credentials using account ID and authentication token.\"\"\""
            ),
        ),
        (
            "True Duplicate",
            (
                "def save_audio(output_dir: Path, audio_data: np.ndarray, prefix: str) -> Path:\n"
                "    \"\"\"Save raw audio numpy array to a WAV file on disk.\"\"\""
            ),
            (
                "def export_wav_file(destination_folder: Path, waveform_array: np.ndarray, filename_prefix: str) -> Path:\n"
                "    \"\"\"Export audio waveform numpy array as a WAV file to disk.\"\"\""
            ),
        ),
        (
            "True Duplicate",
            (
                "def get_cyclomatic_complexity(self) -> CodeQualityMetric:\n"
                "    \"\"\"Calculate average cyclomatic complexity score per function in the codebase.\"\"\""
            ),
            (
                "def compute_code_complexity(self) -> ComplexityReport:\n"
                "    \"\"\"Compute the mean cyclomatic complexity index across functions.\"\"\""
            ),
        ),

        # --- Complementary Counterparts ---
        (
            "Complementary Counterpart",
            (
                "def load_wav(filepath: Path) -> np.ndarray:\n"
                "    \"\"\"Load a WAV audio file and return audio data as a numpy array.\"\"\""
            ),
            (
                "def save_audio(output_dir: Path, audio_data: np.ndarray, prefix: str) -> Path:\n"
                "    \"\"\"Save raw audio numpy array to a WAV file on disk.\"\"\""
            ),
        ),
        (
            "Complementary Counterpart",
            (
                "def serialize_state(state_dict: dict[str, Any]) -> str:\n"
                "    \"\"\"Serialize state dictionary into a JSON string payload.\"\"\""
            ),
            (
                "def deserialize_state(json_str: str) -> dict[str, Any]:\n"
                "    \"\"\"Parse a JSON string payload back into a state dictionary.\"\"\""
            ),
        ),

        # --- Domain Adjacent ---
        (
            "Domain-Adjacent",
            (
                "def parse_file(self, file_path: Path) -> ASTFile:\n"
                "    \"\"\"Parse Python source file into an Abstract Syntax Tree.\"\"\""
            ),
            (
                "def apply_refactoring(self, operation: RefactoringOperation) -> dict[str, Any]:\n"
                "    \"\"\"Apply AST refactoring operation across multiple source files.\"\"\""
            ),
        ),
    ]

    print(f"\nRunning 2-Stage Filter across {len(test_pairs)} test pairs:\n")

    for ground_truth, text_a, text_b in test_pairs:
        sig_line_a = text_a.split("\n")[0]
        sig_line_b = text_b.split("\n")[0]

        # Stage 1: Embedding Cosine Similarity
        emb_a = model.encode([text_a], normalize_embeddings=True)
        emb_b = model.encode([text_b], normalize_embeddings=True)
        raw_score = float(cosine_similarity(emb_a, emb_b)[0][0])

        # Stage 2: Heuristic Signals
        shape_a = parse_sig_shape(sig_line_a)
        shape_b = parse_sig_shape(sig_line_b)

        is_antonym, antonym_detail = is_antonym_pair(shape_a.func_name, shape_b.func_name)
        io_relation = check_signature_relationship(shape_a, shape_b)

        # Combined Classification
        if raw_score < 0.75:
            final_class = "UNRELATED / DOMAIN-ADJACENT (Ignored)"
        elif is_antonym or "INVERTED_IO" in io_relation:
            final_class = "COMPLEMENTARY_COMPANION (Classified as Companion, NOT Duplicate)"
        elif "MATCHING_IO_SHAPE" in io_relation:
            final_class = "HIGH_CONFIDENCE_DUPLICATE (Flagged for Review)"
        else:
            final_class = "RELATED_UTILITY (General Advisory Context)"

        print(f"GROUND TRUTH: [{ground_truth.upper()}]")
        print(f"  Func A:   {sig_line_a}")
        print(f"  Func B:   {sig_line_b}")
        print(f"  Stage 1 (Embedding Similarity): {raw_score:.4f}")
        print(f"  Stage 2 (Verb Check):          {antonym_detail if is_antonym else 'No antonym conflict'}")
        print(f"  Stage 2 (Signature I/O):       {io_relation}")
        print(f"  --> FINAL RESOLUTION:          {final_class}")
        print("-" * 80)


if __name__ == "__main__":
    run_evaluation()
