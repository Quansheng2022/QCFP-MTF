
# coding: utf-8
"""
QCFP-MTF Project Source Bundle Builder
--------------------------------------

用途：
1. 将指定项目目录/文件合并成一个适合 ChatGPT / DeepSeek 审查的文本 Bundle。
2. 默认 fail-closed：
   - 敏感文件不进入 Bundle；
   - 读取失败/编码失败/源文件在合并过程中变化 -> BUNDLE_STATUS=INCOMPLETE；
   - STRICT_MODE=True 时，不会用不完整 Bundle 覆盖正式输出。
3. 每个文件记录：
   - path
   - source_sha256（原始字节）
   - content_sha256（写入 Bundle 的 UTF-8 文本）
   - size_bytes
   - encoding
   - line_count
4. Bundle 记录 Manifest SHA256，支持完整性和可追溯性检查。

QCFP-SOURCE-BUNDLE-2 收口（M1-M4）：
    M1 Scan Profiles：code-review（默认）/ governance-review 两个正式
       Profile，Profile 名称写入 Bundle，输出文件按 Profile 区分。
    M2 Scope Manifest Hash：SCOPE_MANIFEST_SHA256 证明「承诺扫描什么」，
       MANIFEST_SHA256 证明「实际合并了什么」，BUNDLE_ROOT_SHA256 绑定两者。
    M3 Encoding Detection：仅 BOM 时标 utf-8-sig，普通 UTF-8 标 utf-8，
       GB18030 兜底；解码失败 → merge error → INCOMPLETE。
    M4 Sidecar Bundle Hash + --verify：离线验证 Bundle+Sidecar
       （不依赖项目源目录）。

仅使用 Python 标准库。
"""

from __future__ import annotations

import fnmatch
import codecs
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


# ============================================================================
# 1. 用户配置
# ============================================================================

PROJECT_ROOT = Path(
    r"C:\Users\Quansheng\Documents\projects\TA_Workflow"
)

OUTPUT_FILE = PROJECT_ROOT / "Merged_Code" / "merged_code_QCFP-MTF.txt"

# M1：Scan Profiles 正式化。
#   code-review       —— 默认；日常 ChatGPT/DeepSeek 代码审查、修改验收。
#   governance-review —— 正式治理审查；在源码之上加入治理证据
#                        （audit/baseline、MTR evidence、utl、qcfp_settings）。
# 注意：MTR 证据实际位于 Report/QCFP_MTF/audit/mtr（见
# scripts/minimal_trusted_release.py），不是根级 audit/mtr。
SCAN_PROFILES = {
    "code-review": [
        "Core/QCFP_MTF",
        "run_QCFP_MTF_workflow.py",
        "run_QCFP_Governance_workflow.py",
    ],
    "governance-review": [
        "Core/QCFP_MTF",
        "run_QCFP_MTF_workflow.py",
        "run_QCFP_Governance_workflow.py",
        "audit/baseline",
        "Report/QCFP_MTF/audit/mtr",
        "Core/utl",
        "Config/qcfp_settings.yaml",
    ],
}

DEFAULT_PROFILE = "code-review"

# 向后兼容别名（等价 code-review）。
SCAN_TARGETS = SCAN_PROFILES[DEFAULT_PROFILE]

# True：
#   Bundle 不完整时写成 *.incomplete.txt，不覆盖正式 OUTPUT_FILE。
# False：
#   即使不完整也写 OUTPUT_FILE，但 Footer 会标记 BUNDLE_STATUS=INCOMPLETE。
STRICT_MODE = True

# 合并结束后再次读取源文件，确认 SHA256 没有在合并过程中发生变化。
VERIFY_SOURCE_AFTER_WRITE = True

# 额外写一个 JSON Manifest sidecar。
WRITE_SIDECAR_MANIFEST = True

# None = 不限制单文件大小。
# 如希望防止误收超大文本文件，可设置，例如：
# MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
MAX_FILE_SIZE_BYTES: Optional[int] = None


# ============================================================================
# 2. 扫描 / 排除规则
# ============================================================================

EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    "dist",
    "build",
    "venv",
    "env",
    ".venv",
    "merged_code",
}

INCLUDE_EXTENSIONS = {
    ".py", ".pyi",
    ".js", ".ts", ".jsx", ".tsx",
    ".java",
    ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp",
    ".go", ".rs", ".rb", ".php",
    ".html", ".css", ".scss", ".less",
    ".json", ".xml", ".yaml", ".yml", ".toml",
    ".txt", ".md", ".rst",
    ".sql",
    ".sh", ".bat", ".cmd", ".ps1",
    ".ini", ".cfg", ".conf",
}

# 明确允许的无扩展名 / 隐藏配置文件。
# 注意：不再“所有隐藏文件自动放行”。
SAFE_SPECIAL_FILES = {
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".flake8",
    ".dockerignore",
    ".env.example",
    ".env.sample",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}

# 文件名级敏感信息阻断。
SENSITIVE_FILE_NAMES = {
    ".env",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "credentials",
    "credentials.json",
    "credential.json",
    "secrets.json",
    "secret.json",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}

# 后缀级敏感信息阻断。
SENSITIVE_SUFFIXES = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".jks",
    ".keystore",
}

# 普通排除模式。
EXCLUDE_PATTERNS = {
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.tmp",
    "*.bak",
    "*.swp",
    "*.swo",
    "*~",
    "#*#",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
}

# 强敏感内容标记：命中则文件不进入 Bundle。
# 只做低误报的“私钥”类硬阻断，不对 password/api_key 字样做泛化拦截，
# 避免测试代码/配置模板产生大量误报。
HARD_SECRET_MARKERS = (
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "-----BEGIN DSA PRIVATE KEY-----",
)

# 解码顺序。
TEXT_ENCODINGS = (
    "utf-8-sig",
    "utf-8",
    "gb18030",
)

# Bundle 边界。若源文件正文中出现这些标记，则 fail-closed，避免重建歧义。
FILE_BEGIN = "<<<QCFP_BUNDLE_FILE_BEGIN_v2>>>"
CONTENT_BEGIN = "<<<QCFP_BUNDLE_CONTENT_BEGIN_v2>>>"
CONTENT_END = "<<<QCFP_BUNDLE_CONTENT_END_v2>>>"
FILE_END = "<<<QCFP_BUNDLE_FILE_END_v2>>>"

BUNDLE_SCHEMA = "QCFP-SOURCE-BUNDLE-2"


# ============================================================================
# 3. 数据结构
# ============================================================================

@dataclass
class FileRecord:
    path: str
    source_sha256: str
    content_sha256: str
    size_bytes: int
    encoding: str
    line_count: int
    char_count: int


@dataclass
class Problem:
    path: str
    kind: str
    reason: str


# ============================================================================
# 4. 通用 Helper
# ============================================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(obj) -> str:
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def manifest_hash(records: list[FileRecord]) -> str:
    payload = [asdict(r) for r in records]
    return sha256_text(canonical_json(payload))


def profile_scan_targets(profile: str) -> list[str]:
    """M1：未知 Profile 直接 fail-closed。"""
    if profile not in SCAN_PROFILES:
        raise ValueError(
            f"未知 Scan Profile: {profile!r}；"
            f"可用: {sorted(SCAN_PROFILES)}"
        )
    return list(SCAN_PROFILES[profile])


def normalize_scan_targets(scan_targets) -> list[str]:
    return sorted(
        str(t).replace("\\", "/")
        for t in scan_targets
    )


def build_scope_manifest(profile: str, scan_targets) -> dict:
    """M2：Scope Manifest —— 承诺「扫描什么」。"""
    return {
        "bundle_schema": BUNDLE_SCHEMA,
        "bundle_profile": profile,
        "scan_targets": normalize_scan_targets(scan_targets),
        "exclude_dirs": sorted(EXCLUDE_DIRS),
        "safe_special_files": sorted(SAFE_SPECIAL_FILES),
        "exclude_patterns": sorted(EXCLUDE_PATTERNS),
    }


def scope_manifest_hash(profile: str, scan_targets) -> str:
    """SCOPE_MANIFEST_SHA256 = sha256(canonical(scope_manifest))。"""
    return sha256_text(
        canonical_json(build_scope_manifest(profile, scan_targets))
    )


def bundle_root_hash(scope_sha256: str, file_manifest_sha256: str) -> str:
    """BUNDLE_ROOT_SHA256 绑定 Scope + Files 两个语义完全不同的 Hash。"""
    return sha256_text(canonical_json({
        "scope_manifest_sha256": scope_sha256,
        "file_manifest_sha256": file_manifest_sha256,
    }))


def output_for_profile(output_file: Path, profile: str) -> Path:
    """merged_code_QCFP-MTF.txt → merged_code_QCFP-MTF.<profile>.txt。"""
    return output_file.with_name(
        f"{output_file.stem}.{profile}{output_file.suffix}"
    )


def normalize_rel_path(path: Path, project_root: Path) -> str:
    return path.relative_to(project_root).as_posix()


def is_within(child: Path, parent: Path) -> bool:
    """跨平台判断 child 是否位于 parent 内。"""
    try:
        child_resolved = child.resolve(strict=False)
        parent_resolved = parent.resolve(strict=False)
        common = os.path.commonpath(
            [str(child_resolved), str(parent_resolved)]
        )
        return Path(common) == parent_resolved
    except (ValueError, OSError):
        return False


def is_sensitive_filename(filename: str) -> bool:
    name = filename.lower()

    # 明确允许 .env.example / .env.sample。
    if name in {".env.example", ".env.sample"}:
        return False

    if name in SENSITIVE_FILE_NAMES:
        return True

    # .env.local / .env.production / .env.dev 等默认拒绝。
    if name.startswith(".env."):
        return True

    suffix = Path(name).suffix.lower()
    if suffix in SENSITIVE_SUFFIXES:
        return True

    return False


def matches_exclude_pattern(filename: str) -> bool:
    name = filename.lower()
    return any(
        fnmatch.fnmatch(name, pattern.lower())
        for pattern in EXCLUDE_PATTERNS
    )


def should_include_by_name(filename: str) -> bool:
    """固定优先级：Sensitive DENY → Pattern DENY → Special ALLOW → Suffix ALLOW."""
    name = filename.lower()

    if is_sensitive_filename(name):
        return False

    if matches_exclude_pattern(name):
        return False

    if name in SAFE_SPECIAL_FILES:
        return True

    return Path(name).suffix.lower() in INCLUDE_EXTENSIONS


def decode_text(raw: bytes) -> tuple[Optional[str], Optional[str]]:
    """M3：仅 BOM 时标 utf-8-sig；普通 UTF-8 标 utf-8；GB18030 兜底。

    不使用 errors=ignore/replace；无法解码返回 (None, None) →
    调用方按 DECODE_ERROR → INCOMPLETE 处理。"""
    if raw.startswith(codecs.BOM_UTF8):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("gb18030"), "gb18030"
    except UnicodeDecodeError:
        pass
    return None, None


def line_count_of(content: str) -> int:
    if not content:
        return 0
    return content.count("\n") + (0 if content.endswith("\n") else 1)


def contains_hard_secret(content: str) -> Optional[str]:
    for marker in HARD_SECRET_MARKERS:
        if marker in content:
            return marker
    return None


def has_bundle_marker_collision(content: str) -> bool:
    return any(
        marker in content
        for marker in (FILE_BEGIN, CONTENT_BEGIN, CONTENT_END, FILE_END)
    )


def atomic_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ============================================================================
# 5. 扫描 Candidate
# ============================================================================

def resolve_scan_target(project_root: Path, target: str | Path) -> Path:
    p = Path(target)
    if not p.is_absolute():
        p = project_root / p
    return p.resolve(strict=False)


def collect_candidates(
    project_root: Path,
    scan_targets: Iterable[str | Path],
    output_file: Path,
) -> tuple[list[Path], list[Problem], list[Problem]]:
    """
    返回：
      candidates
      scan_errors
      security_exclusions
    """
    candidates: dict[str, Path] = {}
    scan_errors: list[Problem] = []
    security_exclusions: list[Problem] = []

    project_root = project_root.resolve(strict=False)
    output_abs = output_file.resolve(strict=False)
    incomplete_abs = output_file.with_name(
        output_file.stem + ".incomplete" + output_file.suffix
    ).resolve(strict=False)

    def consider_file(path: Path, requested_directly: bool = False) -> None:
        rel_display = str(path)

        if not is_within(path, project_root):
            scan_errors.append(Problem(
                path=rel_display,
                kind="PATH_ESCAPE",
                reason="文件位于 PROJECT_ROOT 之外",
            ))
            return

        rel = normalize_rel_path(path.resolve(strict=False), project_root)

        # 当前输出和可能存在的 incomplete 输出绝不作为输入。
        resolved = path.resolve(strict=False)
        if resolved in {output_abs, incomplete_abs}:
            return

        if path.is_symlink():
            # 若这是本来会进入 Bundle 的源码，则视为不完整；
            # symlink 可能越界，不能静默跟随。
            if requested_directly or should_include_by_name(path.name):
                scan_errors.append(Problem(
                    path=rel,
                    kind="SYMLINK_SOURCE_BLOCKED",
                    reason="源码文件是 symbolic link；为防路径逃逸不跟随",
                ))
            return

        if is_sensitive_filename(path.name):
            security_exclusions.append(Problem(
                path=rel,
                kind="SENSITIVE_FILENAME",
                reason="敏感文件名规则命中",
            ))
            return

        if matches_exclude_pattern(path.name):
            if requested_directly:
                scan_errors.append(Problem(
                    path=rel,
                    kind="REQUESTED_TARGET_EXCLUDED",
                    reason="请求的文件命中 EXCLUDE_PATTERNS",
                ))
            return

        if not should_include_by_name(path.name):
            if requested_directly:
                scan_errors.append(Problem(
                    path=rel,
                    kind="REQUESTED_TARGET_UNSUPPORTED",
                    reason="请求的文件不在允许的文本/代码类型中",
                ))
            return

        candidates[rel] = path

    for target in scan_targets:
        target_path = resolve_scan_target(project_root, target)

        if not is_within(target_path, project_root):
            scan_errors.append(Problem(
                path=str(target),
                kind="SCAN_TARGET_OUTSIDE_PROJECT",
                reason="扫描目标位于 PROJECT_ROOT 之外",
            ))
            continue

        if not target_path.exists():
            scan_errors.append(Problem(
                path=str(target),
                kind="SCAN_TARGET_MISSING",
                reason="扫描目标不存在",
            ))
            continue

        if target_path.is_symlink():
            scan_errors.append(Problem(
                path=normalize_rel_path(target_path, project_root),
                kind="SCAN_TARGET_SYMLINK_BLOCKED",
                reason="扫描目标是 symbolic link",
            ))
            continue

        if target_path.is_file():
            consider_file(target_path, requested_directly=True)
            continue

        for root, dirs, files in os.walk(
            target_path,
            topdown=True,
            followlinks=False,
        ):
            root_path = Path(root)

            # 原地剪枝。
            kept_dirs: list[str] = []
            for d in dirs:
                d_path = root_path / d

                if d.lower() in EXCLUDE_DIRS:
                    continue

                if d_path.is_symlink():
                    rel = normalize_rel_path(
                        d_path.resolve(strict=False),
                        project_root,
                    ) if is_within(d_path, project_root) else str(d_path)

                    scan_errors.append(Problem(
                        path=rel,
                        kind="SYMLINK_DIR_BLOCKED",
                        reason="目录 symbolic link 被阻止",
                    ))
                    continue

                kept_dirs.append(d)

            dirs[:] = kept_dirs

            for filename in files:
                consider_file(root_path / filename)

    result = sorted(
        candidates.values(),
        key=lambda p: normalize_rel_path(
            p.resolve(strict=False),
            project_root,
        ).lower(),
    )

    if not result:
        scan_errors.append(Problem(
            path="",
            kind="NO_CANDIDATE_FILES",
            reason="没有发现可合并的候选文件",
        ))

    return result, scan_errors, security_exclusions


# ============================================================================
# 6. Bundle 写入
# ============================================================================

def write_file_entry(
    out_f,
    project_root: Path,
    path: Path,
) -> tuple[Optional[FileRecord], Optional[Problem]]:
    rel = normalize_rel_path(path.resolve(strict=False), project_root)

    try:
        stat_before = path.stat()
        raw = path.read_bytes()
        stat_after = path.stat()
    except Exception as exc:
        return None, Problem(
            path=rel,
            kind="READ_ERROR",
            reason=f"{type(exc).__name__}: {exc}",
        )

    # 读取期间发生变化，拒绝把不稳定快照当成完整证据。
    if (
        stat_before.st_size != stat_after.st_size
        or stat_before.st_mtime_ns != stat_after.st_mtime_ns
    ):
        return None, Problem(
            path=rel,
            kind="SOURCE_CHANGED_DURING_READ",
            reason="文件在读取期间发生变化",
        )

    if MAX_FILE_SIZE_BYTES is not None and len(raw) > MAX_FILE_SIZE_BYTES:
        return None, Problem(
            path=rel,
            kind="FILE_TOO_LARGE",
            reason=f"{len(raw)} bytes > MAX_FILE_SIZE_BYTES={MAX_FILE_SIZE_BYTES}",
        )

    if b"\x00" in raw:
        return None, Problem(
            path=rel,
            kind="BINARY_CONTENT",
            reason="检测到 NUL 字节，按二进制文件处理",
        )

    content, encoding = decode_text(raw)
    if content is None or encoding is None:
        return None, Problem(
            path=rel,
            kind="DECODE_ERROR",
            reason=f"无法使用 {TEXT_ENCODINGS} 解码",
        )

    secret_marker = contains_hard_secret(content)
    if secret_marker:
        return None, Problem(
            path=rel,
            kind="HARD_SECRET_BLOCKED",
            reason=f"命中私钥/敏感内容标记: {secret_marker}",
        )

    if has_bundle_marker_collision(content):
        return None, Problem(
            path=rel,
            kind="BUNDLE_MARKER_COLLISION",
            reason="源文件正文包含 Bundle 控制标记，无法安全无歧义封装",
        )

    record = FileRecord(
        path=rel,
        source_sha256=sha256_bytes(raw),
        content_sha256=sha256_text(content),
        size_bytes=len(raw),
        encoding=encoding,
        line_count=line_count_of(content),
        char_count=len(content),
    )

    out_f.write(FILE_BEGIN + "\n")
    out_f.write(f"path: {record.path}\n")
    out_f.write(f"source_sha256: {record.source_sha256}\n")
    out_f.write(f"content_sha256: {record.content_sha256}\n")
    out_f.write(f"size_bytes: {record.size_bytes}\n")
    out_f.write(f"encoding: {record.encoding}\n")
    out_f.write(f"line_count: {record.line_count}\n")
    out_f.write(f"char_count: {record.char_count}\n")
    out_f.write(CONTENT_BEGIN + "\n")

    out_f.write(content)
    if content and not content.endswith("\n"):
        out_f.write("\n")

    out_f.write(CONTENT_END + "\n")
    out_f.write(f"path: {record.path}\n")
    out_f.write(FILE_END + "\n\n")

    return record, None


def verify_sources_after_write(
    project_root: Path,
    records: list[FileRecord],
) -> list[Problem]:
    problems: list[Problem] = []

    if not VERIFY_SOURCE_AFTER_WRITE:
        return problems

    for record in records:
        path = project_root / Path(record.path)

        try:
            raw = path.read_bytes()
        except Exception as exc:
            problems.append(Problem(
                path=record.path,
                kind="POST_WRITE_READ_ERROR",
                reason=f"{type(exc).__name__}: {exc}",
            ))
            continue

        current_hash = sha256_bytes(raw)
        if current_hash != record.source_sha256:
            problems.append(Problem(
                path=record.path,
                kind="SOURCE_CHANGED_AFTER_CAPTURE",
                reason=(
                    f"captured={record.source_sha256}, "
                    f"current={current_hash}"
                ),
            ))

    return problems


def build_footer(
    records: list[FileRecord],
    scan_errors: list[Problem],
    merge_errors: list[Problem],
    integrity_errors: list[Problem],
    security_exclusions: list[Problem],
    profile: str,
    scope_sha256: str,
) -> tuple[dict, str]:
    incomplete_reasons = (
        list(scan_errors)
        + list(merge_errors)
        + list(integrity_errors)
    )

    status = "COMPLETE" if not incomplete_reasons else "INCOMPLETE"
    m_hash = manifest_hash(records)
    root_hash = bundle_root_hash(scope_sha256, m_hash)

    footer = {
        "schema": "QCFP-SOURCE-BUNDLE-MANIFEST-2",
        "bundle_schema": BUNDLE_SCHEMA,
        "bundle_profile": profile,
        "bundle_status": status,
        "merged_file_count": len(records),
        "scan_error_count": len(scan_errors),
        "merge_error_count": len(merge_errors),
        "integrity_error_count": len(integrity_errors),
        "security_exclusion_count": len(security_exclusions),
        "scope_manifest_sha256": scope_sha256,
        "manifest_sha256": m_hash,
        "bundle_root_sha256": root_hash,
        "records": [asdict(r) for r in records],
        "scan_errors": [asdict(x) for x in scan_errors],
        "merge_errors": [asdict(x) for x in merge_errors],
        "integrity_errors": [asdict(x) for x in integrity_errors],
        "security_exclusions": [
            asdict(x) for x in security_exclusions
        ],
    }
    return footer, status


def write_bundle(
    project_root: Path,
    scan_targets: Iterable[str | Path],
    output_file: Path,
    profile: str | None = None,
) -> tuple[Path, dict]:
    project_root = project_root.resolve(strict=False)
    output_file = output_file.resolve(strict=False)
    scan_targets = list(scan_targets)
    profile = profile or DEFAULT_PROFILE
    profile_scan_targets(profile)  # 未知 Profile fail-closed
    scope_sha256 = scope_manifest_hash(profile, scan_targets)

    if not project_root.exists() or not project_root.is_dir():
        raise FileNotFoundError(
            f"PROJECT_ROOT 不存在或不是目录: {project_root}"
        )

    output_file.parent.mkdir(parents=True, exist_ok=True)

    candidates, scan_errors, security_exclusions = collect_candidates(
        project_root,
        scan_targets,
        output_file,
    )

    records: list[FileRecord] = []
    merge_errors: list[Problem] = []

    fd, tmp_name = tempfile.mkstemp(
        prefix=output_file.name + ".",
        suffix=".tmp",
        dir=str(output_file.parent),
    )
    tmp_path = Path(tmp_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out_f:
            out_f.write("=" * 80 + "\n")
            out_f.write("QCFP-MTF Project Source Bundle\n")
            out_f.write(f"bundle_schema: {BUNDLE_SCHEMA}\n")
            out_f.write(f"bundle_profile: {profile}\n")
            out_f.write("bundle_status: PENDING (final status in footer)\n")
            out_f.write(f"generated_at_utc: {utc_now()}\n")
            out_f.write(f"project_root: {project_root}\n")
            out_f.write(
                "scan_targets: "
                + json.dumps(
                    [str(x) for x in scan_targets],
                    ensure_ascii=False,
                )
                + "\n"
            )
            out_f.write(f"discovered_candidate_files: {len(candidates)}\n")
            out_f.write(
                f"security_exclusions: {len(security_exclusions)}\n"
            )
            out_f.write("=" * 80 + "\n\n")

            for index, path in enumerate(candidates, start=1):
                record, problem = write_file_entry(
                    out_f,
                    project_root,
                    path,
                )

                rel = normalize_rel_path(
                    path.resolve(strict=False),
                    project_root,
                )

                if problem:
                    merge_errors.append(problem)
                    print(
                        f"[SKIP {index}/{len(candidates)}] "
                        f"{rel} -> {problem.kind}: {problem.reason}"
                    )
                    continue

                assert record is not None
                records.append(record)
                print(
                    f"[OK {index}/{len(candidates)}] {record.path}"
                )

            # 在 Footer 写出前复核：源文件在合并期间是否变化。
            integrity_errors = verify_sources_after_write(
                project_root,
                records,
            )

            footer, status = build_footer(
                records=records,
                scan_errors=scan_errors,
                merge_errors=merge_errors,
                integrity_errors=integrity_errors,
                security_exclusions=security_exclusions,
                profile=profile,
                scope_sha256=scope_sha256,
            )

            out_f.write("=" * 80 + "\n")
            out_f.write("QCFP_BUNDLE_FOOTER\n")
            out_f.write(f"BUNDLE_SCHEMA: {BUNDLE_SCHEMA}\n")
            out_f.write(f"BUNDLE_PROFILE: {profile}\n")
            out_f.write(f"BUNDLE_STATUS: {status}\n")
            out_f.write(f"MERGED_FILES: {len(records)}\n")
            out_f.write(f"SCAN_ERRORS: {len(scan_errors)}\n")
            out_f.write(f"MERGE_ERRORS: {len(merge_errors)}\n")
            out_f.write(
                f"INTEGRITY_ERRORS: {len(integrity_errors)}\n"
            )
            out_f.write(
                f"SECURITY_EXCLUSIONS: {len(security_exclusions)}\n"
            )
            out_f.write(
                f"SCOPE_MANIFEST_SHA256: "
                f"{footer['scope_manifest_sha256']}\n"
            )
            out_f.write(
                f"MANIFEST_SHA256: {footer['manifest_sha256']}\n"
            )
            out_f.write(
                f"BUNDLE_ROOT_SHA256: {footer['bundle_root_sha256']}\n"
            )

            if scan_errors:
                out_f.write("\n[SCAN_ERRORS]\n")
                for p in scan_errors:
                    out_f.write(
                        f"- {p.path} | {p.kind} | {p.reason}\n"
                    )

            if merge_errors:
                out_f.write("\n[MERGE_ERRORS]\n")
                for p in merge_errors:
                    out_f.write(
                        f"- {p.path} | {p.kind} | {p.reason}\n"
                    )

            if integrity_errors:
                out_f.write("\n[INTEGRITY_ERRORS]\n")
                for p in integrity_errors:
                    out_f.write(
                        f"- {p.path} | {p.kind} | {p.reason}\n"
                    )

            if security_exclusions:
                out_f.write("\n[SECURITY_EXCLUSIONS]\n")
                for p in security_exclusions:
                    out_f.write(
                        f"- {p.path} | {p.kind} | {p.reason}\n"
                    )

            out_f.write("\nQCFP_BUNDLE_COMPLETE: ")
            out_f.write("TRUE\n" if status == "COMPLETE" else "FALSE\n")
            out_f.write("=" * 80 + "\n")

            out_f.flush()
            os.fsync(out_f.fileno())

        # STRICT：不完整 Bundle 不覆盖正式输出。
        if status == "COMPLETE" or not STRICT_MODE:
            final_path = output_file
        else:
            final_path = output_file.with_name(
                output_file.stem + ".incomplete" + output_file.suffix
            )

        os.replace(tmp_path, final_path)

        bundle_file_sha256 = sha256_bytes(final_path.read_bytes())
        footer["bundle_file"] = str(final_path)
        footer["bundle_file_sha256"] = bundle_file_sha256
        footer["generated_at_utc"] = utc_now()
        footer["project_root"] = str(project_root)
        footer["scan_targets"] = [str(x) for x in scan_targets]
        footer["strict_mode"] = STRICT_MODE

        if WRITE_SIDECAR_MANIFEST:
            if final_path == output_file:
                manifest_path = output_file.with_name(
                    output_file.stem + ".manifest.json"
                )
            else:
                manifest_path = output_file.with_name(
                    output_file.stem + ".incomplete.manifest.json"
                )

            atomic_write_json(manifest_path, footer)
            footer["sidecar_manifest"] = str(manifest_path)

        return final_path, footer

    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise


# ============================================================================
# 7. Main
# ============================================================================

def parse_bundle_text(text: str) -> dict:
    """解析 Bundle 文本（离线，不依赖项目源目录）。

    返回：header / records / footer_fields / boundary / problems。
    """
    problems: list[str] = []
    header: dict = {}
    footer_fields: dict = {}
    records: list[FileRecord] = []

    boundary = {
        FILE_BEGIN: text.count(FILE_BEGIN),
        CONTENT_BEGIN: text.count(CONTENT_BEGIN),
        CONTENT_END: text.count(CONTENT_END),
        FILE_END: text.count(FILE_END),
    }

    # Header：第一个 FILE_BEGIN 之前
    first_file = text.find(FILE_BEGIN)
    if first_file == -1:
        problems.append("缺少 FILE_BEGIN 标记")
        return {"header": header, "records": records,
                "footer_fields": footer_fields,
                "boundary": boundary, "problems": problems}
    header_text = text[:first_file]
    for line in header_text.splitlines():
        if ":" in line and not line.startswith("=") \
                and "QCFP-MTF Project Source Bundle" not in line:
            key, _, value = line.partition(":")
            header[key.strip()] = value.strip()
    if header.get("scan_targets"):
        try:
            header["scan_targets"] = json.loads(header["scan_targets"])
        except json.JSONDecodeError:
            problems.append("scan_targets 头解析失败")

    # Footer：QCFP_BUNDLE_FOOTER 之后
    footer_start = text.find("QCFP_BUNDLE_FOOTER")
    if footer_start == -1:
        problems.append("缺少 QCFP_BUNDLE_FOOTER")
    else:
        for line in text[footer_start:].splitlines():
            if ":" in line and not line.startswith("=") \
                    and line.strip() != "QCFP_BUNDLE_FOOTER":
                key, _, value = line.partition(":")
                footer_fields[key.strip()] = value.strip()

    # 文件块
    cursor = first_file
    seen_paths: set[str] = set()
    while True:
        begin = text.find(FILE_BEGIN, cursor)
        if begin == -1:
            break
        end = text.find(FILE_END, begin)
        if end == -1:
            problems.append("FILE_END 缺失")
            break
        block = text[begin:end + len(FILE_END)]
        cursor = end + len(FILE_END)

        meta_end = block.find(CONTENT_BEGIN)
        content_end = block.find(CONTENT_END)
        if meta_end == -1 or content_end == -1:
            problems.append("CONTENT_BEGIN/CONTENT_END 缺失")
            continue
        meta = block[:meta_end]
        content_written = block[meta_end + len(CONTENT_BEGIN):content_end]
        meta_fields: dict = {}
        for line in meta.splitlines():
            if line.startswith(FILE_BEGIN) or line.startswith(CONTENT_BEGIN):
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                meta_fields[key.strip()] = value.strip()
        try:
            record = FileRecord(
                path=meta_fields["path"],
                source_sha256=meta_fields["source_sha256"],
                content_sha256=meta_fields["content_sha256"],
                size_bytes=int(meta_fields["size_bytes"]),
                encoding=meta_fields["encoding"],
                line_count=int(meta_fields["line_count"]),
                char_count=int(meta_fields["char_count"]),
            )
        except (KeyError, ValueError) as exc:
            problems.append(f"文件块元数据非法: {exc}")
            continue
        if record.path in seen_paths:
            problems.append(f"重复 path: {record.path}")
        seen_paths.add(record.path)
        records.append(record)
        # 尾部 path 行应与块头一致
        if f"path: {record.path}" not in block[content_end:]:
            problems.append(f"尾部 path 不一致: {record.path}")

    return {"header": header, "records": records,
            "footer_fields": footer_fields,
            "boundary": boundary, "problems": problems}


def verify_bundle(
    bundle_path: Path,
    manifest_path: Path | None = None,
) -> dict:
    """M4：离线验证 Bundle + Sidecar（不依赖项目源目录）。"""
    checks: dict[str, str] = {}
    bundle_path = Path(bundle_path)
    if not bundle_path.exists():
        return {"verdict": "BUNDLE_VERIFICATION_FAILED",
                "checks": {"Bundle exists": "FAIL"},
                "problems": ["bundle 文件不存在"]}

    if manifest_path is None:
        manifest_path = bundle_path.with_name(
            bundle_path.stem + ".manifest.json"
        )
    if not manifest_path.exists():
        return {"verdict": "BUNDLE_VERIFICATION_FAILED",
                "checks": {"Sidecar exists": "FAIL"},
                "problems": [f"sidecar manifest 不存在: {manifest_path}"]}

    try:
        sidecar = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"verdict": "BUNDLE_VERIFICATION_FAILED",
                "checks": {"Sidecar parse": "FAIL"},
                "problems": [f"sidecar 解析失败: {exc}"]}

    raw = bundle_path.read_bytes()
    text = raw.decode("utf-8")
    parsed = parse_bundle_text(text)
    problems = list(parsed["problems"])
    records = parsed["records"]
    header = parsed["header"]
    footer = parsed["footer_fields"]

    # 1. Footer 存在
    checks["Footer exists"] = "PASS" if "BUNDLE_SCHEMA" in footer \
        else "FAIL"
    if checks["Footer exists"] == "FAIL":
        problems.append("footer 缺失")
    # 2. Schema / Status
    checks["Schema"] = "PASS" if footer.get("BUNDLE_SCHEMA") == \
        BUNDLE_SCHEMA else "FAIL"
    checks["Status"] = "PASS" if footer.get("BUNDLE_STATUS") == "COMPLETE" \
        and footer.get("QCFP_BUNDLE_COMPLETE") == "TRUE" else "FAIL"
    # 3. Boundary integrity
    counts = parsed["boundary"]
    boundary_ok = len({counts[k] for k in
                       (FILE_BEGIN, CONTENT_BEGIN, CONTENT_END, FILE_END)}) \
        == 1 and counts[FILE_BEGIN] == len(records)
    checks["Boundary Integrity"] = "PASS" if boundary_ok else "FAIL"
    if not boundary_ok:
        problems.append(f"边界计数不一致: {counts}")
    # 4. 每文件 content hash / char_count / line_count
    content_ok = 0
    for record in records:
        content_written = _content_of_record(text, record)
        if content_written is None:
            problems.append(f"无法定位内容: {record.path}")
            continue
        original = content_written
        if original.endswith("\n") and len(original) - 1 == record.char_count:
            original = original[:-1]
        if sha256_text(original) != record.content_sha256:
            problems.append(f"content hash 不匹配: {record.path}")
            continue
        if len(original) != record.char_count \
                or line_count_of(original) != record.line_count:
            problems.append(f"char/line 计数不匹配: {record.path}")
            continue
        content_ok += 1
    checks["Content Hash"] = f"{content_ok}/{len(records)}"
    # 5. Manifest hash（从块重建）
    checks["Manifest Hash"] = "PASS" if manifest_hash(records) == \
        footer.get("MANIFEST_SHA256") else "FAIL"
    if checks["Manifest Hash"] == "FAIL":
        problems.append("MANIFEST_SHA256 不匹配")
    # 6. Scope hash（header profile + scan_targets + 模块常量）
    profile = header.get("bundle_profile", "")
    scan_targets = header.get("scan_targets") or []
    scope_ok = scope_manifest_hash(profile, scan_targets) == \
        footer.get("SCOPE_MANIFEST_SHA256")
    checks["Scope Hash"] = "PASS" if scope_ok else "FAIL"
    if not scope_ok:
        problems.append("SCOPE_MANIFEST_SHA256 不匹配")
    # 7. Bundle root
    root_ok = bundle_root_hash(
        footer.get("SCOPE_MANIFEST_SHA256", ""),
        footer.get("MANIFEST_SHA256", ""),
    ) == footer.get("BUNDLE_ROOT_SHA256")
    checks["Bundle Root"] = "PASS" if root_ok else "FAIL"
    if not root_ok:
        problems.append("BUNDLE_ROOT_SHA256 不匹配")
    # 8. 整文件 SHA == sidecar
    whole_ok = sha256_bytes(raw) == sidecar.get("bundle_file_sha256")
    checks["Bundle File SHA256"] = "PASS" if whole_ok else "FAIL"
    if not whole_ok:
        problems.append("整文件 SHA256 与 sidecar 不一致")

    checks["Profile"] = profile or "MISSING"
    checks["File Count"] = f"{len(records)}/{len(records)}"

    failed = any(v == "FAIL" for v in checks.values()
                 if isinstance(v, str))
    return {
        "verdict": "BUNDLE_VERIFIED" if not failed and not problems
        else "BUNDLE_VERIFICATION_FAILED",
        "checks": checks,
        "problems": problems,
        "profile": profile,
        "file_count": len(records),
    }


def _content_of_record(text: str, record: FileRecord) -> str | None:
    """从文本中取出某记录 CONTENT_BEGIN..CONTENT_END 的内容。"""
    marker = f"path: {record.path}\n"
    start = text.find(marker)
    if start == -1:
        return None
    begin = text.find(CONTENT_BEGIN, start)
    end = text.find(CONTENT_END, begin)
    if begin == -1 or end == -1:
        return None
    content = text[begin + len(CONTENT_BEGIN):end]
    # CONTENT_BEGIN 标记行自带换行；去掉前导 \n 还原实际内容
    if content.startswith("\n"):
        content = content[1:]
    return content


def print_verification(result: dict) -> None:
    print("QCFP Bundle Verification")
    print("────────────────────────")
    checks = result.get("checks", {})
    for key, value in checks.items():
        print(f"{key:<20} {value}")
    for problem in result.get("problems", []):
        print(f"  [FAIL] {problem}")
    print("\nVERDICT:")
    print(result["verdict"])


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="QCFP-MTF Project Source Bundle Builder / Verifier"
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        choices=sorted(SCAN_PROFILES),
        help="Scan Profile（默认 code-review）",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_FILE),
        help="输出基础文件名（自动按 Profile 追加后缀）",
    )
    parser.add_argument(
        "--verify",
        metavar="BUNDLE",
        help="离线验证 Bundle（不依赖项目源目录）",
    )
    parser.add_argument(
        "--manifest",
        help="Verify 时使用的 sidecar manifest（缺省按同名 .manifest.json）",
    )
    args = parser.parse_args(argv)

    if args.verify:
        result = verify_bundle(
            Path(args.verify),
            Path(args.manifest) if args.manifest else None,
        )
        print_verification(result)
        return 0 if result["verdict"] == "BUNDLE_VERIFIED" else 1

    profile = args.profile
    output_file = output_for_profile(Path(args.output), profile)

    print("=" * 80)
    print("QCFP-MTF Project Source Bundle Builder")
    print("=" * 80)
    print(f"Project Root : {PROJECT_ROOT}")
    print(f"Profile      : {profile}")
    print(f"Output       : {output_file}")
    print(f"Strict Mode  : {STRICT_MODE}")
    print("Scan Targets :")
    for target in profile_scan_targets(profile):
        print(f"  - {target}")
    print("=" * 80)

    try:
        final_path, footer = write_bundle(
            project_root=PROJECT_ROOT,
            scan_targets=profile_scan_targets(profile),
            output_file=output_file,
            profile=profile,
        )
    except Exception as exc:
        print(
            f"\n[FATAL] 合并失败: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    size = final_path.stat().st_size
    total_chars = sum(
        r["char_count"]
        for r in footer["records"]
    )
    rough_tokens = total_chars // 3

    print("\n" + "=" * 80)
    print("合并结束")
    print(f"BUNDLE_STATUS      : {footer['bundle_status']}")
    print(f"MERGED_FILES       : {footer['merged_file_count']}")
    print(f"SCAN_ERRORS        : {footer['scan_error_count']}")
    print(f"MERGE_ERRORS       : {footer['merge_error_count']}")
    print(f"INTEGRITY_ERRORS   : {footer['integrity_error_count']}")
    print(
        f"SECURITY_EXCLUSIONS: "
        f"{footer['security_exclusion_count']}"
    )
    print(f"MANIFEST_SHA256    : {footer['manifest_sha256']}")
    print(f"SCOPE_MANIFEST_SHA256: {footer['scope_manifest_sha256']}")
    print(f"BUNDLE_ROOT_SHA256  : {footer['bundle_root_sha256']}")
    print(f"BUNDLE_SHA256      : {footer['bundle_file_sha256']}")
    print(f"输出文件           : {final_path}")

    if footer.get("sidecar_manifest"):
        print(f"Manifest           : {footer['sidecar_manifest']}")

    if size >= 1024 * 1024:
        print(f"文件大小           : {size / (1024 * 1024):.2f} MB")
    elif size >= 1024:
        print(f"文件大小           : {size / 1024:.2f} KB")
    else:
        print(f"文件大小           : {size} bytes")

    print(f"总字符数           : {total_chars:,}")
    print(
        f"粗略 Token 估算    : ~{rough_tokens:,} "
        "(仅供参考，不作为精确额度)"
    )

    if footer["bundle_status"] == "COMPLETE":
        print("\n[PASS] Bundle 完整，可用于代码审查。")
        print(
            "建议上传合并 TXT；正式治理验收时同时保留本地 "
            "Manifest SHA256。"
        )
        return 0

    print("\n[NOT_PROVEN] Bundle 不完整。")
    if STRICT_MODE:
        print(
            "STRICT_MODE=True：未覆盖正式输出，"
            "不完整结果已写入 *.incomplete.txt。"
        )
    print(
        "请先处理 Footer / Manifest 中的 SCAN_ERRORS、"
        "MERGE_ERRORS、INTEGRITY_ERRORS，再用于正式验收。"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
