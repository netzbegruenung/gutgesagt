/**
 * Absatz „Spielgefühl“ der Datenschutzerklärung (Schalter `spielgefuehl_buehne`). Mit
 * Schalter ersetzt er unter „Punkte“ die Einwilligungsteile zu Punkten, Abzeichen am Namen
 * und Rangliste; die Rechenregeln (Punkte, Meilensteine, Muster-Hinweise) bleiben stehen.
 *
 * Wortlaut von Jura (26.11., vorläufig zum Bauen, endgültig vor dem Go), mit den Sätzen
 * zur Namenswahl aus der Nachsteuerung vom selben Abend und der Ergänzung zum Schutz gegen
 * Absprachen aus der Antwort auf die Fachfragen zu PR #849; Einleitung und Sockelsatz nach
 * Jura vom 27.11. (vorläufig). Kennung des Fragewortlauts:
 * spielgefuehl-2026-11-26 (backend domain/spielgefuehl.py).
 */
export const DSE_SPIELGEFUEHL_TITEL = 'Spielgefühl.';

/**
 * Der Absatz als Einleitung und Liste der angebotenen Stufen (Jura zum Gamification-Gegencheck,
 * 26.11.; Einleitung nach der Sammelrunde 27.11., ohne doppeltes „Spielgefühl“ hinter dem
 * fett gesetzten Titel im Fließtext): Der Listenpunkt zur Stufe Rangliste steht nur,
 * solange der Schalter `rangliste` wirksam an ist, sonst nach der Liste der Satz
 * DSE_SPIELGEFUEHL_OHNE_RANGLISTE. Danach DSE_SPIELGEFUEHL_SCHLUSS.
 */
export const DSE_SPIELGEFUEHL_EINLEITUNG = 'Du wählst selbst, ob und wie du mitspielst:';

export const DSE_SPIELGEFUEHL_AUS = '‚Aus‘: Wir berechnen nichts.';

export const DSE_SPIELGEFUEHL_NUR_FUER_MICH =
  '‚Nur für mich‘: Wir berechnen Punkte und Meilensteine, die nur du siehst (wie unten ' +
  'beschrieben), und mit deiner Stufe gilt auch der Schutz gegen Absprachen (unten).';

export const DSE_SPIELGEFUEHL_RANGLISTE =
  '‚In der Saison-Rangliste mitspielen‘: Zusätzlich stehst du in der Rangliste ' +
  'der laufenden Saison mit dem Namen, den du wählst, also deinem Anzeigenamen oder einem ' +
  'zufällig vergebenen Ranglistennamen, sowie deinem Platz, deinen Punkten und deinen ' +
  'Abzeichen; Abzeichen zeigen wir nirgends sonst. Die Rangliste sehen nur, wer selbst ' +
  'mitspielt, und erst ab zehn Teilnehmenden: die ersten zehn und den eigenen Platz. Den ' +
  'Zufallsnamen würfeln wir beim ersten Mal und auf deinen Wunsch neu; den Namen kannst du ' +
  'unter „Meine Beiträge“ jederzeit umstellen.';

export const DSE_SPIELGEFUEHL_OHNE_RANGLISTE =
  'Die Stufe ‚In der Saison-Rangliste mitspielen‘ bieten wir gerade nicht an.';

export const DSE_SPIELGEFUEHL_SCHLUSS =
  'Jede Antwort speichern wir mit Stufe, deiner ' +
  'Namenswahl, Zeitpunkt, Kennung des Wortlauts und, falls vorhanden, deinem Zufallsnamen als ' +
  'Nachweis; Punkte und Plätze speichern wir nicht, sondern berechnen sie bei jedem Abruf. ' +
  'Änderst du die Stufe, wirkt das sofort. Zweck: dir und, wenn du mitspielst, den anderen ' +
  'Mitspielenden zeigen, wie deine Mitwirkung wirkt. Rechtsgrundlage: deine ausdrückliche ' +
  'Einwilligung (Art. 6 Abs. 1 lit. a, Art. 9 Abs. 2 lit. a DSGVO). Dauer: die Antworten bis ' +
  'zur Löschung deines Kontos.';

/**
 * Steht immer, auch ohne Schalter (Jura 26.11., Wortlaut nach der Sammelrunde 27.11.): Eine
 * gespeicherte Wahl bleibt, wenn wir die Funktion ausschalten, und lässt sich in den
 * Datenschutz-Einstellungen ausschalten.
 */
export const DSE_SPIELGEFUEHL_SOCKEL =
  'Hast du beim Spielgefühl eine Stufe gewählt, speichern wir deine Wahl, deine Namenswahl, ' +
  'gegebenenfalls deinen Zufallsnamen, die Fassung des Einwilligungstexts und den Zeitpunkt. ' +
  'Ausschalten kannst du das jederzeit in deinen Datenschutz-Einstellungen, auch wenn wir die ' +
  'Funktion gerade nicht anbieten.';
