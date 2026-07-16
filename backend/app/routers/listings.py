from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.utils.dependencies import require_farmer, get_current_user
from app.models.user import User
from app.models.produce import Listing
from app.services import stt_service, storage_service, vision_service, listing_service
from app.schemas.listing import ListingCreate, ListingResponse
from typing import List

router = APIRouter(tags=["Voice Listings"])

MAX_FILE_SIZE = 5 * 1024 * 1024 # 5 MB

@router.post("/voice/transcribe")
async def transcribe_voice_listing(
    audio: UploadFile = File(...),
    current_farmer: User = Depends(require_farmer)
):
    # 1. Check file size (Read all bytes into memory)
    audio_bytes = await audio.read()
    if len(audio_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Audio file too large. Max size is 5MB.")
    
    # 2. Transcribe the audio via our local STT service (faster-whisper)
    try:
        # Note: Language is assumed 'te' (Telugu) per PRD default, but can transcribe English too.
        transcript = await stt_service.transcribe_audio(audio_bytes)
    except ValueError as e:
        # e.g., "Empty or unreadable audio"
        raise HTTPException(status_code=400, detail=str(e))
        
    # 3. Use the LLM Gateway to extract structured JSON data from the transcript
    intent_data = await stt_service.extract_listing_intent(transcript)
    
    # 4. Return the combined response
    return {
        "transcript": transcript,
        "produce_name": intent_data.get("produce_name"),
        "quantity": intent_data.get("quantity"),
        "unit": intent_data.get("unit"),
        "confidence": intent_data.get("confidence", 0.0),
        "confirmation_message": intent_data.get("confirmation_message_te")
    }

@router.post("/listings/{listing_id}/photo")
async def upload_listing_photo(
    listing_id: uuid.UUID,
    photo: UploadFile = File(...),
    current_farmer: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    # 1. Fetch the listing and ensure the farmer actually owns it
    result = await db.execute(select(Listing).where(Listing.listing_id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.farmer_id != current_farmer.user_id:
        raise HTTPException(status_code=403, detail="You do not own this listing")

    # 2. Safety check: Max 5MB file size
    image_bytes = await photo.read()
    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Photo too large. Max size is 5MB.")
    
    # 3. Upload to MinIO Storage
    file_extension = photo.filename.split('.')[-1] if photo.filename and '.' in photo.filename else 'jpg'
    object_key = f"{listing_id}/{uuid.uuid4()}.{file_extension}"
    storage_service.upload_file(
        key=object_key, 
        data=image_bytes, 
        content_type=photo.content_type or "image/jpeg"
    )

    # 4. Grade the photo using Groq Vision API
    vision_result = await vision_service.grade_produce_photo(image_bytes)
    
    # 5. Update the Database
    listing.photo_url = object_key
    listing.vision_grade = vision_result.get("grade")
    await db.commit()
    
    # 6. Return response
    return {
        "photo_url": object_key,
        "vision_grade": vision_result.get("grade"),
        "reason": vision_result.get("reason")
    }

@router.post("/listings", response_model=ListingResponse)
async def create_listing(
    payload: ListingCreate,
    current_farmer: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    from app.models.produce import ProduceCatalog, UnitType
    from sqlalchemy import select
    import uuid

    final_produce_id = payload.produce_id
    
    if not final_produce_id and payload.produce_name:
        # Check if produce exists by name (case insensitive)
        result = await db.execute(
            select(ProduceCatalog).where(ProduceCatalog.name_en.ilike(payload.produce_name))
        )
        existing = result.scalars().first()
        if existing:
            final_produce_id = existing.produce_id
        else:
            # Auto-create it!
            new_produce = ProduceCatalog(
                produce_id=uuid.uuid4(),
                name_en=payload.produce_name.title(),
                name_te=payload.produce_name.title(), # Just duplicate english if they spoke it, or assume telugu
                unit=UnitType.kg
            )
            db.add(new_produce)
            
            await db.commit()
            await db.refresh(new_produce)
            final_produce_id = new_produce.produce_id

    if not final_produce_id:
        raise HTTPException(status_code=400, detail="Must provide produce_id or produce_name")

    return await listing_service.create_listing(
        farmer_id=current_farmer.user_id,
        produce_id=final_produce_id,
        quantity=float(payload.quantity),
        db=db
    )

@router.get("/listings/my", response_model=List[ListingResponse])
async def get_my_listings(
    current_farmer: User = Depends(require_farmer),
    db: AsyncSession = Depends(get_db)
):
    return await listing_service.get_farmer_listings(
        farmer_id=current_farmer.user_id,
        db=db
    )

@router.get("/listings/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await listing_service.get_listing_by_id_for_user(
        listing_id=listing_id,
        user=current_user,
        db=db
    )
