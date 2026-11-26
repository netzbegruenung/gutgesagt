import os
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, Depends, FastAPI

# Import configuration first
from core.config import punkte_schalter_pruefen, settings

# Initialize logging with dependency injection
from core.logging import initialize_logging, get_logger

initialize_logging(settings.get_logging_config())
logger = get_logger(__name__)

logger.info("📚 Importing FastAPI app dependencies")
logger.debug(f"📁 Current directory: {os.getcwd()}")

from dependencies import anzeigename_merken, initialize_services
from services.embeddings.qdrant_embeddings_manager import (
    get_qdrant_embeddings_manager,
    get_embeddings_manager,
)
from services.seeding.seeding_service import get_seeding_service
from infrastructure.database.connection import get_app_database, close_app_database
from infrastructure.database import migrationen
from api.v1.commentary import router as commentary_router
from api.v1.content import router as content_router
from api.v1.contribution import router as contribution_router
from api.v1.metrics import router as metrics_router
from api.v1.reference import router as reference_router

from api.v1.search import router as search_router
from api.v1.garten import router as garten_router
from api.v1.statement import router as statement_router

from api.v1.generic_text import router as generic_text_router
from api.v1.post import router as post_router
from api.v1.image import router as image_router
from api.v1.einwurf import router as einwurf_router
from api.v1.seeding import router as seeding_router
from api.v1.usage import router as usage_router
from api.v1.naechster_schritt import router as naechster_schritt_router
from api.v1.einwilligungs_moment import router as einwilligungs_moment_router
from api.v1.spielgefuehl import router as spielgefuehl_router
from api.v1.voting import router as voting_router
from api.v1.moderation import router as moderation_router
from api.v1.vormoderation import router as vormoderation_router
from api.v1.loeschauftraege import router as loeschauftraege_router
from api.v1.schalter import router as schalter_router
from api.v1.funktionen import router as funktionen_router
from api.v1.merkliste import router as merkliste_router
from api.v1.ereignis import router as ereignis_router
from api.v1.ankunft import admin_router as ankuenfte_admin_router
from api.v1.ankunft import router as ankunft_router
from api.v1.saisons import admin_router as saisons_admin_router
from api.v1.saisons import router as saisons_router
from api.v1.saal_spruch import admin_router as saal_spruch_admin_router
from api.v1.saal_spruch import router as saal_spruch_router
from api.v1.rangliste import router as rangliste_router
from api.v1.konter_probe import router as konter_probe_router
from api.v1.sperren import router as sperren_router
from api.v1.health import router as health_router
from api.v1.feedback import router as feedback_router
from api.v1.einladungen import router as einladungen_router
from api.v1.teams import router as teams_router
from api.v1.gegenlesen import router as gegenlesen_router
from api.v1.spracherkennung import router as spracherkennung_router
from api.v1.varianten import router as varianten_router
from api.v1.linkvorschau import router as linkvorschau_router
from api.v1.kuerzungsvorschlag import router as kuerzungsvorschlag_router
from api.v1.art9_einwilligung import router as art9_einwilligung_router
from api.v1.nutzungsbedingungen import router as nutzungsbedingungen_router
from api.v1.herkunft_pruefen import router as herkunft_pruefen_router
from api.v1.aufrufe import router as aufrufe_router
from services.cleanup.bereinigungsjob import bereinigungsjob_starten
from services.suchen_ohne_treffer_service import (
    get_personen_des_tages,
    loeschen_im_takt,
)
from repositories.suchen_ohne_treffer_repository import (
    get_suchen_ohne_treffer_repository,
)
from dependencies import (
    abzeichen_service_bauen,
    get_feedback_service,
    get_loeschfristen_service,
    get_muster_hinweise_service,
    get_nutzung_rate_limiter,
)
from services.feedback_service import loeschen_im_takt as feedback_loeschen_im_takt
from services.gegenlesen.gegenlesen_service import SPRACHWERKZEUGE
from repositories.usage_tracking_repository import get_usage_repository
from services.entdoppelung import pruefwerte_verwerfen_im_takt
from repositories.gepostet_repository import get_gepostet_repository
from services.abzeichen_service import abzeichen_im_takt, abzeichen_service_setzen
from services.herkunft_pruefen import (
    get_herkunft_pruefen_service,
    herkunft_pruefen_bauen,
    pruefen_im_takt,
)
from services.aufrufe_service import verdichten_im_takt as aufrufe_verdichten_im_takt
from repositories.aufrufe_repository import get_aufrufe_repository
from services.muster_hinweise_service import (
    loeschen_im_takt as muster_hinweise_loeschen_im_takt,
)
from services.spracherkennung.spracherkennung import SPRACHERKENNUNG
from services.loeschfristen_service import (
    loeschen_im_takt as loeschfristen_im_takt,
)
from utils.rate_limiter import (
    aufraeumen_im_takt,
    aehnliche_aussagen_rate_limiter,
    einladung_pruefen_rate_limiter,
    einladung_rate_limiter,
    feedback_rate_limiter,
    aufrufe_rate_limiter,
    gegenlesen_rate_limiter,
    spracherkennung_rate_limiter,
    kuerzungsvorschlag_rate_limiter,
    report_rate_limiter,
    search_query_statement_rate_limiter,
    team_beitreten_rate_limiter,
    themen_vorschlag_rate_limiter,
)
from utils.tagesdeckel import tagesdeckel
import asyncio

# This is a workaround for a dependency issue: "OMP: Error #15: Initializing libomp140.x86_64.dll, but found libomp140.x86_64.dll already initialized.""
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager that handles QdrantEmbeddingsManager startup/shutdown
    and non-blocking seeding initialization.
    """
    # Startup
    # Punkte nur mit der eigenen Einwilligung "Punkte und Meilensteine" (#668); vor
    # allem anderen, damit ein falscher Schalter den Dienst gar nicht erst startet.
    punkte_schalter_pruefen(settings)
    try:
        logger.info("🚀 Starting Gut gesagt Semantic Search Service v1.0.0")

        # Initialize QdrantEmbeddingsManager with settings (fast)
        shared_manager = get_qdrant_embeddings_manager(settings)
        await shared_manager.start()
        logger.info("✅ QdrantEmbeddingsManager started")

        # Initialize application database
        logger.info("Initializing application database")
        app_db = get_app_database()
        app_db.create_tables()
        # Nach create_all und vor der ersten Anfrage, wie in den Kettentests.
        # Scheitert eine Migration, startet der Dienst nicht.
        eingespielt = migrationen.einspielen(app_db.engine, settings.migrations_path)
        logger.info("✅ Application database initialized, migrations: %s", eingespielt)

        # Initialize seeding service with metadata path
        seeding_service = get_seeding_service(
            settings, shared_manager, settings.metadata_path
        )
        logger.info("✅ SeedingService initialized")

        # Store seeding service for manual API access (no automatic seeding)
        logger.info("Seeding available via /api/v1/seeding/start endpoint")

        # Initialize lightweight content services (without blocking data load)
        logger.info("Initializing content services...")
        initialize_services()
        logger.info("✅ Content services initialized")

        # Der taegliche Bereinigungsjob (Frist der Nutzungsereignisse)
        logger.info("Starting Bereinigungsjob...")
        bereinigungsjob_starten()
        logger.info("✅ Bereinigungsjob started")

        # Start rate limiter cleanup task
        logger.info("Starting rate limiter cleanup task...")
        # Frueher stuendlich und ohne await - die Coroutine lief nie, abgelaufene
        # Schluessel blieben bis zum Neustart im Speicher.
        # Referenz halten: asyncio haelt Tasks nur schwach, und beim Shutdown
        # wird er abgebrochen statt mit der Schleife zu sterben.
        app.state.rate_limiter_aufraeumen = asyncio.create_task(
            aufraeumen_im_takt(
                [
                    report_rate_limiter,
                    aehnliche_aussagen_rate_limiter,
                    search_query_statement_rate_limiter,
                    feedback_rate_limiter,
                    aufrufe_rate_limiter,
                    einladung_rate_limiter,
                    einladung_pruefen_rate_limiter,
                    team_beitreten_rate_limiter,
                    gegenlesen_rate_limiter,
                    get_nutzung_rate_limiter(),
                    spracherkennung_rate_limiter,
                    kuerzungsvorschlag_rate_limiter,
                    themen_vorschlag_rate_limiter,
                    # Kein RateLimiter, raeumt aber genauso auf (Zaehler von gestern).
                    tagesdeckel,
                ]
            )
        )
        logger.info("✅ Rate limiter cleanup task started")

        # Kennzahl "Suchen ohne Treffer": alte Wochen taeglich loeschen, unabhaengig
        # vom abschaltbaren Bereinigungsjob (services/suchen_ohne_treffer_service.py).
        app.state.suchen_ohne_treffer_loeschen = asyncio.create_task(
            loeschen_im_takt(
                get_suchen_ohne_treffer_repository(), get_personen_des_tages()
            )
        )
        logger.info("✅ Searches-without-hits cleanup task started")

        # Feedback nach der Frist loeschen, ebenso unabhaengig vom Bereinigungsjob
        # (services/feedback_service.py).
        app.state.feedback_loeschen = asyncio.create_task(
            feedback_loeschen_im_takt(get_feedback_service())
        )
        logger.info("✅ Feedback cleanup task started")

        # Sprachmodell fuers Gegenlesen (#358) im Hintergrund laden (rund 2 s), damit
        # das erste Gegenlesen nicht wartet und der Start nicht blockiert. Fehlt es,
        # antwortet /api/v1/gegenlesen mit 503; der Dienst laeuft trotzdem.
        app.state.gegenlesen_vorladen = asyncio.create_task(_gegenlesen_vorladen())

        # Lingua fuer den Sprachhinweis (#405) ebenso im Hintergrund vorladen; fehlt
        # es, antwortet /api/v1/spracherkennung mit 503.
        app.state.spracherkennung_vorladen = asyncio.create_task(
            _spracherkennung_vorladen()
        )

        # Loeschfristen fuer Meldungen, Einwuerfe, geloeschte Beitraege und das
        # Tagespseudonym an Suchereignissen (am Tagesende verdichtet), ebenso
        # unabhaengig vom Bereinigungsjob (services/loeschfristen_service.py).
        app.state.loeschfristen = asyncio.create_task(
            loeschfristen_im_takt(get_loeschfristen_service())
        )
        logger.info("✅ Loeschfristen task started")

        # Pruefwerte der Entdoppelung nach ihrem Tag verwerfen (#352), unabhaengig
        # von Punkten und Usage-Cleanup (services/entdoppelung.py).
        app.state.pruefwerte_verwerfen = asyncio.create_task(
            pruefwerte_verwerfen_im_takt(
                get_usage_repository(),
                gepostet=get_gepostet_repository().vergangene_wochen_verdichten,
            )
        )
        # Paar-Pruefwerte nach dem Fenster verwerfen und alte Muster-Hinweise
        # loeschen (#352, services/muster_hinweise_service.py).
        app.state.muster_hinweise_loeschen = asyncio.create_task(
            muster_hinweise_loeschen_im_takt(get_muster_hinweise_service())
        )
        logger.info("✅ Check value and pattern note cleanup tasks started")

        # Meilenstein-Abzeichen am Anzeigenamen (#351): der Dienst immer, damit ein
        # Widerruf der Art.-9-Einwilligung ein frueheres Ja auch bei ausgeschalteten
        # Abzeichen zuruecknimmt; Frage und Rechnen im Takt nur mit beiden Schaltern
        # (services/abzeichen_service.py). Der Takt laeuft, wenn die Obergrenze es
        # erlaubt; ob er rechnet, entscheidet je Lauf der Admin-Wert (#708).
        abzeichen = abzeichen_service_bauen(settings)
        abzeichen_service_setzen(abzeichen)
        # Im Spielgefuehl-Modell rechnet er fuer die Rangliste (spielgefuehl_buehne).
        if settings.abzeichen_sichtbar or (
            settings.spielgefuehl_buehne_aktiv
            and settings.punkte_aktiv
            and settings.rangliste_aktiv
        ):
            app.state.abzeichen_rechnen = asyncio.create_task(
                abzeichen_im_takt(abzeichen)
            )
            logger.info("✅ Milestone badge task started")

        # Herkunft pruefen (#759): Der Takt sieht stuendlich nach; ohne wirksamen
        # Schalter ruft er nichts ab und liest nichts (services/herkunft_pruefen.py).
        app.state.herkunft_pruefen = asyncio.create_task(
            pruefen_im_takt(herkunft_pruefen_bauen())
        )

        # Seitenaufrufe (#761): Tagespseudonyme vergangener Tage zu Tageszahlen
        # verdichten und loeschen, auch bei ausgeschaltetem Schalter (loescht nur).
        app.state.aufrufe_verdichten = asyncio.create_task(
            aufrufe_verdichten_im_takt(get_aufrufe_repository())
        )

        logger.info(
            "✅ Application startup complete - server ready to accept connections"
        )

        # Store seeding service for API access
        app.state.seeding_service = seeding_service

        yield  # Server is now ready to accept connections

    finally:
        # Shutdown
        try:
            logger.info("Shutting down Gut gesagt Semantic Search Service")
            for name in (
                "rate_limiter_aufraeumen",
                "suchen_ohne_treffer_loeschen",
                "feedback_loeschen",
                "loeschfristen",
                "pruefwerte_verwerfen",
                "muster_hinweise_loeschen",
                "abzeichen_rechnen",
                "herkunft_pruefen",
                "aufrufe_verdichten",
            ):
                task = getattr(app.state, name, None)
                if task is not None:
                    task.cancel()
            # Ein laufender Lauf "Herkunft pruefen" haengt nicht am Takt (#759)
            herkunft = get_herkunft_pruefen_service()
            if herkunft is not None:
                herkunft.abbrechen()
            manager = get_embeddings_manager()
            await manager.shutdown()
            close_app_database()
            logger.info("✅ Application shutdown complete")
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {type(e).__name__}", exc_info=True)


async def _gegenlesen_vorladen() -> None:
    try:
        await asyncio.to_thread(SPRACHWERKZEUGE.laden)
        logger.info("✅ Gegenlesen: Sprachmodell geladen")
    except Exception as fehler:
        # Auch unerwartete Fehler hier abfangen: Ein Task, dessen Ausnahme niemand
        # abholt, meldet sie erst beim Beenden. Der Dienst laeuft ohne Gegenlesen weiter.
        logger.error("Gegenlesen nicht verfuegbar: %s", type(fehler).__name__)


async def _spracherkennung_vorladen() -> None:
    try:
        await asyncio.to_thread(SPRACHERKENNUNG.laden)
        logger.info("✅ Spracherkennung: Lingua geladen")
    except Exception as fehler:
        # Wie beim Gegenlesen: Der Dienst laeuft ohne Sprachhinweis weiter.
        logger.error("Spracherkennung nicht verfuegbar: %s", type(fehler).__name__)


logger.info("🔧 Initializing FastAPI app")

# Initialize FastAPI app with lifespan management
app = FastAPI(
    title="Gut gesagt API",
    description="Semantic search API with unified embeddings",
    version="1.0.0",
    lifespan=lifespan,
    # Starlette beantwortet einen Pfad, der sich nur im abschliessenden Slash von
    # einer Route unterscheidet, mit 307 und einem Location-Header -- und zwar
    # bevor irgendeine Auth-Dependency laeuft. Location enthaelt dabei den
    # absoluten Ziel-URL, also den internen Dienstnamen samt Port
    # (http://localhost:8000/...). GET /api/v1/moderation/reports/ verriet so die
    # interne Topologie an einen unauthentifizierten Aufrufer.
    #
    # Abgeschaltet statt den Header nachtraeglich im BFF umzuschreiben: die
    # Umleitung entsteht hier, und eine Korrektur am Proxy wirkt nur fuer den Weg
    # ueber den Proxy. Ohne sie gibt es keinen Location-Header, den irgendein
    # Ingress vergessen koennte zu bereinigen.
    #
    # Preis: ein Pfad ohne Slash trifft eine mit "/" registrierte Route nicht mehr
    # (und umgekehrt). Betroffen sind nur die Index-Stubs "@router.get('/')" der
    # Content-Router; das Frontend nutzt deren URLs ausschliesslich als Basis und
    # haengt immer einen Pfad an, und alle Healthchecks rufen /api/v1/health ohne
    # Slash auf.
    redirect_slashes=False,
    # Legt den Anzeigenamen aus X-User-Display-Name ab, einmal je Person und Aenderung.
    dependencies=[Depends(anzeigename_merken)],
)

# Add rate limiting middleware for content creation endpoints
from middleware.rate_limit import RateLimitMiddleware

app.add_middleware(
    RateLimitMiddleware,
    # Je Person, aus der Umgebung (core/config.py); Startkonten sind ausgenommen.
    requests_per_minute=settings.anlege_rate_limit_je_minute,
    requests_per_hour=settings.anlege_rate_limit_je_stunde,
)

# Tagesdeckel (middleware/tagesdeckel.py): nach dem Rate-Limit eingetragen und damit
# aussen; lehnt das Rate-Limit ab, gibt der Tagesdeckel den Platz wieder frei.
from middleware.tagesdeckel import TagesdeckelMiddleware

app.add_middleware(TagesdeckelMiddleware)

# Aufrufe zaehlen (#761, middleware/aufrufe_zaehlen.py): aus Abrufen, die die App ohnehin
# macht, nach der Antwort; ohne wirksamen Schalter tut die Middleware nichts.
from middleware.aufrufe_zaehlen import AufrufeZaehlenMiddleware

app.add_middleware(AufrufeZaehlenMiddleware)

app.include_router(commentary_router, prefix="/api/v1/commentary", tags=["commentary"])
app.include_router(content_router, prefix="/api/v1/content", tags=["content"])
app.include_router(
    contribution_router, prefix="/api/v1/contribution", tags=["contribution"]
)
app.include_router(metrics_router, prefix="/api/v1/metrics", tags=["metrics"])
app.include_router(reference_router, prefix="/api/v1/reference", tags=["reference"])
app.include_router(search_router, prefix="/api/v1/search", tags=["search"])
# Gartenansicht (#783): unter /search, damit sie wie die Suche fuer Besucher offen ist
app.include_router(garten_router, prefix="/api/v1/search", tags=["search"])
app.include_router(statement_router, prefix="/api/v1/statement", tags=["statement"])
app.include_router(
    generic_text_router, prefix="/api/v1/generic_text", tags=["generic_text"]
)
app.include_router(post_router, prefix="/api/v1/post", tags=["post"])
app.include_router(image_router, prefix="/api/v1/image", tags=["image"])
app.include_router(einwurf_router, prefix="/api/v1/rawinput", tags=["rawinput"])
app.include_router(seeding_router, prefix="/api/v1", tags=["seeding"])
app.include_router(usage_router, prefix="/api/v1/usage", tags=["usage"])
# Karte "Dein naechster Schritt" (#789), nur fuer Angemeldete
app.include_router(naechster_schritt_router, prefix="/api/v1/usage", tags=["usage"])
app.include_router(einwilligungs_moment_router, prefix="/api/v1/usage", tags=["usage"])
app.include_router(spielgefuehl_router, prefix="/api/v1/usage", tags=["usage"])
app.include_router(voting_router, prefix="/api/v1/voting", tags=["voting"])
app.include_router(moderation_router, prefix="/api/v1/moderation", tags=["moderation"])
app.include_router(
    vormoderation_router, prefix="/api/v1/moderation", tags=["moderation"]
)
# Loeschauftraege nach dem Widerruf der Art.-9-Einwilligung (DSFA R9b), admin-only
app.include_router(
    loeschauftraege_router,
    prefix="/api/v1/moderation/loeschauftraege",
    tags=["moderation"],
)
# Schalter mit Obergrenze und Admin-Wert (#708), admin-only
app.include_router(
    schalter_router, prefix="/api/v1/moderation/schalter", tags=["moderation"]
)
# Welche Funktionen hinter einem Schalter an sind (#756), ohne Anmeldung
app.include_router(funktionen_router, prefix="/api/v1/funktionen", tags=["schalter"])
# Merkliste (#758), hinter dem Schalter merkliste
app.include_router(merkliste_router, prefix="/api/v1/merkliste", tags=["merkliste"])
# Neutraler Sammelpfad (#799): die Art der Meldung steht nur im Body.
app.include_router(ereignis_router, prefix="/api/v1/ereignis", tags=["ereignis"])
# Ankuenfte je Kampagnenwort und Tag: Melden ohne Anmeldung, das Wort nur im Body;
# die Zahlen nur fuer Admins (api/v1/ankunft.py)
app.include_router(ankunft_router, prefix="/api/v1/ankunft", tags=["ankunft"])
app.include_router(ankuenfte_admin_router, prefix="/api/v1/ankuenfte", tags=["ankunft"])
# Saisons mit Gemeinschaftsziel (#782): Balken ohne Anmeldung, Pflege nur Admins
app.include_router(saisons_router, prefix="/api/v1/saisons", tags=["saisons"])
app.include_router(rangliste_router, prefix="/api/v1/rangliste", tags=["rangliste"])
app.include_router(
    saisons_admin_router, prefix="/api/v1/moderation/saisons", tags=["moderation"]
)
# Saal-Spruch: Spruch ohne Anmeldung, Pflege nur Admins
app.include_router(saal_spruch_router, prefix="/api/v1/saal-spruch", tags=["spiel"])
app.include_router(
    saal_spruch_admin_router,
    prefix="/api/v1/moderation/saal-sprueche",
    tags=["moderation"],
)
# Konter-Probe (#786), ohne Anmeldung, nur lesend; der Tipp bleibt im Browser
app.include_router(konter_probe_router, prefix="/api/v1/konter-probe", tags=["spiel"])
app.include_router(sperren_router, prefix="/api/v1/sperren", tags=["moderation"])
app.include_router(health_router, prefix="/api/v1", tags=["monitoring"])
app.include_router(feedback_router, prefix="/api/v1/feedback", tags=["feedback"])
app.include_router(
    einladungen_router, prefix="/api/v1/einladungen", tags=["einladungen"]
)
app.include_router(teams_router, prefix="/api/v1/teams", tags=["teams"])
app.include_router(gegenlesen_router, prefix="/api/v1/gegenlesen", tags=["gegenlesen"])
app.include_router(varianten_router, prefix="/api/v1/varianten", tags=["varianten"])
# Nur fuer den nginx im Frontend-Image (#360); am BFF gesperrt (EndpointPolicy.Blocked).
app.include_router(
    linkvorschau_router, prefix="/api/v1/linkvorschau", tags=["linkvorschau"]
)
app.include_router(
    spracherkennung_router, prefix="/api/v1/spracherkennung", tags=["spracherkennung"]
)
app.include_router(
    kuerzungsvorschlag_router,
    prefix="/api/v1/kuerzungsvorschlag",
    tags=["kuerzungsvorschlag"],
)
app.include_router(
    art9_einwilligung_router,
    prefix="/api/v1/art9-einwilligung",
    tags=["art9-einwilligung"],
)
app.include_router(
    nutzungsbedingungen_router,
    prefix="/api/v1/nutzungsbedingungen",
    tags=["nutzungsbedingungen"],
)
app.include_router(
    herkunft_pruefen_router,
    prefix="/api/v1/herkunft-pruefen",
    tags=["herkunft-pruefen"],
)
app.include_router(aufrufe_router, prefix="/api/v1/aufrufe", tags=["aufrufe"])

# Betriebskennzahlen unter /metrics (#420). Zuletzt hinzugefuegt, also aussen: Die
# Middleware zaehlt auch, was das Rate-Limit abweist. Am BFF ist /metrics gesperrt.
from api.betriebskennzahlen import einbinden as betriebskennzahlen_einbinden

betriebskennzahlen_einbinden(app)


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting FastAPI server")

    uvicorn.run(app, host="0.0.0.0")
