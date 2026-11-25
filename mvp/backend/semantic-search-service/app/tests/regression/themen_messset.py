"""
Vorlaeufiges Messset fuer Themenvorschlaege (#401): Aussagen mit ihren Themen, damit
themen_messen.py ohne Produktionsdaten laeuft. Regeln und Ergebnis in THEMEN.md.

Massgeblich ist das Testset, also die Zuordnungen von Hand aus Produktion (Admin-Export
unter /themen/testset, Glossar "Testset"); themen_messen.py misst es mit --testset DATEI.
Dieses Messset ersetzt es nicht: Die Themen hier hat ein Agent zugeordnet, nicht die
Personen, die Gut gesagt nutzen, und es ist klein (je Thema drei bis acht Aussagen).

Quelle: start = Aussage des Startbestands woertlich (suche_testset.STARTBESTAND), seed =
Aussage aus mvp/data/seed/v1.0, eigen = fuer dieses Messset formuliert. Die Auswertung
nennt start/seed getrennt: Diese Texte haben Menschen geschrieben, nicht fuer die Messung.

Keine echten Personen, keine Personendaten, keine Eingaben aus Produktion. Neue Aussagen
ans Ende, IDs fortlaufend; eine ID wechselt nie den Text.
"""

from typing import NamedTuple, Tuple

from tests.regression import suche_testset as st

QUELLEN = ("start", "seed", "eigen")


class Beispiel(NamedTuple):
    id: str
    text: str
    themen: Tuple[str, ...]
    quelle: str


# fmt: off
BEISPIELE = tuple(Beispiel(*b) for b in (
    # Startbestand und Seed
    ("T001", st.VOEGEL, ("energie-heizen", "natur-umwelt"), "start"),
    ("T002", st.DUNKELFLAUTE, ("energie-heizen",), "start"),
    ("T003", st.ATOM, ("energie-heizen",), "start"),
    ("T004", st.CHINA, ("klima",), "start"),
    ("T005", st.WOHLSTAND, ("klima", "wirtschaft-arbeit"), "start"),
    ("T006", st.HEIZUNG, ("energie-heizen",), "start"),
    ("T007", st.NEUBAU, ("energie-heizen", "wohnen"), "start"),
    ("T008", st.CO2PREIS, ("klima", "haushalt-steuern", "soziales"), "start"),
    ("T009", st.BALKON, ("energie-heizen",), "start"),
    ("T010", st.MIETER, ("energie-heizen", "wohnen"), "start"),
    ("T011", st.EAUTO, ("verkehr",), "start"),
    ("T012", st.VERBRENNER, ("verkehr", "wirtschaft-arbeit"), "start"),
    ("T013", st.TEMPO, ("verkehr", "klima"), "start"),
    ("T014", st.TICKET, ("verkehr", "stadt-land"), "start"),
    ("T015", st.LAND, ("stadt-land",), "start"),
    ("T016", st.FLEISCH, ("landwirtschaft-ernaehrung",), "start"),
    ("T017", st.LANDWIRTE, ("landwirtschaft-ernaehrung",), "start"),
    ("T018", st.BIO, ("landwirtschaft-ernaehrung", "soziales"), "start"),
    ("T019", st.WOLF, ("natur-umwelt",), "start"),
    ("T020", st.INSEKTEN, ("natur-umwelt", "landwirtschaft-ernaehrung"), "start"),
    ("T021", st.VERBOT, ("demokratie-freiheit",), "start"),
    ("T022", st.AKADEMIKER, ("stadt-land", "bildung"), "start"),
    ("T023", st.RENTE, ("soziales", "haushalt-steuern"), "start"),
    ("T024", st.EU, ("europa",), "start"),
    ("T025", st.BUERGERGELD, ("soziales", "wirtschaft-arbeit"), "start"),
    ("T026", st.FLUECHTLINGE, ("migration", "wirtschaft-arbeit"), "start"),
    ("T027", st.MIGRANTEN, ("migration", "frieden-sicherheit"), "start"),
    ("T028", st.GENDERN, ("gleichstellung-vielfalt",), "start"),
    ("T029", st.KLIMAKLEBER, ("klima", "demokratie-freiheit"), "start"),
    ("T030", st.MEINUNG, ("demokratie-freiheit",), "start"),
    ("T031", st.UNZUVERLAESSIG, ("energie-heizen",), "seed"),
    ("T032", st.TEUER, ("energie-heizen",), "seed"),
    # Klima
    ("T033", "Der Klimawandel ist natürlich, das gab es schon immer.", ("klima",), "eigen"),
    ("T034", "Ein bisschen wärmer schadet doch niemandem.", ("klima",), "eigen"),
    ("T035", "Die Klimaziele sind sowieso nicht mehr zu schaffen.", ("klima",), "eigen"),
    ("T036", "Hitzewellen im Sommer hat es früher auch gegeben.", ("klima", "gesundheit"), "eigen"),
    # Energie und Heizen
    ("T037", "Ohne russisches Gas frieren wir im Winter.", ("energie-heizen", "frieden-sicherheit"), "eigen"),
    ("T038", "Der Strompreis ist wegen der Energiewende so hoch.", ("energie-heizen",), "eigen"),
    ("T039", "Solaranlagen auf Feldern zerstören die Landschaft.", ("energie-heizen", "natur-umwelt"), "eigen"),
    # Verkehr
    ("T040", "Radwege nehmen den Autofahrern den Platz weg.", ("verkehr",), "eigen"),
    ("T041", "Die Bahn ist ständig unpünktlich, darauf kann man sich nicht verlassen.", ("verkehr",), "eigen"),
    ("T042", "Ohne Auto kommt man auf dem Land nirgendwohin.", ("verkehr", "stadt-land"), "eigen"),
    ("T043", "Das Dieselfahrverbot enteignet die Autofahrer.", ("verkehr",), "eigen"),
    # Landwirtschaft und Ernaehrung
    ("T044", "Vegane Ernährung ist ungesund.", ("landwirtschaft-ernaehrung", "gesundheit"), "eigen"),
    ("T045", "Ohne Glyphosat können die Bauern nicht wirtschaften.", ("landwirtschaft-ernaehrung",), "eigen"),
    ("T046", "Die Streichung beim Agrardiesel ruiniert die Höfe.", ("landwirtschaft-ernaehrung", "haushalt-steuern"), "eigen"),
    ("T047", "Mehr Tierwohl macht Fleisch für Familien unbezahlbar.", ("landwirtschaft-ernaehrung", "soziales"), "eigen"),
    # Natur und Umwelt
    ("T048", "Plastik aus Deutschland landet doch gar nicht im Meer.", ("natur-umwelt",), "eigen"),
    ("T049", "Naturschutz verhindert jeden Neubau.", ("natur-umwelt", "wohnen"), "eigen"),
    ("T050", "Mülltrennung bringt nichts, am Ende wird sowieso alles verbrannt.", ("natur-umwelt",), "eigen"),
    ("T051", "Der Borkenkäfer ist schlimmer für den Wald als die Trockenheit.", ("natur-umwelt", "klima"), "eigen"),
    # Wirtschaft und Arbeit
    ("T052", "Die Industrie wandert ab, weil Deutschland zu teuer geworden ist.", ("wirtschaft-arbeit",), "eigen"),
    ("T053", "Der Mindestlohn vernichtet Arbeitsplätze.", ("wirtschaft-arbeit", "soziales"), "eigen"),
    ("T054", "Der Fachkräftemangel ist eine Erfindung der Arbeitgeber.", ("wirtschaft-arbeit",), "eigen"),
    ("T055", "Mit der Vier-Tage-Woche verlieren wir unseren Wohlstand.", ("wirtschaft-arbeit",), "eigen"),
    # Haushalt und Steuern
    ("T056", "Die Schuldenbremse darf auf keinen Fall gelockert werden.", ("haushalt-steuern",), "eigen"),
    ("T057", "Der Staat verschwendet unser Steuergeld.", ("haushalt-steuern",), "eigen"),
    ("T058", "Eine Vermögensteuer vertreibt die Reichen aus dem Land.", ("haushalt-steuern", "wirtschaft-arbeit"), "eigen"),
    ("T059", "Die Erbschaftsteuer trifft vor allem kleine Familienbetriebe.", ("haushalt-steuern", "wirtschaft-arbeit"), "eigen"),
    # Soziales
    ("T060", "Die Kindergrundsicherung landet sowieso nicht bei den Kindern.", ("soziales",), "eigen"),
    ("T061", "Wer arm ist, ist selbst schuld.", ("soziales",), "eigen"),
    ("T062", "Für die eigenen Rentner ist nie Geld da.", ("soziales",), "eigen"),
    # Wohnen
    ("T063", "Die Mietpreisbremse sorgt nur dafür, dass niemand mehr baut.", ("wohnen",), "eigen"),
    ("T064", "Das Einfamilienhaus soll verboten werden.", ("wohnen", "demokratie-freiheit"), "eigen"),
    ("T065", "In der Stadt kann sich keine Familie mehr eine Wohnung leisten.", ("wohnen", "stadt-land", "soziales"), "eigen"),
    ("T066", "Enteignungen von Wohnkonzernen schaffen keine einzige neue Wohnung.", ("wohnen",), "eigen"),
    # Gesundheit
    ("T067", "Auf dem Land gibt es bald keine Hausärzte mehr.", ("gesundheit", "stadt-land"), "eigen"),
    ("T068", "Die Krankenhausreform macht die kleinen Kliniken kaputt.", ("gesundheit",), "eigen"),
    ("T069", "Die Cannabis-Legalisierung macht unsere Jugend süchtig.", ("gesundheit",), "eigen"),
    ("T070", "In der Pflege verdient man zu wenig, deshalb will das keiner machen.", ("gesundheit", "wirtschaft-arbeit"), "eigen"),
    # Bildung
    ("T071", "Unsere Schulen fallen auseinander.", ("bildung",), "eigen"),
    ("T072", "Die Kinder lernen in der Schule nicht mehr richtig lesen und schreiben.", ("bildung",), "eigen"),
    ("T073", "Mit dem Lehrermangel lässt die Politik die Schüler im Stich.", ("bildung",), "eigen"),
    ("T074", "Ein Studium lohnt sich heute nicht mehr, eine Ausbildung ist besser.", ("bildung", "wirtschaft-arbeit"), "eigen"),
    # Digitales
    ("T075", "In deutschen Behörden läuft noch alles mit Faxgeräten.", ("digitales",), "eigen"),
    ("T076", "Auf dem Dorf gibt es immer noch kein schnelles Internet.", ("digitales", "stadt-land"), "eigen"),
    ("T077", "Künstliche Intelligenz nimmt uns allen die Jobs weg.", ("digitales", "wirtschaft-arbeit"), "eigen"),
    ("T078", "Die Chatkontrolle ist das Ende des Briefgeheimnisses.", ("digitales", "demokratie-freiheit", "europa"), "eigen"),
    ("T079", "Tablets im Klassenzimmer machen die Kinder dumm.", ("digitales", "bildung"), "eigen"),
    # Migration
    ("T080", "Wir können nicht alle aufnehmen.", ("migration",), "eigen"),
    ("T081", "Asylbewerber bekommen mehr Geld als deutsche Rentner.", ("migration", "soziales"), "eigen"),
    ("T082", "Abschiebungen scheitern, weil die Behörden nichts tun.", ("migration",), "eigen"),
    ("T083", "Ohne Zuwanderung bricht unsere Pflege zusammen.", ("migration", "gesundheit", "wirtschaft-arbeit"), "eigen"),
    # Demokratie und Freiheit
    ("T084", "Die Medien sind doch alle gleichgeschaltet.", ("demokratie-freiheit",), "eigen"),
    ("T085", "Die da oben machen sowieso, was sie wollen.", ("demokratie-freiheit",), "eigen"),
    ("T086", "Der öffentlich-rechtliche Rundfunk ist Staatsfunk.", ("demokratie-freiheit",), "eigen"),
    # Extremismus
    ("T087", "Die AfD ist eine ganz normale Partei.", ("extremismus",), "eigen"),
    ("T088", "Linksextremismus ist genauso gefährlich wie Rechtsextremismus.", ("extremismus",), "eigen"),
    ("T089", "Ein Verbot der AfD wäre undemokratisch.", ("extremismus", "demokratie-freiheit"), "eigen"),
    ("T090", "Die Reichsbürger sind harmlose Spinner.", ("extremismus",), "eigen"),
    # Europa
    ("T091", "Deutschland zahlt in der EU für alle anderen.", ("europa", "haushalt-steuern"), "eigen"),
    ("T092", "Ohne den Euro ginge es uns besser.", ("europa", "wirtschaft-arbeit"), "eigen"),
    ("T093", "Das Europaparlament hat doch gar nichts zu sagen.", ("europa", "demokratie-freiheit"), "eigen"),
    # Frieden und Sicherheit
    ("T094", "Waffenlieferungen an die Ukraine verlängern nur den Krieg.", ("frieden-sicherheit",), "eigen"),
    ("T095", "Die Bundeswehr ist nicht einmal verteidigungsfähig.", ("frieden-sicherheit",), "eigen"),
    ("T096", "Wir brauchen wieder die Wehrpflicht.", ("frieden-sicherheit",), "eigen"),
    ("T097", "Die Grünen waren mal Pazifisten und sind jetzt Kriegstreiber.", ("frieden-sicherheit",), "eigen"),
    # Stadt und Land
    ("T098", "Auf dem Land schließt eine Dorfkneipe nach der anderen.", ("stadt-land",), "eigen"),
    ("T099", "Die Politik vergisst die Menschen in den Dörfern.", ("stadt-land",), "eigen"),
    ("T100", "Im Osten wird seit der Wende nur abgebaut.", ("stadt-land", "wirtschaft-arbeit"), "eigen"),
    # Gleichstellung und Vielfalt
    ("T101", "Frauenquoten sind ungerecht gegenüber Männern.", ("gleichstellung-vielfalt",), "eigen"),
    ("T102", "Das Selbstbestimmungsgesetz gefährdet Frauen in Umkleiden.", ("gleichstellung-vielfalt",), "eigen"),
    ("T103", "Frauen verdienen nur weniger, weil sie andere Berufe wählen.", ("gleichstellung-vielfalt", "wirtschaft-arbeit"), "eigen"),
    ("T104", "Der Regenbogen hat an Rathäusern nichts zu suchen.", ("gleichstellung-vielfalt",), "eigen"),
))
# fmt: on
