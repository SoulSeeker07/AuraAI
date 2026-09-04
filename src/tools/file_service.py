"""
File Service - Intelligent File Search and Launcher for AuraAI.

Discovers, matches, and opens user files (resumes, documents, downloads, notes, etc.)
across common user directories and workspaces.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Project root path
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class FileService:
    """
    Intelligent file search and launcher service.
    
    Searches user document folders, downloads, desktop, project workspaces,
    and custom directories to locate and open matching files.
    """

    _instance: FileService | None = None

    # Priority extensions for document and file search
    PRIORITY_EXTENSIONS = (
        ".pdf", ".docx", ".doc", ".txt", ".md", ".rtf",
        ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".json",
        ".html", ".png", ".jpg", ".jpeg", ".py", ".zip"
    )

    def __init__(self, search_paths: list[Path | str] | None = None):
        """Initialize FileService with standard search paths."""
        self.custom_paths: list[Path] = [Path(p) for p in (search_paths or []) if Path(p).exists()]
        self._cached_search_roots: list[Path] | None = None

    @classmethod
    def get_instance(cls) -> FileService:
        """Singleton accessor for FileService."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_known_user_aliases(self) -> list[str]:
        """Return known username tokens for Sreekanta / user."""
        aliases = {"sreekanta", "sree", "yrsre"}
        try:
            from Memory import Memory
            mem = Memory()
            stored = mem.fact_value("profile", "name") or mem.fact_value("person", "name")
            if stored:
                aliases.add(stored.lower())
                for part in stored.lower().split():
                    if len(part) > 2:
                        aliases.add(part)
        except Exception:
            pass
        return list(aliases)

    def get_search_roots(self) -> list[Path]:
        """Return unique existing search directories in priority order."""
        if self._cached_search_roots is not None:
            return self._cached_search_roots

        roots: list[Path] = []
        home = Path.home()

        # 0. Current workspace project root & cwd
        if _PROJECT_ROOT.exists() and _PROJECT_ROOT not in roots:
            roots.append(_PROJECT_ROOT)
        try:
            cwd = Path.cwd().resolve()
            if cwd.exists() and cwd not in roots:
                roots.append(cwd)
        except Exception:
            pass

        # 1. User primary personal drive paths on Windows
        for dev_path_str in ("D:/Sreekanta", "D:/Sreekanta/Documents", "D:/Sreekanta/Downloads", "D:/Sreekanta/Desktop", "D:/Documents", "D:/Downloads"):
            p = Path(dev_path_str)
            if p.exists() and p not in roots:
                roots.append(p)

        # 2. Standard user profile document directories (specific folders only)
        for sub in ("Documents", "Downloads", "Desktop", "Saved Games"):
            p = home / sub
            if p.exists() and p not in roots:
                roots.append(p)

        # 3. Workspace document directories
        for gen_dir in ("Generated_Documents", "docs", "notes", "training"):
            p = _PROJECT_ROOT / gen_dir
            if p.exists() and p not in roots:
                roots.append(p)

        # 4. OneDrive document directories
        onedrive_env = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer") or os.environ.get("OneDriveCommercial")
        if onedrive_env:
            od_path = Path(onedrive_env)
            for sub in ("Documents", "Desktop", "Attachments"):
                p = od_path / sub
                if p.exists() and p not in roots:
                    roots.append(p)

        # 5. User custom paths
        for cp in self.custom_paths:
            if cp.exists() and cp not in roots:
                roots.append(cp)

        self._cached_search_roots = roots
        return roots

    def normalize_query(self, query: str) -> tuple[str, list[str], bool, str | None]:
        """
        Normalize query string and return cleaned stem, token list, is_self flag, and explicit extension.
        
        Example: 'open this agent.md' -> ('agent', ['agent'], False, '.md')
        """
        raw = query.strip()
        is_self_query = bool(re.search(r"\b(my|i|me|mine|myself|worked|company|experience)\b", raw, re.IGNORECASE))
        
        # Check for explicit file extension
        explicit_ext: str | None = None
        for ext in self.PRIORITY_EXTENSIONS:
            pattern = re.escape(ext) + r"(\b|$)"
            if re.search(pattern, raw, re.IGNORECASE):
                explicit_ext = ext.lower()
                break

        # Strip common action and demonstrative noise words
        noise_pattern = r"\b(open|find|launch|show|get|view|display|my|the|a|an|this|that|these|those|current|here|selected|file|document|doc|which|what|where|are|is|in)\b"
        cleaned = re.sub(noise_pattern, " ", raw, flags=re.IGNORECASE)
        if explicit_ext:
            cleaned = re.sub(re.escape(explicit_ext) + r"(\b|$)", " ", cleaned, flags=re.IGNORECASE)
        cleaned = " ".join(cleaned.split()).strip()
        if not cleaned:
            cleaned = raw.strip()
            if explicit_ext:
                cleaned = re.sub(re.escape(explicit_ext) + r"(\b|$)", " ", cleaned, flags=re.IGNORECASE).strip()

        # Split tokens on spaces, underscores, and hyphens (ignoring bare extension names)
        tokens = [
            t.lower() for t in re.split(r"[\s_\-\.]+", cleaned)
            if t and t.lower() not in ("md", "txt", "pdf", "docx", "doc", "py", "json", "csv", "xlsx", "pptx", "html", "png", "jpg")
        ]
        stem = cleaned.lower()
        return stem, tokens, is_self_query, explicit_ext

    def _score_file(
        self,
        file_path: Path,
        query_stem: str,
        query_tokens: list[str],
        is_self_query: bool = False,
        explicit_ext: str | None = None,
    ) -> float:
        """Calculate a relevance match score between 0.0 and 1.0 for a candidate file."""
        import difflib

        name_lower = file_path.name.lower().strip()
        stem_lower = file_path.stem.lower().strip()
        ext_lower = file_path.suffix.lower().strip()
        path_str_lower = str(file_path).lower()

        query_trimmed = query_stem.strip()

        # 1. Exact match on filename or stem
        if stem_lower == query_trimmed or name_lower == query_trimmed:
            return 1.0
        if explicit_ext and name_lower == f"{query_trimmed}{explicit_ext}":
            return 1.0

        # 2. Match with underscores or spaces normalized
        stem_norm = stem_lower.replace("_", " ").replace("-", " ").strip()
        query_norm = query_trimmed.replace("_", " ").replace("-", " ").strip()
        if stem_norm == query_norm:
            return 0.98

        # 3. Singular / plural stem matching (e.g. "agent" vs "agents", "doc" vs "docs")
        if stem_norm.rstrip("s") == query_norm.rstrip("s") and len(query_norm.rstrip("s")) >= 3:
            ext_bonus = 0.02 if (explicit_ext and ext_lower == explicit_ext) else 0.0
            return min(0.98, 0.96 + ext_bonus)

        # 4. Query stem is complete substring in filename stem
        if query_trimmed and len(query_trimmed) >= 3:
            if query_trimmed in stem_lower:
                len_diff = abs(len(stem_lower) - len(query_trimmed))
                base = 0.95 if len_diff <= 2 else 0.90
                ext_bonus = 0.03 if (explicit_ext and ext_lower == explicit_ext) else 0.0
                return min(0.98, base + ext_bonus)
            if query_norm in stem_norm:
                return 0.90

        # 5. Fuzzy stem similarity for typos (e.g. "importent" -> "important", "agent" -> "agents")
        fuzzy_stem_ratio = difflib.SequenceMatcher(None, query_norm, stem_norm).ratio()
        if fuzzy_stem_ratio >= 0.78:
            ext_boost = 0.06 if (explicit_ext and ext_lower == explicit_ext) or (ext_lower in self.PRIORITY_EXTENSIONS) else 0.0
            drive_boost = 0.05 if ("d:\\sreekanta" in path_str_lower or "auraai" in path_str_lower) else 0.0
            return min(0.98, max(0.65, fuzzy_stem_ratio * 0.9 + ext_boost + drive_boost))

        # 6. Token matching with User Identity Awareness and Fuzzy Token Matching
        user_aliases = self.get_known_user_aliases()
        is_user_doc = any(alias in stem_lower or alias in path_str_lower for alias in user_aliases)

        if query_tokens:
            stem_tokens = set(re.split(r"[\s_\-\.]+", stem_lower))
            matched_tokens = []
            for qt in query_tokens:
                if (
                    qt in stem_tokens
                    or any(qt.rstrip("s") == st.rstrip("s") for st in stem_tokens)
                    or any(qt == st or (len(qt) >= 4 and len(st) >= 4 and qt in st) for st in stem_tokens)
                ):
                    matched_tokens.append(qt)
                elif any(len(qt) >= 4 and len(st) >= 4 and difflib.SequenceMatcher(None, qt, st).ratio() >= 0.80 for st in stem_tokens):
                    matched_tokens.append(qt)

            token_ratio = len(matched_tokens) / len(query_tokens)

            # Special boost if key words like 'resume' or 'cv' match
            has_resume_query = any(t in ("resume", "cv", "bio") for t in query_tokens)
            has_resume_stem = any(w in stem_lower for w in ("resume", "cv", "bio"))

            if has_resume_query and has_resume_stem:
                token_ratio = max(token_ratio, 0.70)
                
                # If the user asks about "my resume", strongly prioritize files with Sreekanta's name
                if is_self_query or not any(t in stem_lower for t in ("mohammed", "khan", "john", "alex")):
                    if is_user_doc:
                        token_ratio += 0.25
                    elif any(other in stem_lower for other in ("mohammed", "khan", "john", "alex")):
                        token_ratio -= 0.35

                # Boost if user name is explicitly in stem
                if any(alias in stem_lower for alias in user_aliases):
                    token_ratio += 0.15

            # Extension boost
            if explicit_ext and ext_lower == explicit_ext:
                ext_boost = 0.15
            elif ext_lower in self.PRIORITY_EXTENSIONS:
                ext_boost = 0.05
            else:
                ext_boost = 0.0

            # Drive path boost for primary user drive and personal folders
            is_personal_folder = any(p in path_str_lower for p in ("d:\\sreekanta", "\\documents", "\\desktop", "\\downloads", "auraai"))
            is_dev_scratch = any(p in path_str_lower for p in ("\\scratch\\", "\\tests\\", "\\scripts\\", "\\.git\\"))

            personal_boost = 0.15 if is_personal_folder else 0.0
            dev_penalty = -0.35 if is_dev_scratch else 0.0

            final_score = token_ratio * 0.8 + ext_boost + personal_boost + dev_penalty
            return min(1.0, max(0.0, final_score))

        return 0.0

    def find_files(self, query: str, max_results: int = 10, max_depth: int = 2) -> list[dict[str, Any]]:
        """
        Search for files matching the given query across search roots.
        
        Returns a list of candidate dictionaries sorted by relevance score.
        """
        query_stem, query_tokens, is_self_query, explicit_ext = self.normalize_query(query)
        if not query_stem and not query_tokens:
            return []

        search_roots = self.get_search_roots()
        candidates: list[dict[str, Any]] = []
        seen_paths: set[str] = set()

        # Step 1: Instant shallow scan (immediate direct files in search roots)
        for root in search_roots:
            if not root.exists() or not root.is_dir():
                continue
            try:
                for entry in root.iterdir():
                    if entry.is_file():
                        if entry.name.startswith((".", "~$")) or entry.suffix.lower() in (".pyc", ".pyd", ".tmp", ".log", ".bin"):
                            continue
                        norm_key = str(entry.resolve()).lower()
                        if norm_key in seen_paths:
                            continue

                        score = self._score_file(entry, query_stem, query_tokens, is_self_query=is_self_query, explicit_ext=explicit_ext)
                        if score >= 0.5:
                            seen_paths.add(norm_key)
                            try:
                                stat = entry.stat()
                                size_bytes = stat.st_size
                                modified_time = stat.st_mtime
                            except Exception:
                                size_bytes = 0
                                modified_time = 0.0

                            candidates.append({
                                "path": entry,
                                "path_str": str(entry),
                                "filename": entry.name,
                                "stem": entry.stem,
                                "extension": entry.suffix.lower(),
                                "size_bytes": size_bytes,
                                "modified_time": modified_time,
                                "score": score,
                            })
            except Exception as e:
                logger.debug(f"Shallow scan notice on {root}: {e}")

        # If shallow scan already found a high-confidence match (>= 0.85), return immediately in < 2ms!
        if candidates and any(c["score"] >= 0.85 for c in candidates):
            def _sort_key(item: dict[str, Any]):
                ext_pref = 1 if item["extension"] in (".pdf", ".docx", ".doc", ".txt", ".md") else 0
                return (item["score"], ext_pref, item["modified_time"])

            candidates.sort(key=_sort_key, reverse=True)
            return candidates[:max_results]

        # Step 2: Pruned recursive walk only if shallow scan didn't find high-confidence match
        for root in search_roots:
            if not root.exists() or not root.is_dir():
                continue

            try:
                for dirpath, dirnames, filenames in os.walk(root):
                    # Prune slow/irrelevant directories
                    dirnames[:] = [
                        d for d in dirnames
                        if not d.startswith((".", "__"))
                        and d.lower() not in (
                            "node_modules", ".venv", "venv", "env", "site-packages",
                            "appdata", "windows", "program files", "program files (x86)",
                            "dist", "build", ".git", ".aura_staging", "cache", "temp"
                        )
                    ]

                    # Check depth relative to root
                    try:
                        rel_parts = Path(dirpath).relative_to(root).parts
                        if len(rel_parts) > max_depth:
                            dirnames.clear()
                            continue
                    except Exception:
                        pass

                    for filename in filenames:
                        # Ignore system/binary files
                        if filename.startswith((".", "~$")) or filename.endswith((".pyc", ".pyd", ".tmp", ".log", ".bin")):
                            continue

                        full_path = Path(dirpath) / filename
                        norm_key = str(full_path.resolve()).lower()
                        if norm_key in seen_paths:
                            continue

                        score = self._score_file(full_path, query_stem, query_tokens, is_self_query=is_self_query, explicit_ext=explicit_ext)
                        if score >= 0.5:
                            seen_paths.add(norm_key)
                            try:
                                stat = full_path.stat()
                                size_bytes = stat.st_size
                                modified_time = stat.st_mtime
                            except Exception:
                                size_bytes = 0
                                modified_time = 0.0

                            candidates.append({
                                "path": full_path,
                                "path_str": str(full_path),
                                "filename": full_path.name,
                                "stem": full_path.stem,
                                "extension": full_path.suffix.lower(),
                                "size_bytes": size_bytes,
                                "modified_time": modified_time,
                                "score": score,
                            })
            except Exception as e:
                logger.debug(f"Deep traversal error on {root}: {e}")

        # Sort by score descending, then by priority extension, then by newest modified time
        def _sort_key(item: dict[str, Any]):
            ext_pref = 1 if item["extension"] in (".pdf", ".docx", ".doc", ".txt", ".md") else 0
            return (item["score"], ext_pref, item["modified_time"])

        candidates.sort(key=_sort_key, reverse=True)
        return candidates[:max_results]

    def find_best_file(self, query: str) -> Path | None:
        """Find the single most relevant file for the given query.

        Threshold is 0.75 (not 0.5) — calibrated so that single-token
        coincidences (e.g. "status" matching architecture_status.md for
        query "git status") don't clear the bar. A genuine name match
        scores >= 0.98; a clear partial match (query substring in stem)
        scores >= 0.90. The 0.75 floor admits fuzzy-but-meaningful matches
        while rejecting noise. Recalibrate against the eval corpus once
        classification logging is in place.
        """
        _CONFIDENCE_FLOOR = 0.75
        results = self.find_files(query, max_results=1)
        if results and results[0]["score"] >= _CONFIDENCE_FLOOR:
            return results[0]["path"]
        return None

    def open_file(self, file_path: Path | str) -> tuple[bool, str]:
        """
        Open a file using the default Windows system application.
        
        Returns:
            (success: bool, message: str)
        """
        target = Path(file_path)
        if not target.exists():
            return False, f"File does not exist: {target}"

        try:
            # On Windows, os.startfile opens with the registered default application
            os.startfile(str(target))
            return True, f"✓ Opened '{target.name}' with default application."
        except Exception as e:
            logger.warning(f"os.startfile failed for {target}: {e}. Falling back to cmd start.")
            try:
                subprocess.Popen(["cmd", "/c", "start", "", str(target)], shell=True)
                return True, f"✓ Opened '{target.name}'."
            except Exception as exc:
                return False, f"Failed to open '{target.name}': {exc}"

    def find_and_open(self, query: str) -> tuple[bool, str, Path | None]:
        """
        Search for a matching file and open it.
        
        Returns:
            (success: bool, message: str, matched_path: Path | None)
        """
        best_match = self.find_best_file(query)
        if not best_match:
            # Check if query is already an exact path
            direct_path = Path(query.strip(" '\""))
            if direct_path.exists() and direct_path.is_file():
                best_match = direct_path

        if best_match:
            ok, msg = self.open_file(best_match)
            if ok:
                return True, f"✓ Opened '{best_match.name}'\n📍 Location: {best_match}", best_match
            return False, msg, best_match

        return False, f"Could not find a file matching '{query}'. Searched in Documents, Downloads, Desktop, and Workspace.", None
