from fastapi import APIRouter

router = APIRouter()

@router.post("/api/")
def sync_employees_route():
    return {"message": "Sync employees route called successfully."}