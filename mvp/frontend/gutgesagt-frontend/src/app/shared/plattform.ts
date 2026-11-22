/**
 * Die Plattform eines Links, aus Hostname und - fuer Mastodon - Pfad abgeleitet.
 *
 * Zweck ist ein Herkunfts-Tag: Die Karte im Fangkorb zeigt, woher ein Einwurf
 * stammt, und der Filter waehlt danach aus. Benannt sind die Plattformen, von
 * denen haeufig eingeworfen wird; alles andere ist "Web".
 */
export type Plattform = 'instagram' | 'youtube' | 'tiktok' | 'threads' | 'x' | 'bluesky' | 'mastodon' | 'web';

/** Alle Plattformen in Anzeigereihenfolge. */
export const PLATTFORMEN: ReadonlyArray<{ wert: Plattform; name: string }> = [
  { wert: 'instagram', name: 'Instagram' },
  { wert: 'youtube', name: 'YouTube' },
  { wert: 'tiktok', name: 'TikTok' },
  { wert: 'threads', name: 'Threads' },
  { wert: 'x', name: 'X' },
  { wert: 'bluesky', name: 'Bluesky' },
  { wert: 'mastodon', name: 'Mastodon' },
  { wert: 'web', name: 'Web' },
];

const DOMAINS: ReadonlyArray<[Plattform, string[]]> = [
  ['instagram', ['instagram.com']],
  ['youtube', ['youtube.com', 'youtu.be']],
  ['tiktok', ['tiktok.com']],
  ['threads', ['threads.net', 'threads.com']],
  ['x', ['x.com', 'twitter.com']],
  ['bluesky', ['bsky.app']],
  // Mastodon ist foederiert und hat keine eigene Domain. Hier stehen grosse und
  // fuer Gruene naheliegende Instanzen (am 22.11.2026 per /api/v2/instance als
  // Mastodon belegt); Posts anderer Instanzen erkennt MASTODON_PFAD.
  [
    'mastodon',
    [
      'mastodon.social',
      'mastodon.online',
      'mstdn.social',
      'chaos.social',
      'social.tchncs.de',
      'troet.cafe',
      'mastodon.green',
      'gruene.social',
    ],
  ],
];

/**
 * Heuristik fuer Mastodon-Posts auf beliebigen Instanzen: die Post-Adresse
 * `/@name/123` (auch `/@name@andere.instanz/123`, wenn eine Instanz einen
 * fremden Post zeigt) und die ActivityPub-Form `/users/name/statuses/123`.
 * Greift erst nach den bekannten Domains, damit etwa threads.net/@a/post/1 oder
 * tiktok.com/@a/video/1 bei ihrer Plattform bleiben. Ein blosses Profil (`/@name`)
 * zaehlt auf fremden Hosts nicht - das sagt zu wenig.
 */
const MASTODON_PFAD = /^\/(@[^/@]+(@[^/]+)?|users\/[^/]+\/statuses)\/\d+\/?$/;

/**
 * Die Plattform zu einem Link, oder null ohne Link.
 *
 * Subdomains zaehlen mit (m.youtube.com, vm.tiktok.com), aehnlich klingende
 * Domains nicht (notinstagram.com). Mastodon-Posts erkennt zusaetzlich ihr
 * Pfad auf jedem Host (MASTODON_PFAD). Eine unlesbare Adresse ist trotzdem ein
 * Link und zaehlt als Web.
 */
export function plattformAusUrl(url: string | null | undefined): Plattform | null {
  const adresse = url?.trim();
  if (!adresse) {
    return null;
  }

  let host: string;
  let pfad: string;
  try {
    const geparst = new URL(adresse);
    host = geparst.hostname.toLowerCase();
    pfad = geparst.pathname;
  } catch {
    return 'web';
  }

  for (const [plattform, domains] of DOMAINS) {
    if (domains.some((domain) => host === domain || host.endsWith(`.${domain}`))) {
      return plattform;
    }
  }
  return MASTODON_PFAD.test(pfad) ? 'mastodon' : 'web';
}

export function plattformName(plattform: Plattform): string {
  return PLATTFORMEN.find((eintrag) => eintrag.wert === plattform)?.name ?? 'Web';
}
