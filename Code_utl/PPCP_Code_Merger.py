from __future__ import annotations

import fnmatch
import os
from pathlib import Path


# ============================================================================
# Project File Merger
# Passport Photo Compliance Processor
#
# Purpose:
#   Merge relevant project source / test / config / documentation files
#   into one UTF-8 text artifact for AI review and acceptance.
#
# Important:
#   - Scan the whole PROJECT_ROOT.
#   - Do NOT scan passport_photo/ only.
#   - Do NOT include secrets, caches, binary files or previous merged artifacts.
# ============================================================================


# ----------------------------------------------------------------------------
# Directory exclusions
# ----------------------------------------------------------------------------

EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "node_modules",

    # Python / test caches
    ".pytest_cache",
    ".hypothesis",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",

    # Coverage
    "htmlcov",

    # Build artifacts
    "dist",
    "build",

    # Virtual environments
    "venv",
    "env",
    ".venv",

    # Packaging
    ".eggs",
}


# ----------------------------------------------------------------------------
# Extension exclusions
# ----------------------------------------------------------------------------

EXCLUDE_EXTENSIONS = {
    # Python compiled / native
    ".pyc",
    ".pyo",
    ".pyd",

    # Native binaries
    ".exe",
    ".dll",
    ".so",
    ".dylib",

    # Images
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".webp",
    ".tif",
    ".tiff",

    # Video
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".wmv",

    # Audio
    ".mp3",
    ".wav",
    ".flac",
    ".aac",

    # Archives
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".rar",
    ".7z",

    # Binary documents
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",

    # Databases
    ".db",
    ".sqlite",
    ".sqlite3",

    # Runtime / cache
    ".log",
    ".tmp",
    ".cache",

    # Coverage binary database
    ".coverage",
}


# ----------------------------------------------------------------------------
# Extensions that may be included
# ----------------------------------------------------------------------------

INCLUDE_EXTENSIONS = {
    # Python
    ".py",

    # JavaScript / TypeScript
    ".js",
    ".ts",
    ".jsx",
    ".tsx",

    # Java / C / C++
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".hpp",

    # Other languages
    ".go",
    ".rs",
    ".rb",
    ".php",

    # Web
    ".html",
    ".css",
    ".scss",
    ".less",

    # Structured configuration
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",

    # Documentation / text
    ".txt",
    ".md",
    ".rst",

    # SQL
    ".sql",

    # Shell / automation
    ".sh",
    ".bat",
    ".cmd",
    ".ps1",

    # Config
    ".ini",
    ".cfg",
    ".conf",
}


# ----------------------------------------------------------------------------
# Exact special filenames that may be included
# ----------------------------------------------------------------------------

INCLUDE_FILENAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",

    ".gitignore",
    ".gitattributes",
    ".flake8",
    ".editorconfig",

    # Templates only — never real .env files
    ".env.example",
    ".env.sample",
}


# ----------------------------------------------------------------------------
# Sensitive or generated files that must never be included
# ----------------------------------------------------------------------------

EXCLUDE_FILENAMES = {
    # Secrets
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.test",

    # Coverage runtime database
    ".coverage",

    # OS artifacts
    "Thumbs.db",
    ".DS_Store",
}


# ----------------------------------------------------------------------------
# Filename patterns that must be excluded
# ----------------------------------------------------------------------------

EXCLUDE_FILENAME_PATTERNS = {
    # Prevent previous merged artifacts from being merged again.
    "merged_*.txt",
    "merged-*.txt",

    # Optional generated reports
    "coverage*.xml",
}


# ----------------------------------------------------------------------------
# Safety limits
# ----------------------------------------------------------------------------

# Avoid accidentally merging giant generated text files / datasets.
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB per file


# ----------------------------------------------------------------------------
# Phase 1 acceptance structure
#
# Set to False if using this merger for another project or later phase.
# ----------------------------------------------------------------------------

VALIDATE_PHASE1_ACCEPTANCE_STRUCTURE = True


PHASE1_REQUIRED_PATHS = (
    "passport_photo",
    "tests",
    "tests/unit",
    "tests/property",
    "tests/golden",
    "pyproject.toml",
)


PHASE1_RECOMMENDED_PATHS = (
    "tests/acceptance",
    "tests/fixtures",
    "TEST_EVIDENCE_PHASE1.md",
    "PHASE1_ACCEPTANCE_PATCH.md",
)


# ============================================================================
# Helpers
# ============================================================================


def validate_acceptance_structure(project_root: Path) -> None:
    """
    Validate that the repository contains the minimum artifacts needed
    for Phase 1 Final Acceptance.

    Missing required paths stop the merge.
    Missing recommended paths generate warnings only.
    """

    missing_required: list[str] = []

    for relative_path in PHASE1_REQUIRED_PATHS:
        path = project_root / relative_path
        if not path.exists():
            missing_required.append(relative_path)

    if missing_required:
        print("\n" + "=" * 80)
        print("ERROR: Phase 1 acceptance structure is incomplete.")
        print("=" * 80)

        for relative_path in missing_required:
            print(f"Missing required path: {relative_path}")

        raise RuntimeError(
            "Required Phase 1 Test Evidence artifacts are missing."
        )

    print("\nPhase 1 required acceptance structure: PASS")

    for relative_path in PHASE1_RECOMMENDED_PATHS:
        path = project_root / relative_path
        if not path.exists():
            print(
                f"WARNING: Recommended acceptance artifact missing: "
                f"{relative_path}"
            )


def matches_excluded_filename_pattern(filename: str) -> bool:
    """
    Return True if filename matches one of the generated-file patterns.
    """

    filename_lower = filename.lower()

    return any(
        fnmatch.fnmatch(filename_lower, pattern.lower())
        for pattern in EXCLUDE_FILENAME_PATTERNS
    )


def should_include_file(file_path: Path) -> bool:
    """
    Decide whether one filesystem file should enter the merged artifact.
    """

    filename = file_path.name
    suffix = file_path.suffix.lower()

    # Explicit filename exclusions.
    if filename in EXCLUDE_FILENAMES:
        return False

    # Generated filename patterns.
    if matches_excluded_filename_pattern(filename):
        return False

    # Temporary / editor backup files.
    if filename.startswith("~"):
        return False

    if filename.endswith(".tmp"):
        return False

    if filename.endswith(".bak"):
        return False

    # Explicit extension exclusions.
    if suffix in EXCLUDE_EXTENSIONS:
        return False

    # Exact whitelisted filenames.
    if filename in INCLUDE_FILENAMES:
        return True

    # Normal text/code extensions.
    if suffix in INCLUDE_EXTENSIONS:
        return True

    return False


def read_text_file(file_path: Path) -> tuple[str, str]:
    """
    Read a project text file.

    Returns:
        (content, encoding_used)

    Encoding order:
        UTF-8
        UTF-8 with BOM
        GBK
    """

    encodings = (
        "utf-8",
        "utf-8-sig",
        "gbk",
    )

    last_error: Exception | None = None

    for encoding in encodings:
        try:
            content = file_path.read_text(encoding=encoding)
            return content, encoding
        except UnicodeDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    raise RuntimeError(f"Unable to read file: {file_path}")


def safe_relative_path(
    file_path: Path,
    project_root: Path,
) -> Path:
    """
    Return a path relative to project root.
    """

    try:
        return file_path.relative_to(project_root)
    except ValueError as exc:
        raise RuntimeError(
            f"File lies outside project root: {file_path}"
        ) from exc


# ============================================================================
# Main merge logic
# ============================================================================


def collect_files(
    root_dir: Path,
    output_file: Path,
    project_root: Path,
) -> None:
    """
    Walk root_dir and merge relevant project files into output_file.

    Args:
        root_dir:
            Directory to scan.

        output_file:
            Final merged artifact.

        project_root:
            Repository root used for relative paths.
    """

    root_dir = root_dir.resolve()
    output_file = output_file.resolve()
    project_root = project_root.resolve()

    if not root_dir.is_dir():
        raise RuntimeError(
            f"Scan root does not exist or is not a directory: {root_dir}"
        )

    if not project_root.is_dir():
        raise RuntimeError(
            f"Project root does not exist or is not a directory: "
            f"{project_root}"
        )

    # Ensure scan root belongs to project root.
    try:
        root_dir.relative_to(project_root)
    except ValueError as exc:
        raise RuntimeError(
            f"Scan root must be inside project root.\n"
            f"Project root: {project_root}\n"
            f"Scan root:    {root_dir}"
        ) from exc

    candidate_files: list[tuple[Path, Path]] = []

    skipped_files: list[tuple[str, str]] = []

    # ------------------------------------------------------------------------
    # Discover files
    # ------------------------------------------------------------------------

    for current_root, dirs, files in os.walk(root_dir):
        current_root_path = Path(current_root)

        # Remove excluded directories before os.walk descends into them.
        dirs[:] = sorted(
            (
                dirname
                for dirname in dirs
                if dirname not in EXCLUDE_DIRS
            ),
            key=str.lower,
        )

        for filename in sorted(files, key=str.lower):
            full_path = current_root_path / filename

            # Never merge the output artifact itself.
            try:
                if full_path.resolve() == output_file:
                    continue
            except OSError:
                pass

            if not should_include_file(full_path):
                continue

            relative_path = safe_relative_path(
                full_path,
                project_root,
            )

            try:
                file_size = full_path.stat().st_size
            except OSError as exc:
                skipped_files.append(
                    (
                        str(relative_path),
                        f"Unable to read file metadata: {exc}",
                    )
                )
                continue

            if file_size > MAX_FILE_SIZE_BYTES:
                skipped_files.append(
                    (
                        str(relative_path),
                        (
                            f"File too large: {file_size:,} bytes "
                            f"(limit={MAX_FILE_SIZE_BYTES:,})"
                        ),
                    )
                )
                continue

            candidate_files.append(
                (
                    full_path,
                    relative_path,
                )
            )

    # Deterministic order.
    candidate_files.sort(
        key=lambda item: str(item[1]).lower()
    )

    # ------------------------------------------------------------------------
    # Prepare output
    # ------------------------------------------------------------------------

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    merged_count = 0
    total_chars = 0

    # ------------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------------

    with output_file.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as out_f:

        out_f.write("=" * 80 + "\n")
        out_f.write("项目文件合并\n")
        out_f.write(f"项目根目录: {project_root}\n")
        out_f.write(f"扫描路径: {root_dir}\n")
        out_f.write(
            f"候选文件数: {len(candidate_files)}\n"
        )
        out_f.write("=" * 80 + "\n\n")

        for full_path, relative_path in candidate_files:
            relative_text = str(relative_path)

            try:
                content, encoding_used = read_text_file(
                    full_path
                )

            except Exception as exc:
                skipped_files.append(
                    (
                        relative_text,
                        f"Read failed: {exc}",
                    )
                )

                print(
                    f"跳过文件: {relative_text} - {exc}"
                )

                continue

            out_f.write(
                f"==== {relative_text} ====\n"
            )

            out_f.write(content)

            if not content.endswith("\n"):
                out_f.write("\n")

            out_f.write("\n")

            merged_count += 1
            total_chars += len(content)

            if encoding_used == "utf-8":
                print(
                    f"已处理: {relative_text}"
                )
            else:
                print(
                    f"已处理 ({encoding_used}): "
                    f"{relative_text}"
                )

        # --------------------------------------------------------------------
        # Audit summary
        # --------------------------------------------------------------------

        out_f.write("\n")
        out_f.write("=" * 80 + "\n")
        out_f.write("MERGE SUMMARY\n")

        out_f.write(
            f"候选文件数: {len(candidate_files)}\n"
        )

        out_f.write(
            f"成功合并文件数: {merged_count}\n"
        )

        out_f.write(
            f"跳过文件数: {len(skipped_files)}\n"
        )

        out_f.write(
            f"总字符数: {total_chars:,}\n"
        )

        if skipped_files:
            out_f.write("\n")
            out_f.write("SKIPPED FILES\n")

            for relative_path, reason in skipped_files:
                out_f.write(
                    f"- {relative_path}: {reason}\n"
                )

        out_f.write("=" * 80 + "\n")

    # ------------------------------------------------------------------------
    # Console summary
    # ------------------------------------------------------------------------

    estimated_tokens = total_chars // 3

    print("\n" + "=" * 80)
    print("合并完成!")
    print("=" * 80)

    print(
        f"候选文件数: {len(candidate_files)}"
    )

    print(
        f"成功处理文件数: {merged_count}"
    )

    print(
        f"跳过文件数: {len(skipped_files)}"
    )

    print(
        f"输出文件: {output_file}"
    )

    print(
        f"总字符数: {total_chars:,}"
    )

    print(
        f"预估 Token 数: ~{estimated_tokens:,}"
    )

    print("=" * 80)

    if skipped_files:
        print("\nWARNING: 有文件被跳过。")
        print(
            "请检查最终文件末尾的 SKIPPED FILES。"
        )


# ============================================================================
# Post-merge verification
# ============================================================================


def verify_final_artifact(
    output_file: Path,
) -> bool:
    """
    Perform basic structural checks against the generated acceptance artifact.

    This does not replace pytest.
    It only verifies that important Test Evidence sections made it into
    the merged review artifact.
    """

    if not output_file.is_file():
        print(
            f"ERROR: 输出文件不存在: {output_file}"
        )
        return False

    try:
        content = output_file.read_text(
            encoding="utf-8"
        )
    except Exception as exc:
        print(
            f"ERROR: 无法重新读取输出文件: {exc}"
        )
        return False

    required_markers = {
        "production source":
            "passport_photo",

        "unit tests":
            "tests\\unit",

        "property tests":
            "tests\\property",

        "golden tests":
            "tests\\golden",

        "pyproject":
            "==== pyproject.toml ====",
    }

    # Windows-generated relative paths normally contain backslashes.
    # Also accept forward-slash variants for portability.
    marker_alternatives = {
        "production source": (
            "passport_photo\\",
            "passport_photo/",
        ),
        "unit tests": (
            "tests\\unit\\",
            "tests/unit/",
        ),
        "property tests": (
            "tests\\property\\",
            "tests/property/",
        ),
        "golden tests": (
            "tests\\golden\\",
            "tests/golden/",
        ),
        "pyproject": (
            "==== pyproject.toml ====",
        ),
    }

    verification_failed = False

    print("\n" + "=" * 80)
    print("FINAL ARTIFACT VERIFICATION")
    print("=" * 80)

    for label, alternatives in marker_alternatives.items():
        found = any(
            marker in content
            for marker in alternatives
        )

        if found:
            print(
                f"PASS: {label}"
            )
        else:
            print(
                f"FAIL: {label}"
            )
            verification_failed = True

    # These are recommended rather than absolute structural blockers.
    recommended_markers = {
        "acceptance tests": (
            "tests\\acceptance\\",
            "tests/acceptance/",
        ),
        "test evidence document": (
            "==== TEST_EVIDENCE_PHASE1.md ====",
        ),
        "acceptance patch document": (
            "==== PHASE1_ACCEPTANCE_PATCH.md ====",
        ),
    }

    for label, alternatives in recommended_markers.items():
        found = any(
            marker in content
            for marker in alternatives
        )

        if found:
            print(
                f"PASS: {label}"
            )
        else:
            print(
                f"WARNING: {label} not found"
            )

    # Ensure Hypothesis runtime cache itself was not merged.
    forbidden_markers = (
        "==== .hypothesis\\",
        "==== .hypothesis/",
    )

    if any(
        marker in content
        for marker in forbidden_markers
    ):
        print(
            "FAIL: .hypothesis cache directory was merged."
        )
        verification_failed = True
    else:
        print(
            "PASS: .hypothesis cache excluded"
        )

    # Prevent nested merged artifacts.
    nested_merged_lines = [
        line
        for line in content.splitlines()
        if (
            line.startswith("==== merged_")
            or line.startswith("==== merged-")
        )
    ]

    if nested_merged_lines:
        print(
            "FAIL: Nested merged artifact detected:"
        )

        for line in nested_merged_lines[:10]:
            print(
                f"  {line}"
            )

        verification_failed = True

    else:
        print(
            "PASS: previous merged artifacts excluded"
        )

    print("=" * 80)

    return not verification_failed


# ============================================================================
# Main
# ============================================================================


def main() -> None:

    # ------------------------------------------------------------------------
    # Project configuration
    # ------------------------------------------------------------------------

    project_root = Path(
        r"C:\Users\Quansheng\Documents"
        r"\projects\PassportPhoto"
    )

    # IMPORTANT:
    # Scan the whole project root.
    #
    # Do NOT use:
    # project_root / "passport_photo"
    #
    scan_path = project_root

    output_file = Path(
        r"C:\Users\Quansheng\Documents"
        r"\projects\TA_Workflow"
        r"\Merged_Code"
        r"\merged_PPCP_phase1_final_acceptance.txt"
    )

    # ------------------------------------------------------------------------
    # Basic checks
    # ------------------------------------------------------------------------

    if not project_root.is_dir():
        print(
            f"错误: 项目根目录不存在 - "
            f"{project_root}"
        )
        return

    # ------------------------------------------------------------------------
    # Acceptance structure validation
    # ------------------------------------------------------------------------

    if VALIDATE_PHASE1_ACCEPTANCE_STRUCTURE:
        try:
            validate_acceptance_structure(
                project_root
            )
        except RuntimeError as exc:
            print(
                f"\n停止生成: {exc}"
            )
            return

    # ------------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------------

    try:
        collect_files(
            root_dir=scan_path,
            output_file=output_file,
            project_root=project_root,
        )

    except Exception as exc:
        print(
            f"\nERROR: 合并失败: {exc}"
        )
        return

    # ------------------------------------------------------------------------
    # File size
    # ------------------------------------------------------------------------

    if output_file.exists():
        size = output_file.stat().st_size

        if size >= 1024 * 1024:
            print(
                f"\n输出文件大小: "
                f"{size / (1024 * 1024):.2f} MB"
            )

        elif size >= 1024:
            print(
                f"\n输出文件大小: "
                f"{size / 1024:.2f} KB"
            )

        else:
            print(
                f"\n输出文件大小: "
                f"{size} 字节"
            )

    # ------------------------------------------------------------------------
    # Verify final artifact
    # ------------------------------------------------------------------------

    artifact_ok = verify_final_artifact(
        output_file
    )

    if not artifact_ok:
        print(
            "\nFINAL ARTIFACT VERIFICATION: FAILED"
        )
        print(
            "请修复上述问题后重新生成，不要上传当前文件。"
        )
        return

    print(
        "\nFINAL ARTIFACT VERIFICATION: PASS"
    )

    print("\n" + "=" * 80)
    print("上传前建议")
    print("=" * 80)

    print(
        "1. 确认 pytest 全量测试已经运行成功。"
    )

    print(
        "2. Phase 1 当前预期结果应为: "
        "237 passed / 0 failed / 0 errors。"
    )

    print(
        "3. 确认 TEST_EVIDENCE_PHASE1.md "
        "中的 Final Full Suite 数字一致。"
    )

    print(
        "4. 上传文件:"
    )

    print(
        f"   {output_file}"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()