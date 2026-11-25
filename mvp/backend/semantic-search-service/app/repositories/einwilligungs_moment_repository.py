"""
Was die App fuer das Einwilligungs-Budget ueber die angemeldete Person wissen muss
(#788, GLOSSARY.md "Einwilligungs-Budget"): ob sie schon einmal abgestimmt hat, wie
viele der Einwilligungsfragen sie schon beantwortet hat und seit wann es das Konto
in Gut gesagt gibt.

Nur lesend und nur aus Tabellen, die es schon gibt: Stimmen (``votes``), die
Antworten auf die Art.-9-Einwilligung, die Einwilligung "Punkte und Meilensteine",
die Zustimmung zur Sichtbarkeit, Team-Mitgliedschaften und die Zustimmung zu den
Nutzungsbedingungen. Gespeichert wird nichts, auch kein Besuch.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text

from infrastructure.database.connection import AppDatabase, get_app_database

# Eine Abfrage, damit die Seite "Meine Beitraege" nur einmal fragt. LEAST uebergeht
# in PostgreSQL NULL, solange nicht alle Werte NULL sind.
_ABFRAGE = text(
    """
    SELECT
        EXISTS (SELECT 1 FROM votes WHERE user_id = :u) AS abgestimmt,
        (CASE WHEN EXISTS (SELECT 1 FROM art9_einwilligungen WHERE user_id = :u)
                OR EXISTS (SELECT 1 FROM art9_ohne_einwilligung WHERE user_id = :u)
              THEN 1 ELSE 0 END)
        + (CASE WHEN EXISTS (SELECT 1 FROM punkte_einwilligung WHERE user_id = :u)
                THEN 1 ELSE 0 END)
        + (CASE WHEN EXISTS (SELECT 1 FROM abzeichen_sichtbarkeit WHERE user_id = :u)
                THEN 1 ELSE 0 END)
        + (CASE WHEN EXISTS (
                    SELECT 1 FROM team_mitgliedschaften WHERE konto_kennung = :u)
                THEN 1 ELSE 0 END) AS beantwortet,
        LEAST(
            (SELECT min(eingewilligt_am) FROM art9_einwilligungen WHERE user_id = :u),
            (SELECT min(entschieden_am) FROM art9_ohne_einwilligung WHERE user_id = :u),
            (SELECT min(zugestimmt_am) FROM nutzungsbedingungen_zustimmungen
                WHERE user_id = :u)
        ) AS konto_seit
    """
)


@dataclass(frozen=True)
class EinwilligungsMoment:
    # Mindestens eine eigene Stimme steht (eine zurueckgenommene zaehlt nicht mehr).
    abgestimmt: bool
    # Wie viele Einwilligungsfragen die Person schon beantwortet hat: Art. 9, Punkte
    # und Meilensteine, Sichtbarkeit, Team (nur ein Ja ist gespeichert).
    beantwortet: int
    # Die frueheste Antwort auf Art. 9 oder Nutzungsbedingungen; None ohne beides.
    konto_seit: Optional[datetime]


class EinwilligungsMomentRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        """``db``: eine AppDatabase; ohne Angabe die globale."""
        self.db = db if db is not None else get_app_database()

    def lesen(self, user_id: str) -> EinwilligungsMoment:
        with self.db.get_session() as session:
            zeile = session.execute(_ABFRAGE, {"u": user_id}).one()
            return EinwilligungsMoment(
                abgestimmt=bool(zeile.abgestimmt),
                beantwortet=int(zeile.beantwortet),
                konto_seit=zeile.konto_seit,
            )


_repository: Optional[EinwilligungsMomentRepository] = None


def get_einwilligungs_moment_repository() -> EinwilligungsMomentRepository:
    """Die globale Instanz holen oder anlegen."""
    global _repository
    if _repository is None:
        _repository = EinwilligungsMomentRepository()
    return _repository
