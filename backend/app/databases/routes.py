"""Structured databases: collections of typed records with properties."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.databases.formula import FormulaError, evaluate
from app.models import (
    Database,
    DatabaseProperty,
    DatabaseRecord,
    DatabaseRecordValue,
    User,
)
from app.security.deps import get_current_user

router = APIRouter(prefix="/databases", tags=["databases"])

PROPERTY_TYPES = {
    "title", "text", "number", "checkbox", "select", "multi_select",
    "date", "person", "url", "relation", "formula",
}


class DatabaseIn(BaseModel):
    name: str
    group_id: str | None = None


class PropertyIn(BaseModel):
    name: str
    prop_type: str = "text"
    options: list[str] | None = None
    formula: str | None = None  # for prop_type == "formula"


class RecordIn(BaseModel):
    values: dict[str, object] = {}


class RecordPatch(BaseModel):
    values: dict[str, object]


def _own(db: Session, user: User, database_id: str) -> Database:
    db_obj = db.get(Database, database_id)
    if db_obj is None or db_obj.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Database not found")
    return db_obj


def _property_out(p: DatabaseProperty) -> dict:
    options = None
    if p.options:
        try:
            options = json.loads(p.options)
        except (ValueError, TypeError):
            options = None
    return {"id": p.id, "name": p.name, "type": p.prop_type, "options": options}


def _record_out(record: DatabaseRecord, values: dict[str, object]) -> dict:
    return {"id": record.id, "values": values, "created_at": record.created_at}


def _db_out(db_obj: Database, props: list[DatabaseProperty], records: list[dict]) -> dict:
    return {
        "id": db_obj.id,
        "name": db_obj.name,
        "properties": [_property_out(p) for p in props],
        "records": records,
    }


def _record_values(db: Session, record_id: str) -> dict[str, object]:
    rows = db.execute(
        select(DatabaseRecordValue).where(DatabaseRecordValue.record_id == record_id)
    ).scalars().all()
    out: dict[str, object] = {}
    for r in rows:
        try:
            out[r.property_id] = json.loads(r.value_json) if r.value_json else None
        except (ValueError, TypeError):
            out[r.property_id] = r.value_json
    return out


@router.get("")
def list_databases(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dbs = db.execute(select(Database).where(Database.owner_id == user.id).order_by(Database.updated_at.desc())).scalars().all()
    return [{"id": d.id, "name": d.name, "created_at": d.created_at} for d in dbs]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_database(body: DatabaseIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_obj = Database(name=body.name, owner_id=user.id, group_id=body.group_id)
    db.add(db_obj)
    db.flush()
    db.add(DatabaseProperty(database_id=db_obj.id, name="Name", prop_type="title", position=0))
    db.commit()
    db.refresh(db_obj)
    return {"id": db_obj.id, "name": db_obj.name}


@router.get("/{database_id}")
def get_database(database_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_obj = _own(db, user, database_id)
    props = list(
        db.execute(
            select(DatabaseProperty).where(DatabaseProperty.database_id == database_id).order_by(DatabaseProperty.position)
        ).scalars()
    )
    records = db.execute(
        select(DatabaseRecord).where(DatabaseRecord.database_id == database_id).order_by(DatabaseRecord.created_at)
    ).scalars().all()

    formula_props = []
    for p in props:
        if p.prop_type == "formula":
            try:
                opts = json.loads(p.options) if p.options else {}
                formula_props.append((p, opts.get("expression", "")))
            except (ValueError, TypeError):
                formula_props.append((p, ""))

    name_by_id = {p.id: p.name for p in props}
    recs = []
    for r in records:
        values = _record_values(db, r.id)
        if formula_props:
            context = {name_by_id[pid]: v for pid, v in values.items() if pid in name_by_id}
            for p, expr in formula_props:
                try:
                    values[p.id] = evaluate(expr, context)
                except FormulaError:
                    values[p.id] = None
        recs.append(_record_out(r, values))
    return _db_out(db_obj, props, recs)


@router.post("/{database_id}/properties", status_code=status.HTTP_201_CREATED)
def add_property(database_id: str, body: PropertyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _own(db, user, database_id)
    if body.prop_type not in PROPERTY_TYPES:
        raise HTTPException(status_code=400, detail="Invalid property type")
    count = db.execute(select(DatabaseProperty).where(DatabaseProperty.database_id == database_id)).scalars().all()
    opts = body.options if body.options else None
    if body.prop_type == "formula":
        opts = json.dumps({"expression": body.formula or ""})
    prop = DatabaseProperty(
        database_id=database_id, name=body.name, prop_type=body.prop_type,
        options=json.dumps(opts) if opts else None,
        position=len(count),
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return _property_out(prop)


@router.delete("/{database_id}/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(database_id: str, property_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _own(db, user, database_id)
    prop = db.get(DatabaseProperty, property_id)
    if prop is None or prop.database_id != database_id:
        raise HTTPException(status_code=404, detail="Property not found")
    db.delete(prop)
    db.commit()
    return None


@router.post("/{database_id}/records", status_code=status.HTTP_201_CREATED)
def add_record(database_id: str, body: RecordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _own(db, user, database_id)
    record = DatabaseRecord(database_id=database_id, created_by=user.id)
    db.add(record)
    db.flush()
    for prop_id, value in body.values.items():
        db.add(DatabaseRecordValue(record_id=record.id, property_id=prop_id, value_json=json.dumps(value)))
    db.commit()
    db.refresh(record)
    return _record_out(record, _record_values(db, record.id))


@router.patch("/{database_id}/records/{record_id}")
def update_record(database_id: str, record_id: str, body: RecordPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _own(db, user, database_id)
    record = db.get(DatabaseRecord, record_id)
    if record is None or record.database_id != database_id:
        raise HTTPException(status_code=404, detail="Record not found")
    existing = {
        r.property_id: r
        for r in db.execute(select(DatabaseRecordValue).where(DatabaseRecordValue.record_id == record_id)).scalars()
    }
    for prop_id, value in body.values.items():
        if prop_id in existing:
            existing[prop_id].value_json = json.dumps(value)
        else:
            db.add(DatabaseRecordValue(record_id=record_id, property_id=prop_id, value_json=json.dumps(value)))
    db.commit()
    return _record_out(record, _record_values(db, record.id))


@router.delete("/{database_id}/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(database_id: str, record_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _own(db, user, database_id)
    record = db.get(DatabaseRecord, record_id)
    if record is None or record.database_id != database_id:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(record)
    db.commit()
    return None
