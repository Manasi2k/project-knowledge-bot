"""Structured spreadsheet queries. Python computes the numbers, never the language model."""
import io
from dataclasses import dataclass

import pandas as pd

ALLOWED_OPS = {"sum", "mean", "min", "max", "count"}


@dataclass
class AggResult:
    value: float
    rows: list[int]     # spreadsheet row numbers that contributed (header is row 1)
    sheet: str
    column: str


def sheet_names(data: bytes) -> list[str]:
    return pd.ExcelFile(io.BytesIO(data)).sheet_names


def read_sheet(data: bytes, sheet: str) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(data), sheet_name=sheet)


def aggregate(data: bytes, sheet: str, column: str, op: str = "sum",
              where: dict | None = None) -> AggResult:
    """Apply one whitelisted operation to one column, with optional equality filters."""
    if op not in ALLOWED_OPS:
        raise ValueError(f"operation must be one of {sorted(ALLOWED_OPS)}")
    df = read_sheet(data, sheet)
    for col in [column, *(where or {})]:
        if col not in df.columns:
            raise ValueError(f"unknown column '{col}'; this sheet has {list(df.columns)}")
    for col, val in (where or {}).items():
        df = df[df[col] == val]
    value = getattr(df[column], op)()
    value = value.item() if hasattr(value, "item") else value
    return AggResult(value=value, rows=[int(i) + 2 for i in df.index], sheet=sheet, column=column)