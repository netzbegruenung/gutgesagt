import uuid

from pydantic import BaseModel, Field
from typing import List, Optional

from dtos.beitrag import HintergrundinfoResponse, KommentarResponse, PostResponse
from dtos.image import BildResponse
from dtos.statement import ThemaDto

# TODO: Evaluate usage of camelize


###   Requests   ###


class SearchByTextRequest(BaseModel):
    query_text: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text",
        example="climate change policy",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return",
        example=10,
    )
    # TODO: Add a field to specify minimum similarity score of statements
    # TODO: Add a field to specify minimum rating of reply suggestions

    # class Config:
    #     alias_generator = camelize
    #     populate_by_name = True


###   Entities   ###

# Je Treffer der Beitrag als Response-DTO (dtos/beitrag.py): Ein DbEntry wird beim
# Anlegen des Treffers umgewandelt, Anzeigename und ist_eigener_beitrag stehen dort.
#
# statement_id und themen: die Aussage, ueber die der Beitrag gefunden wurde, und
# deren Themen, fuer den Themenfilter der Ergebnisseite (#363). Ein direkter Treffer
# ohne Aussage hat keine ID und keine Themen. themen None: Die Themen liessen sich
# nicht nachschlagen; die Seite bietet dann kein Zuordnen an, sonst ersetzte ein Klick
# die vorhandenen Themen.


class CommentarySearchResult(BaseModel):
    score: float
    statement_text: str
    statement_similarity_score: float
    reply_relevance: float
    statement_id: Optional[uuid.UUID] = None
    themen: Optional[List[ThemaDto]] = []
    commentary_result: KommentarResponse
    user_vote: Optional[str] = None  # "like", "dislike", or None
    # Polarity filtering metadata
    polarity_mismatch_detected: Optional[bool] = None
    original_score: Optional[float] = None  # Score before polarity adjustment


class GenericTextSearchResult(BaseModel):
    score: float
    statement_text: str
    statement_similarity_score: float
    reply_relevance: float
    statement_id: Optional[uuid.UUID] = None
    themen: Optional[List[ThemaDto]] = []
    generictext_result: HintergrundinfoResponse
    user_vote: Optional[str] = None  # "like", "dislike", or None
    # Polarity filtering metadata
    polarity_mismatch_detected: Optional[bool] = None
    original_score: Optional[float] = None  # Score before polarity adjustment


class PostSearchResult(BaseModel):
    score: float
    statement_text: str
    statement_similarity_score: float
    reply_relevance: float
    statement_id: Optional[uuid.UUID] = None
    themen: Optional[List[ThemaDto]] = []
    post_result: PostResponse
    user_vote: Optional[str] = None  # "like", "dislike", or None
    # Polarity filtering metadata
    polarity_mismatch_detected: Optional[bool] = None
    original_score: Optional[float] = None  # Score before polarity adjustment


class ImageSearchResult(BaseModel):
    score: float
    statement_text: Optional[str] = None
    statement_similarity_score: Optional[float] = None
    reply_relevance: Optional[float] = None
    statement_id: Optional[uuid.UUID] = None
    themen: Optional[List[ThemaDto]] = []
    image_result: BildResponse
    user_vote: Optional[str] = None
    polarity_mismatch_detected: Optional[bool] = None
    original_score: Optional[float] = None


# "Alles zum Thema" (#754): Passt eine kurze Sucheingabe zu einem Thema, die
# meistgenutzten Aussagen des Themas (services/themen_aussagen_service.py).


class AussageDesThemasDto(BaseModel):
    statement_id: uuid.UUID
    text: str
    # Sichtbare Antworten auf die Aussage.
    antworten: int


class PassendesThemaDto(ThemaDto):
    aussagen: List[AussageDesThemasDto]
    # Alle Aussagen des Themas mit Antwort; mehr als in `aussagen`, dann gibt es
    # "Alle Aussagen zum Thema" (GET /search/thema/{schluessel}).
    anzahl_aussagen: int


class AussagenDesThemasResponse(BaseModel):
    thema: PassendesThemaDto


###   Responses   ###


class SearchResponse(BaseModel):
    query_was_newly_added_as_statement: bool
    # None, wenn das Anlegen der Suchanfrage als Statement scheiterte - frueher
    # stand hier str(None), also der Text "None".
    statement_id: Optional[str]
    statement_text: str
    commentary_search_results_count: int
    commentary_search_results: List[CommentarySearchResult]
    generictext_search_results_count: int
    generictext_search_results: List[GenericTextSearchResult]
    post_search_results_count: int = 0
    post_search_results: List[PostSearchResult] = []
    image_search_results_count: int = 0
    image_search_results: List[ImageSearchResult] = []
    # Ohne Treffer: so oft wurde in den letzten vier Wochen ohne Treffer danach gesucht
    # (je Tagespseudonym und Woche, die eigene Suche eingerechnet); erst ab drei und nur
    # mit dem Schalter null_treffer_anzahl, sonst None (#362,
    # services/suchen_ohne_treffer_service.py, schon_gesucht).
    schon_gesucht_anzahl: Optional[int] = None
    # Nur bei Eingaben aus einem bis drei Woertern, die zu einem Thema passen
    # (domain/themen_abgleich.py), hoechstens zwei; None sonst oder wenn das
    # Nachschlagen scheitert. Die Treffer oben bleiben davon unberuehrt.
    passende_themen: Optional[List[PassendesThemaDto]] = None

    # class Config:
    #     alias_generator = camelize
    #     populate_by_name = True
