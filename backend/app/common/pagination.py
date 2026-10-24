"""Common pagination helpers."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


@dataclass
class PageParams:
    limit: int
    offset: int


def page_params(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


def paginate(db: Session, stmt: Select, params: PageParams) -> tuple[list, int]:
    count = db.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one()
    rows = db.execute(stmt.limit(params.limit).offset(params.offset)).scalars().all()
    return list(rows), count
