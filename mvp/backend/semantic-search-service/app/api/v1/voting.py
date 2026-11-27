from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, Dict, List
import uuid

from core.logging import get_logger
from auth.authorization import validate_user_id, require_auth
from domain.models.vote import VoteCreate, VoteResponse
from services.voting_service import VotingService
from core.config import Settings
from dependencies import (
    get_beitrag_laden,
    get_muster_hinweise_service,
    get_settings,
    get_voting_service,
    require_art9_einwilligung,
)
from services.spielgefuehl_service import stimmen_aktiv, stimmen_eingewilligte
from services.beitrag_laden import BeitragLader, BeitragUnlesbar
from middleware.rate_limiter import check_voting_rate_limit
from core.fehler import NICHT_ERREICHBAR, UNGUELTIGE_ANFRAGE, Validierungsfehler
from domain.team_fortschritt import Art as TeamArt
from services.team_fortschritt_service import team_zaehlen

logger = get_logger(__name__)

router = APIRouter()


def get_current_user(x_user: Optional[str] = Header(None)) -> str:
    """Dependency to get and validate the current user from X-User header."""
    if not x_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return require_auth(x_user, operation="write")


async def nur_sichtbarer_beitrag(
    content_id: uuid.UUID, laden: BeitragLader = Depends(get_beitrag_laden)
) -> Optional[str]:
    """

    Abstimmen nur auf einen Beitrag, den die Person sehen kann: Gesperrt, geloescht
    oder nie vorhanden gibt 404 und keine Stimme. Zuruecknehmen prueft das nicht,
    eine alte Stimme an einem inzwischen gesperrten Beitrag bleibt loszuwerden.

    Ein Datensatz, der da ist, sich aber nicht lesen laesst, ist kaputt und nicht
    abwesend; die Stimme zaehlt dann wie die Nutzung (services/beitrag_laden.py).
    Antwortet der Suchindex nicht, zaehlt sie ebenfalls: Stimmen liegen in
    PostgreSQL und gingen bis #272 ohne Suchindex, die Pruefung soll sie nicht davon
    abhaengig machen.
    """
    try:
        beitrag = await laden(content_id)
    except BeitragUnlesbar:
        return None
    except Exception as fehler:
        # Mit Stacktrace: Auch ein Programmierfehler landet hier und soll auffallen.
        logger.warning(
            f"Visibility check for vote skipped: {type(fehler).__name__}", exc_info=True
        )
        return None
    if beitrag is None:
        raise HTTPException(status_code=404, detail="Content not found")
    # Die Autorin, fuer den Team-Fortschritt (``_fuers_team_zaehlen``) und die
    # Muster-Hinweise aus Zustimmungen; None oben, wenn sich der Beitrag nicht lesen liess.
    return getattr(beitrag, "original_author", None)


def _fuers_team_zaehlen(
    user_id: str, autorin: Optional[str], content_id: uuid.UUID
) -> None:
    """
    Eine Stimme zaehlt fuer die Teams der Person (Team-Fortschritt, #784), aber nicht
    die zu einem eigenen Beitrag: Sonst fuellten drei Klicks am eigenen Bestand die
    Team-Quest (Gamification-Check 26.11., Befund 22), wie es ADR 0004 schon fuer die
    Punkte fuers Bewerten ausschliesst. Ist die Autorin unbekannt (Beitrag unlesbar,
    Suchindex weg), zaehlt die Stimme wie bisher. Fehler nur im Log.
    """
    if autorin is not None and autorin == user_id:
        return
    team_zaehlen(user_id, TeamArt.BEWERTUNG, str(content_id))


def zustimmung_fuer_muster(
    user_id: str, autorin: Optional[str], settings: Settings
) -> None:
    """
    Eine Zustimmung fuer die Muster-Hinweise melden (Schalter ``muster_stimmen``):
    nur, wenn der Schalter wirkt und beide Konten zum Spielgefuehl-Wortlaut mit
    Zustimmungen und zur Art.-9-Einwilligung eingewilligt haben
    (services/spielgefuehl_service.py ``stimmen_eingewilligte``), geprueft bei jeder
    Meldung. Ablehnungen zaehlen nicht. Ohne Schalter keine Datenbankabfrage. Fehler
    nur im Log: Die Stimme ist schon gespeichert.
    """
    if not autorin:
        return
    try:
        if not stimmen_aktiv(settings):
            return
        if settings.ist_startkonto(user_id) or settings.ist_startkonto(autorin):
            return
        if stimmen_eingewilligte([user_id, autorin]) != {user_id, autorin}:
            return
        get_muster_hinweise_service().zustimmung_melden(user_id, autorin)
    except Exception as e:
        logger.error(f"Pattern check for approval failed: {type(e).__name__}")


@router.put(
    "/content/{content_id}/like",
    response_model=VoteResponse,
    dependencies=[Depends(check_voting_rate_limit), Depends(require_art9_einwilligung)],
)
def set_like(
    content_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    autorin: Optional[str] = Depends(nur_sichtbarer_beitrag),
    voting_service: VotingService = Depends(get_voting_service),
    settings: Settings = Depends(get_settings),
) -> VoteResponse:
    """
    Set a like for a content item. Idempotent operation.
    If user already liked, returns success with current state.
    If user had disliked, replaces with like.
    """
    logger.debug(f"Setting like for content {content_id}")
    try:
        result = voting_service.set_like(user_id, content_id)
        _fuers_team_zaehlen(user_id, autorin, content_id)
        # Muster-Hinweise aus gegenseitigen Zustimmungen; Fehler nur im Log.
        zustimmung_fuer_muster(user_id, autorin, settings)
        logger.debug("Like set successfully")
        return result
    except Validierungsfehler as e:
        logger.warning(f"Like validation error: {type(e).__name__}")
        raise HTTPException(status_code=400, detail=e.antworttext)
    except ValueError as e:
        logger.warning(f"Like validation error: {type(e).__name__}")
        raise HTTPException(status_code=400, detail=UNGUELTIGE_ANFRAGE)
    except ConnectionError as e:
        logger.error(f"Database connection error: {type(e).__name__}")
        raise HTTPException(status_code=503, detail=NICHT_ERREICHBAR)
    except Exception as e:
        logger.error(f"Error setting like: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to set like")


@router.delete(
    "/content/{content_id}/like",
    response_model=VoteResponse,
    dependencies=[Depends(check_voting_rate_limit)],
)
def remove_like(
    content_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    voting_service: VotingService = Depends(get_voting_service),
) -> VoteResponse:
    """
    Remove a like for a content item. Idempotent operation.
    If no like exists, returns success with current state.
    """
    logger.debug(f"Removing like for content {content_id}")
    try:
        result = voting_service.remove_like(user_id, content_id)
        logger.debug("Like removed successfully")
        return result
    except ConnectionError as e:
        logger.error(f"Database connection error: {type(e).__name__}")
        raise HTTPException(status_code=503, detail=NICHT_ERREICHBAR)
    except Exception as e:
        logger.error(f"Error removing like: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to remove like")


@router.put(
    "/content/{content_id}/dislike",
    response_model=VoteResponse,
    dependencies=[Depends(check_voting_rate_limit), Depends(require_art9_einwilligung)],
)
def set_dislike(
    content_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    autorin: Optional[str] = Depends(nur_sichtbarer_beitrag),
    voting_service: VotingService = Depends(get_voting_service),
) -> VoteResponse:
    """
    Set a dislike for a content item. Idempotent operation.
    If user already disliked, returns success with current state.
    If user had liked, replaces with dislike.
    """
    logger.debug(f"Setting dislike for content {content_id}")
    try:
        result = voting_service.set_dislike(user_id, content_id)
        _fuers_team_zaehlen(user_id, autorin, content_id)
        logger.debug("Dislike set successfully")
        return result
    except Validierungsfehler as e:
        logger.warning(f"Dislike validation error: {type(e).__name__}")
        raise HTTPException(status_code=400, detail=e.antworttext)
    except ValueError as e:
        logger.warning(f"Dislike validation error: {type(e).__name__}")
        raise HTTPException(status_code=400, detail=UNGUELTIGE_ANFRAGE)
    except ConnectionError as e:
        logger.error(f"Database connection error: {type(e).__name__}")
        raise HTTPException(status_code=503, detail=NICHT_ERREICHBAR)
    except Exception as e:
        logger.error(f"Error setting dislike: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to set dislike")


@router.delete(
    "/content/{content_id}/dislike",
    response_model=VoteResponse,
    dependencies=[Depends(check_voting_rate_limit)],
)
def remove_dislike(
    content_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    voting_service: VotingService = Depends(get_voting_service),
) -> VoteResponse:
    """
    Remove a dislike for a content item. Idempotent operation.
    If no dislike exists, returns success with current state.
    """
    logger.debug(f"Removing dislike for content {content_id}")
    try:
        result = voting_service.remove_dislike(user_id, content_id)
        logger.debug("Dislike removed successfully")
        return result
    except ConnectionError as e:
        logger.error(f"Database connection error: {type(e).__name__}")
        raise HTTPException(status_code=503, detail=NICHT_ERREICHBAR)
    except Exception as e:
        logger.error(f"Error removing dislike: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to remove dislike")


@router.get("/content/{content_id}")
def get_user_vote(
    content_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    voting_service: VotingService = Depends(get_voting_service),
) -> dict:
    """Get the current user's vote for a specific content item."""
    try:
        vote_type = voting_service.get_user_vote(user_id, content_id)
        return {
            "content_id": str(content_id),
            "vote_type": vote_type,  # Can be "like", "dislike", or None
        }
    except Exception as e:
        logger.error(f"Error getting user vote: {type(e).__name__}")
        # Return None vote_type if error occurs
        return {"content_id": str(content_id), "vote_type": None}


@router.post("/votes/batch")
def get_user_votes_batch(
    content_ids: List[uuid.UUID],
    user_id: str = Depends(get_current_user),
    voting_service: VotingService = Depends(get_voting_service),
) -> Dict[str, str]:
    """Get the current user's votes for multiple content items."""
    return voting_service.get_user_votes_for_contents(user_id, content_ids)


# Legacy endpoint removed - use DELETE /content/{id}/like or /content/{id}/dislike instead
