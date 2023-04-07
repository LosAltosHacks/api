from fastapi import APIRouter, HTTPException, Depends
from pyairtable.api.table import Table
from ..dependencies import get_mobile_table
from ..auth.auth_bearer import JWTBearer
from ..models.mobile_attendee import MobileAttendee, recordToMobileAttendee

router = APIRouter(
    prefix="/mobile", tags=["mobile"], dependencies=[Depends(JWTBearer())]
)

# get list of all attendees
@router.get("/")
async def get_all_attendees(table: Table = Depends(get_mobile_table)):
    res = []
    for i in table.all():
        res.append(recordToMobileAttendee(i))

    return res

# get raw data from airtable
@router.get("/raw")
async def get_all_attendees_raw(table: Table = Depends(get_mobile_table)):
    return table.all()

# add new attendee
@router.post("/add")
async def add_attendee(attendee: MobileAttendee, table: Table = Depends(get_mobile_table)):
    # TODO: add input verification?
    res = table.create(attendee.getAirtableFields())
    return res

# get specific attendee
@router.get("/{attendee_id}")
async def get_attendee(attendee_id: str, table: Table = Depends(get_mobile_table)):
    return recordToMobileAttendee(table.get(attendee_id))

# get attendee properties
@router.get("/{attendee_id}/signed_in")
async def check_attendee_signed_in(attendee_id: str, table: Table = Depends(get_mobile_table)):
    return recordToMobileAttendee(table.get(attendee_id)).signed_in

@router.get("/{attendee_id}/meals")
async def get_attendee_meals(attendee_id: str, table: Table = Depends(get_mobile_table)):
    return recordToMobileAttendee(table.get(attendee_id)).meals

@router.get("/{attendee_id}/meals/{meal}")
async def check_attendee_meal(attendee_id: str, meal: str, table: Table = Depends(get_mobile_table)):
    return meal in recordToMobileAttendee(table.get(attendee_id)).meals

# update attendee properties
@router.post("/update/{attendee_id}/signed_in") 
async def change_attendee_signed_in(attendee_id: str, signed_in: bool, table: Table = Depends(get_mobile_table)):
    try:
        return table.update(attendee_id, {"signed_in": signed_in})
    except:
        raise HTTPException(status_code=403, detail="Setting signed_in failed")

@router.post("/update/{attendee_id}/meals/add") 
async def add_attendee_meals(attendee_id: str, meals: list[str], table: Table = Depends(get_mobile_table)):
    old_meals = recordToMobileAttendee(table.get(attendee_id)).meals
    new_meals = old_meals + [meal for meal in meals if meal not in old_meals]

    try:
        return table.update(attendee_id, {"meals": new_meals})
    except:
        raise HTTPException(status_code=403, detail="Adding meals failed")
    
@router.post("/update/{attendee_id}/meals/remove") 
async def remove_attendee_meals(attendee_id: str, meals: list[str], table: Table = Depends(get_mobile_table)):
    old_meals = recordToMobileAttendee(table.get(attendee_id)).meals
    new_meals = [meal for meal in old_meals if meal not in meals]

    try:
        return table.update(attendee_id, {"meals": new_meals})
    except:
        raise HTTPException(status_code=403, detail="Removing meals failed")