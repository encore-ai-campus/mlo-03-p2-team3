"""Run: python -m unittest discover -s tests -v"""
import csv
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from config import BronzeConfig, FileRule
spec = importlib.util.spec_from_file_location("bronze", Path(__file__).resolve().parents[1] / "src/01_bronze.py")
bronze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bronze)


class BronzeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "input"
        (self.source / "nested").mkdir(parents=True)
        self.config = BronzeConfig(self.source, self.root / "bronze", self.root / "meta/history.jsonl")

    def csv(self, name="nested/data.csv", text='id,raw,empty\n001,"  값  ",\n002,NA,-----\n002,NA,-----\n'):
        path = self.source / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_preservation_and_idempotence(self):
        source = self.csv()
        original = source.read_bytes()
        first = bronze.run(self.config)[0]
        output = Path(first["output_path"])
        before = output.stat().st_mtime_ns
        second = bronze.run(self.config)[0]
        self.assertEqual(original, source.read_bytes())
        self.assertEqual(before, output.stat().st_mtime_ns)
        self.assertEqual(first["output_sha256"], second["output_sha256"])
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(pq.read_table(output).select(["id", "raw", "empty"]).to_pylist(), [
            {"id": "001", "raw": "  값  ", "empty": ""},
            {"id": "002", "raw": "NA", "empty": "-----"},
            {"id": "002", "raw": "NA", "empty": "-----"}])
        provenance = pq.read_table(output).select(["source_file", "ingested_at"]).to_pylist()
        self.assertEqual(provenance, [{"source_file": source.name,
                                     "ingested_at": first["data_ingested_at"]}] * 3)
        self.assertEqual(first["data_ingested_at"], second["data_ingested_at"])
        self.assertEqual(first["source_rows"], first["bronze_rows"])
        self.assertRegex(first["saved_at"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        self.assertEqual(len(self.config.manifest_path.read_text(encoding="utf-8").splitlines()), 2)

    def test_excel_sheets_and_columns(self):
        path = self.source / "nested/book.xlsx"
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame({"원문": ["  01  "], "other": ["keep"]}).to_excel(writer, sheet_name="A", index=False)
            pd.DataFrame({"원문": ["002"], "other": ["keep"]}).to_excel(writer, sheet_name="B", index=False)
        config = BronzeConfig(self.source, self.config.output_root, self.config.manifest_path,
                              rules=(FileRule(pattern="**/*.xlsx", sheet_names=("B",), usecols=("원문",)),))
        result = bronze.run(config)[0]
        self.assertEqual(Path(result["output_path"]).relative_to(config.output_root).as_posix(), "nested/book/B.parquet")
        self.assertEqual(pq.read_table(result["output_path"]).select(["원문"]).to_pylist(), [{"원문": "002"}])

    def test_json_fields_in_later_rows_and_nested_preserved(self):
        records = [{"eventType": "A", "announcedAt": "20260523 23:58"},
                   {"eventType": "B", "race": {"rcNo": "01"}, "change": {"before": " A ", "after": ""}},
                   {"eventType": "C", "change": {"reason": "-----"}}]
        (self.source / "events.jsonl").write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        result = bronze.run(self.config)[0]
        rows = pq.read_table(result["output_path"]).to_pylist()
        self.assertEqual(rows[0]["announcedAt"], "20260523 23:58")
        self.assertEqual(rows[1]["race"]["rcNo"], "01")
        self.assertEqual(rows[1]["change"]["before"], " A ")
        self.assertEqual(rows[2]["change"]["reason"], "-----")
        self.assertEqual(result["source_rows"], 3)

    def test_collision_fails_before_writing(self):
        self.csv()
        (self.source / "nested/data.jsonl").write_text('{"a":1}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "충돌"):
            bronze.run(self.config)
        self.assertFalse(self.config.output_root.exists())

    def test_input_output_overlap_rejected(self):
        self.csv()
        with self.assertRaises(ValueError):
            bronze.run(BronzeConfig(self.source, self.source / "bronze", self.config.manifest_path))

    def test_invalid_source_logged_without_overwriting(self):
        self.csv()
        result = bronze.run(self.config)[0]
        output = Path(result["output_path"])
        original = output.read_bytes()
        self.csv(text="id,raw\n1,2,3\n")
        with self.assertRaises(RuntimeError):
            bronze.run(self.config)
        self.assertEqual(original, output.read_bytes())
        record = json.loads(self.config.manifest_path.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(record["status"], "failed")

    def test_provenance_column_collision_fails(self):
        self.csv(text="id,source_file\n001,original\n")
        with self.assertRaises(RuntimeError):
            bronze.run(self.config)
        self.assertFalse((self.config.output_root / "nested/data.parquet").exists())

    def test_changed_source_gets_its_own_collection_time(self):
        from unittest.mock import patch
        self.csv()
        with patch.object(bronze, "now_kst", return_value="2026-11-20 10:00:00"):
            first = bronze.run(self.config)[0]
        self.csv(text="id,raw,empty\n003,new,\n")
        with patch.object(bronze, "now_kst", return_value="2026-11-20 11:00:00"):
            second = bronze.run(self.config)[0]
        self.assertNotEqual(first["source_sha256"], second["source_sha256"])
        self.assertEqual(second["data_ingested_at"], "2026-11-20 11:00:00")

    def test_duplicate_headers_fail_without_renaming(self):
        self.csv(text="id,id\n001,002\n")
        with self.assertRaises(RuntimeError):
            bronze.run(self.config)
        self.assertFalse((self.config.output_root / "nested/data.parquet").exists())


if __name__ == "__main__":
    unittest.main()
