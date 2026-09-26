import time

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.analytics.patterns import mine_patterns
from app.audit import log_event
from app.db import get_db
from app.models import Report, User
from app.security import require_permission
from app.services.analysis_service import analyze_and_store, build_pipeline
from app.services.import_service import MAX_BYTES, OPTIONAL_COLUMNS, REQUIRED_COLUMNS, get_or_create_site, take_pending, validate_csv

router = APIRouter(prefix="/api/imports", tags=["imports"])

TEMPLATE = (
    ",".join(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
    + "\nIMP-0001,Near Miss,2026-05-12,Digboi,GGS-2 Digboi,Pump maintenance,Booster pump,\"During seal replacement the discharge valve was found passing; isolation was not verified and residual pressure was observed. Job stopped.\",Fitter,Contractor-A (synthetic),None,Day,Clear\n"
    + "IMP-0002,Unsafe Condition,2026-05-14,Moran,Warehouse Yard,Inspection,Walkway,\"Housekeeping poor in the warehouse yard, pallets stored on the walkway.\",Storekeeper,,None,Day,Clear\n"
)


@router.get("/template", response_class=PlainTextResponse)
def template(_: User = Depends(require_permission("import"))):
    return PlainTextResponse(TEMPLATE, headers={"Content-Disposition": "attachment; filename=poorvabhas_import_template.csv"}, media_type="text/csv")


@router.post("/validate")
async def validate(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_permission("import"))):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(422, "Upload a .csv file")
    content = await file.read(MAX_BYTES + 1)
    result = validate_csv(db, content, user.id)
    if not result.get("ok"):
        raise HTTPException(422, result.get("error", "Invalid CSV"))
    db.commit()
    return {**result, "filename": file.filename}


@router.post("/{token}/commit")
def commit(token: str, db: Session = Depends(get_db), user: User = Depends(require_permission("import"))):
    rows = take_pending(db, token, user.id)
    if rows is None:
        raise HTTPException(404, "Import session expired - validate the file again")
    t0 = time.time()
    pipeline = build_pipeline(db)
    imported = analysed = sif = review = 0
    ids = []
    for rec in rows:
        site = get_or_create_site(db, rec["site"])
        from datetime import date as _d

        r = Report(report_id=rec["report_id"], report_type=rec["report_type"], date=_d.fromisoformat(rec["date"]), site_id=site.id, location=rec["location"], activity=rec["activity"], equipment=rec.get("equipment"),
                   description=rec["description"], worker_role=rec.get("worker_role"), contractor=rec.get("contractor"), injury_severity=rec.get("injury_severity"), shift=rec.get("shift"), weather=rec.get("weather"),
                   data_source="csv_import", created_by=user.id, status="PENDING")
        db.add(r)
        db.flush()
        imported += 1
        _, out = analyze_and_store(db, r, actor=user, pipeline=pipeline, reason="csv import", audit=False)
        analysed += 1
        sif += out.scl.sif_signal in ("SIF_POTENTIAL", "SIF_EVENT")
        review += bool(out.review_reasons)
        ids.append(r.report_id)
    pat = mine_patterns(db, actor=user) if imported else None
    log_event(db, "IMPORT_COMPLETED", f"CSV import by {user.full_name}: {imported} reports imported and analysed", entity_type="import", entity_id=token[:12], actor=user,
              details={"imported": imported, "sif_signal": sif, "review_required": review, "report_ids": ids[:200]})
    db.commit()
    return {"imported": imported, "analyzed": analysed, "sif_signal": sif, "review_required": review, "report_ids": ids, "patterns": pat, "seconds": round(time.time() - t0, 2)}
