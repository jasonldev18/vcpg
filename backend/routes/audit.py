from typing import Any

from fastapi import APIRouter

from backend.audit import runner

router = APIRouter(prefix="/api/audit")


@router.get("")
def state() -> dict[str, Any]:
    return runner.view()


@router.post("/run")
async def run_deep_scan() -> dict[str, Any]:
    """Manual deep scan from the audit bay; it runs in the background."""
    runner.start("deep")
    return runner.view()
