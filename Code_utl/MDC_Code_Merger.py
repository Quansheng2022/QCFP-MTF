import fnmatch
import hashlib
import os
from pathlib import Path
from typing import List, Optional, Tuple


# ==============================================================================
# Project File Merger
#
# Purpose:
#   Generate a reviewable text snapshot of a software project for:
#     - Code Review
#     - Architecture Review
#     - Governance Review
#     - Release Candidate Review
#
# Design principles:
#   1. Scan project root by default.
#   2. Explicitly exclude secrets and binary/generated artifacts.
#   3. Hidden files are NOT automatically included.
#   4. Keep important project/root configuration files.
#   5. Record all read failures in the generated snapshot.
#   6. Never recursively include the output snapshot itself.
# ==============================================================================


# ==============================================================================
# Configuration
# ==============================================================================

PROJECT_ROOT = Path(
    r"C:\Users\Quansheng\Documents\projects\MD_Converter"
)

# project:
#   Scan the entire project, including root-level specification/configuration/
#   governance/CI files.
#
# package:
#   Scan only PACKAGE_SUBDIR, useful for package-level source-code review.
SCAN_MODE = "project"

PACKAGE_SUBDIR = "md_converter"

OUTPUT_FILE = Path(
    r"C:\Users\Quansheng\Documents\projects"
    r"\TA_Workflow\Merged_Code\merged_code_MDC.txt"
)

# Optional maximum size for one text file.
# None = no limit.
#
# For normal source repositories, 5 MB is a reasonable protection against
# accidentally including huge generated text files.
MAX_FILE_SIZE_BYTES: Optional[int] = 5 * 1024 * 1024


# ==============================================================================
# Directory filters
# ==============================================================================

EXCLUDE_DIRS = {
    # Python
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".eggs",
    "venv",
    "env",
    ".venv",

    # Version control / IDE
    ".git",
    ".idea",
    ".vscode",

    # JavaScript / frontend
    "node_modules",

    # Build artifacts
    "dist",
    "build",
    "htmlcov",

    # Misc caches
    ".cache",
}


# ==============================================================================
# File extension filters
# ==============================================================================

INCLUDE_EXTENSIONS = {
    # Python / scripting
    ".py",
    ".pyi",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",

    # Java / C / C++ / Go / Rust / etc.
    ".java",
    ".cpp",
    ".cc",
    ".cxx",
    ".c",
    ".h",
    ".hpp",
    ".go",
    ".rs",
    ".rb",
    ".php",

    # Web
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".less",

    # Configuration / structured data
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",

    # Documentation / text
    ".txt",
    ".md",
    ".rst",

    # SQL
    ".sql",

    # Shell / automation
    ".sh",
    ".bash",
    ".bat",
    ".cmd",
    ".ps1",

    # Lock files
    ".lock",
}


EXCLUDE_EXTENSIONS = {
    # Python compiled/binary
    ".pyc",
    ".pyo",
    ".pyd",

    # Native binaries
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",

    # Images
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".webp",

    # Video
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",

    # Audio
    ".mp3",
    ".wav",
    ".flac",

    # Archives
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".rar",
    ".7z",

    # Office / document binaries
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",

    # Database
    ".db",
    ".sqlite",
    ".sqlite3",

    # Logs / temp
    ".log",
    ".tmp",
    ".cache",
}


# ==============================================================================
# Explicit filename filters
# ==============================================================================

# Important files without conventional source-code extensions.
INCLUDE_FILENAMES = {
    "Dockerfile",
    "Makefile",
    "Procfile",
    "Pipfile",

    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".flake8",
    ".coveragerc",

    # Safe environment-variable templates only.
    ".env.example",
    ".env.sample",
}


# Exact filenames that should never be uploaded into an AI review snapshot.
SENSITIVE_FILENAMES = {
    ".env",
    ".npmrc",
    ".pypirc",

    "credentials.json",
    "credential.json",
    "secrets.json",
    "secret.json",

    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}


# Sensitive patterns.
#
# IMPORTANT:
# .env.example and .env.sample are handled by INCLUDE_FILENAMES first.
SENSITIVE_PATTERNS = {
    ".env.*",

    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
    "*.jks",
    "*.keystore",

    "*credentials*.json",
    "*secrets*.json",
}


# Patterns that are text, but normally useless/noisy for source review.
EXCLUDE_PATTERNS = {
    "*.min.js",
    "*.min.css",

    "*.log",
    "*.tmp",

    "~*",
    "*.bak",
    "*.old",
    "*.swp",
    "*.swo",
}


# ==============================================================================
# Encoding support
# ==============================================================================

TEXT_ENCODINGS = (
    "utf-8-sig",
    "utf-8",
    "gb18030",
)


# ==============================================================================
# Data structures
# ==============================================================================

FileEntry = Tuple[Path, str]
MergedEntry = Tuple[Path, str, str, str]
SkippedEntry = Tuple[str, str]


# ==============================================================================
# Filter helpers
# ==============================================================================

def matches_any_pattern(filename: str, patterns) -> bool:
    """Return True if filename matches any fnmatch pattern."""
    name_lower = filename.lower()

    return any(
        fnmatch.fnmatch(name_lower, pattern.lower())
        for pattern in patterns
    )


def is_sensitive_file(filename: str) -> bool:
    """
    Determine whether a file may contain credentials/secrets.

    Safe templates such as .env.example and .env.sample are explicitly allowed.
    """
    if filename in INCLUDE_FILENAMES:
        return False

    if filename in SENSITIVE_FILENAMES:
        return True

    return matches_any_pattern(filename, SENSITIVE_PATTERNS)


def should_include_file(path: Path, output_file: Path) -> bool:
    """
    Determine whether a file should be included in the project snapshot.
    """

    filename = path.name

    # ------------------------------------------------------------------
    # Never include the generated output file itself.
    # ------------------------------------------------------------------

    try:
        if path.resolve() == output_file.resolve():
            return False
    except OSError:
        pass

    # ------------------------------------------------------------------
    # Sensitive files always lose, except explicitly safe templates.
    # ------------------------------------------------------------------

    if is_sensitive_file(filename):
        return False

    # ------------------------------------------------------------------
    # Explicit noisy/generated filename patterns.
    # ------------------------------------------------------------------

    if matches_any_pattern(filename, EXCLUDE_PATTERNS):
        return False

    # ------------------------------------------------------------------
    # Explicit safe filenames.
    # ------------------------------------------------------------------

    if filename in INCLUDE_FILENAMES:
        return True

    # ------------------------------------------------------------------
    # Hidden files are NOT automatically included.
    #
    # This is intentional:
    #
    #   .env       -> excluded
    #   .flake8    -> included via whitelist
    #   .coveragerc-> included via whitelist
    #
    # Unknown hidden files require explicit approval.
    # ------------------------------------------------------------------

    if filename.startswith("."):
        return False

    suffix = path.suffix.lower()

    # ------------------------------------------------------------------
    # Explicit excluded extensions.
    # ------------------------------------------------------------------

    if suffix in EXCLUDE_EXTENSIONS:
        return False

    # ------------------------------------------------------------------
    # Supported text/code extensions.
    # ------------------------------------------------------------------

    if suffix in INCLUDE_EXTENSIONS:
        return True

    return False


# ==============================================================================
# File reading
# ==============================================================================

def read_text_file(path: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Read a text file using supported encodings.

    Returns:
        (content, encoding, error)

    On success:
        content != None
        encoding != None
        error == None

    On failure:
        content == None
        error contains explanation
    """

    if MAX_FILE_SIZE_BYTES is not None:
        try:
            size = path.stat().st_size
        except OSError as exc:
            return None, None, f"stat failed: {exc}"

        if size > MAX_FILE_SIZE_BYTES:
            return (
                None,
                None,
                (
                    f"file too large: "
                    f"{size:,} bytes > {MAX_FILE_SIZE_BYTES:,} bytes"
                ),
            )

    errors = []

    for encoding in TEXT_ENCODINGS:
        try:
            with path.open(
                "r",
                encoding=encoding,
                errors="strict",
            ) as file_obj:
                content = file_obj.read()

            return content, encoding, None

        except UnicodeDecodeError as exc:
            errors.append(
                f"{encoding}: UnicodeDecodeError({exc})"
            )

        except OSError as exc:
            return None, None, f"read failed: {exc}"

    return (
        None,
        None,
        "encoding detection failed: " + " | ".join(errors),
    )


# ==============================================================================
# Discovery
# ==============================================================================

def discover_files(
    root_dir: Path,
    project_root: Path,
    output_file: Path,
) -> Tuple[List[FileEntry], int]:
    """
    Discover all eligible project files.

    Returns:
        eligible files
        total visited files
    """

    candidates: List[FileEntry] = []
    total_seen = 0

    for current_root, dirs, files in os.walk(root_dir):

        # --------------------------------------------------------------
        # Prune excluded directories.
        # --------------------------------------------------------------

        dirs[:] = sorted(
            [
                directory
                for directory in dirs
                if directory not in EXCLUDE_DIRS
            ],
            key=str.lower,
        )

        current_root_path = Path(current_root)

        for filename in files:
            total_seen += 1

            full_path = current_root_path / filename

            if not should_include_file(full_path, output_file):
                continue

            try:
                rel_path = full_path.relative_to(project_root)
            except ValueError:
                rel_path = Path(
                    os.path.relpath(full_path, project_root)
                )

            # Always use "/" inside merged snapshot so output is stable
            # across Windows/Linux readers.
            rel_path_text = rel_path.as_posix()

            candidates.append(
                (
                    full_path,
                    rel_path_text,
                )
            )

    candidates.sort(
        key=lambda item: item[1].lower()
    )

    return candidates, total_seen


# ==============================================================================
# Snapshot generation
# ==============================================================================

def collect_files(
    root_dir: Path,
    output_file: Path,
    project_root: Path,
) -> None:
    """
    Traverse root_dir and merge reviewable project files into one text snapshot.

    Args:
        root_dir:
            Directory to scan.

        output_file:
            Generated merged text snapshot.

        project_root:
            Project root used to calculate stable relative paths.
    """

    root_dir = root_dir.resolve()
    project_root = project_root.resolve()

    # Do not call resolve() before parent exists on some environments.
    output_file = output_file.expanduser().absolute()

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 80)
    print("开始扫描项目")
    print(f"项目根目录: {project_root}")
    print(f"扫描路径: {root_dir}")
    print(f"输出文件: {output_file}")
    print("=" * 80)

    # ------------------------------------------------------------------
    # Discover candidate files.
    # ------------------------------------------------------------------

    candidates, total_seen = discover_files(
        root_dir=root_dir,
        project_root=project_root,
        output_file=output_file,
    )

    merged_entries: List[MergedEntry] = []
    skipped_entries: List[SkippedEntry] = []

    total_chars = 0

    # ------------------------------------------------------------------
    # Read everything first.
    #
    # This allows header statistics to reflect actual successful reads,
    # rather than only discovered filenames.
    # ------------------------------------------------------------------

    for full_path, rel_path in candidates:

        content, encoding, error = read_text_file(
            full_path
        )

        if content is None:
            skipped_entries.append(
                (
                    rel_path,
                    error or "unknown read error",
                )
            )

            print(
                f"跳过: {rel_path} "
                f"- {error or 'unknown error'}"
            )

            continue

        merged_entries.append(
            (
                full_path,
                rel_path,
                content,
                encoding or "unknown",
            )
        )

        total_chars += len(content)

        if encoding == "utf-8-sig":
            display_encoding = "UTF-8"
        else:
            display_encoding = encoding.upper()

        print(
            f"已处理 [{display_encoding}]: "
            f"{rel_path}"
        )

    # ------------------------------------------------------------------
    # Write merged snapshot.
    # ------------------------------------------------------------------

    with output_file.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as out_f:

        out_f.write("=" * 80 + "\n")
        out_f.write("项目文件合并快照\n")
        out_f.write(f"项目根目录: {project_root}\n")
        out_f.write(f"扫描路径: {root_dir}\n")
        out_f.write(f"扫描模式: {SCAN_MODE}\n")
        out_f.write(f"遍历文件数: {total_seen}\n")
        out_f.write(
            f"候选文本文件数: {len(candidates)}\n"
        )
        out_f.write(
            f"成功合并文件数: {len(merged_entries)}\n"
        )
        out_f.write(
            f"读取失败文件数: {len(skipped_entries)}\n"
        )
        out_f.write("=" * 80 + "\n\n")

        # --------------------------------------------------------------
        # File contents
        # --------------------------------------------------------------

        for (
            _full_path,
            rel_path,
            content,
            _encoding,
        ) in merged_entries:

            out_f.write(
                f"==== {rel_path} ====\n"
            )

            out_f.write(content)

            if not content.endswith("\n"):
                out_f.write("\n")

            # Blank line between files.
            out_f.write("\n")

        # --------------------------------------------------------------
        # Merge audit report
        # --------------------------------------------------------------

        out_f.write("\n")
        out_f.write("=" * 80 + "\n")
        out_f.write("MERGE REPORT\n")
        out_f.write("=" * 80 + "\n")

        out_f.write(
            f"Files visited: {total_seen}\n"
        )
        out_f.write(
            f"Eligible candidates: {len(candidates)}\n"
        )
        out_f.write(
            f"Merged successfully: {len(merged_entries)}\n"
        )
        out_f.write(
            f"Read failures: {len(skipped_entries)}\n"
        )
        out_f.write(
            f"Total source characters: {total_chars:,}\n"
        )

        if skipped_entries:
            out_f.write("\n")
            out_f.write("Read failures:\n")

            for rel_path, reason in skipped_entries:
                out_f.write(
                    f"- {rel_path}: {reason}\n"
                )
        else:
            out_f.write(
                "\nRead failures: NONE\n"
            )

        out_f.write("=" * 80 + "\n")

    # ------------------------------------------------------------------
    # Calculate SHA256 of generated snapshot.
    #
    # The hash is printed to console rather than written into the snapshot
    # itself, because writing it into the file would change the hash.
    # ------------------------------------------------------------------

    snapshot_sha256 = calculate_sha256(
        output_file
    )

    # ------------------------------------------------------------------
    # Console summary
    # ------------------------------------------------------------------

    print()
    print("=" * 80)
    print("合并完成!")
    print(f"遍历文件数: {total_seen}")
    print(f"候选文本文件数: {len(candidates)}")
    print(f"成功处理文件数: {len(merged_entries)}")
    print(f"读取失败文件数: {len(skipped_entries)}")
    print(f"输出文件: {output_file}")
    print(f"总字符数: {total_chars:,}")
    print(f"SHA256: {snapshot_sha256}")

    # Token estimation is intentionally only a rough range.
    token_low = total_chars // 4
    token_high = total_chars // 2

    print(
        "粗略 Token 范围: "
        f"~{token_low:,} - {token_high:,}"
    )

    print("=" * 80)


# ==============================================================================
# Utilities
# ==============================================================================

def calculate_sha256(path: Path) -> str:
    """Calculate SHA256 hash for a generated snapshot."""

    sha256 = hashlib.sha256()

    with path.open("rb") as file_obj:
        while True:
            block = file_obj.read(
                1024 * 1024
            )

            if not block:
                break

            sha256.update(block)

    return sha256.hexdigest()


def format_file_size(size: int) -> str:
    """Human-readable file size."""

    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"

    if size >= 1024:
        return f"{size / 1024:.2f} KB"

    return f"{size} bytes"


# ==============================================================================
# Main
# ==============================================================================

def main() -> None:

    project_root = PROJECT_ROOT

    # ------------------------------------------------------------------
    # Resolve scan mode.
    # ------------------------------------------------------------------

    if SCAN_MODE == "project":
        scan_path = project_root

    elif SCAN_MODE == "package":
        scan_path = (
            project_root /
            PACKAGE_SUBDIR
        )

    else:
        print(
            "错误: SCAN_MODE 必须为 "
            "'project' 或 'package'"
        )
        return

    # ------------------------------------------------------------------
    # Basic validation.
    # ------------------------------------------------------------------

    if not project_root.exists():
        print(
            f"错误: 项目根目录不存在 - "
            f"{project_root}"
        )
        return

    if not project_root.is_dir():
        print(
            f"错误: 项目根路径不是目录 - "
            f"{project_root}"
        )
        return

    if not scan_path.exists():
        print(
            f"错误: 扫描路径不存在 - "
            f"{scan_path}"
        )
        return

    if not scan_path.is_dir():
        print(
            f"错误: 扫描路径不是目录 - "
            f"{scan_path}"
        )
        return

    # ------------------------------------------------------------------
    # Generate snapshot.
    # ------------------------------------------------------------------

    try:
        collect_files(
            root_dir=scan_path,
            output_file=OUTPUT_FILE,
            project_root=project_root,
        )

    except Exception as exc:
        print()
        print("=" * 80)
        print("合并失败!")
        print(
            f"{type(exc).__name__}: {exc}"
        )
        print("=" * 80)
        raise

    # ------------------------------------------------------------------
    # Final file information.
    # ------------------------------------------------------------------

    if OUTPUT_FILE.exists():

        size = OUTPUT_FILE.stat().st_size

        print()
        print(
            f"输出文件大小: "
            f"{format_file_size(size)}"
        )

        print()
        print("=" * 80)
        print("📤 上传建议:")
        print(
            f"1. 上传文件: {OUTPUT_FILE}"
        )
        print(
            "2. 项目级审查可输入:"
        )
        print(
            "   “请审查、验收上传的项目完整快照。”"
        )
        print(
            "3. Governance / RC 验收可输入:"
        )
        print(
            "   “请按照 Canonical Specification、"
            "Governance 与 Release Gate 对项目进行最终验收。”"
        )
        print(
            "4. 如果文件过大，可切换 "
            "SCAN_MODE='package' 仅审查代码包。"
        )
        print("=" * 80)


if __name__ == "__main__":
    main()