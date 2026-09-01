"""
Targeted Spike: Measuring Embedding Cosine Similarity Distributions for:
1. True Semantic Duplicates (different naming, identical intent/logic)
2. Complementary Counterparts (read vs write, serialize vs deserialize)
3. Domain-Adjacent / Same-Subsystem Functions
4. Unrelated Functions
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


def run_distribution_test():
    print("=" * 80)
    print("Evaluating all-MiniLM-L6-v2 Similarity Thresholds on True Duplicates vs Counterparts")
    print("=" * 80)

    model = SentenceTransformer("all-MiniLM-L6-v2")

    test_pairs = [
        # --- Category 1: True Semantic Duplicates (Rephrased Names, Signatures, Docstrings) ---
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

        # --- Category 2: Complementary Counterparts (Read vs Write, Pub vs Sub) ---
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

        # --- Category 3: Domain-Adjacent (Same domain, different tasks) ---
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

        # --- Category 4: Unrelated Functions ---
        (
            "Unrelated",
            (
                "def load_wav(filepath: Path) -> np.ndarray:\n"
                "    \"\"\"Load a WAV audio file and return audio data as a numpy array.\"\"\""
            ),
            (
                "def analyze_repository(self) -> CodeQualityReport:\n"
                "    \"\"\"Get a comprehensive quality report with code metrics and architectural violations.\"\"\""
            ),
        ),
    ]

    print(f"\nEvaluating {len(test_pairs)} test pairs across 4 semantic categories:\n")

    for category, text_a, text_b in test_pairs:
        emb_a = model.encode([text_a], normalize_embeddings=True)
        emb_b = model.encode([text_b], normalize_embeddings=True)
        score = float(cosine_similarity(emb_a, emb_b)[0][0])

        sig_a = text_a.split("\n")[0]
        sig_b = text_b.split("\n")[0]

        print(f"[{category.upper()}] Score: {score:.4f}")
        print(f"   A: {sig_a}")
        print(f"   B: {sig_b}")
        print("-" * 70)


if __name__ == "__main__":
    run_distribution_test()
