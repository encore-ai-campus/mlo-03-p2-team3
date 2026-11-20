"""Bronze 입력 설정. 상대 경로는 이 프로젝트 루트 기준입니다."""
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"  # 매핑 규칙서: YYYY-MM-DD HH:MI:SS


@dataclass(frozen=True)
class FileRule:
    pattern: str = "**/*"  # source_root 기준 파일 경로 또는 glob
    sheet_names: tuple[str | int, ...] | None = None  # None: Excel 모든 시트
    usecols: tuple[str, ...] | None = None  # None: 모든 원천 컬럼, 지정 시 명시한 순서
    encoding: str = "utf-8-sig"
    delimiter: str = ","
    header: int = 0  # Excel 헤더 행 (0부터)


@dataclass(frozen=True)
class BronzeConfig:
    source_root: Path = PROJECT_ROOT / "data/00_origin"
    output_root: Path = PROJECT_ROOT / "data/01_bronze"
    manifest_path: Path = PROJECT_ROOT / "meta/bronze_ingestion.jsonl"
    rules: tuple[FileRule, ...] = field(default_factory=lambda: (FileRule(),))
    compression: str = "snappy"
    source_file_column: str = "source_file"
    ingested_at_column: str = "ingested_at"  # KST, YYYY-MM-DD HH:MI:SS


CONFIG = BronzeConfig()

# 다른 폴더 예시 (원천 컬럼 선택은 필요할 때만 명시):
# CONFIG = BronzeConfig(
#     source_root=Path("D:/other/input"),
#     output_root=Path("D:/other/01_bronze"),
#     manifest_path=Path("D:/other/meta/bronze_ingestion.jsonl"),
#     rules=(FileRule(pattern="**/*.xlsx", sheet_names=("Sheet1",),
#                     usecols=("원천컬럼1", "원천컬럼2")),),
# )
