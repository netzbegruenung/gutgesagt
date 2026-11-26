"""
Feedback mit der Kategorie "gestoert": der Knopf "Was hat dich gestört?" fuer die
Startphase (Schalter ``feedback_gestoert``, GLOSSARY.md "Feedback").

Vorlaeufige juristische Einschaetzung vom 26.11.2026, Punkt (g): Freitext ohne
Kennung, der Hinweis "Bitte keine Namen oder Daten anderer." und Loeschung bis
31.12.2026. Deshalb gilt fuer diese Kategorie:

- kein Kontaktfeld, nur der Freitext und der Tag (wie jedes Feedback ohne Kennung);
- ab ``GESTOERT_GELOESCHT_AB`` (UTC-Tag) loescht der Loeschlauf des Feedbacks alle
  Eintraege der Kategorie, unabhaengig von der Frist von 180 Tagen
  (services/feedback_service.py), und ab demselben Tag nimmt der Dienst keine neuen
  an: Der Schalter wirkt dann nicht mehr (services/schalter_service.py).
"""

from datetime import date

KATEGORIE_GESTOERT = "gestoert"

# Ab diesem UTC-Tag ist die Startphase vorbei: alles geloescht, nichts Neues.
GESTOERT_GELOESCHT_AB = date(2026, 12, 31)


def gestoert_offen(heute: date) -> bool:
    """Ob der Knopf an diesem UTC-Tag noch Eintraege annehmen darf."""
    return heute < GESTOERT_GELOESCHT_AB
