import { SearchResponse } from '../services/dtos/searchDtos';
import { andereTonlagen } from './andere-tonlage';

function kommentar(id: string, stil: string | null, aussage: string | null, zweck = 'kommentarspalte'): any {
  return {
    score: 1,
    statement_id: aussage,
    statement_text: aussage ? `Aussage ${aussage}` : null,
    content_type: 'commentary',
    commentary_result: { id, title: `Titel ${id}`, text: 'Text', created: '2026-11-20T10:00:00Z', style: stil, zweck },
  };
}

function antwort(...kommentare: any[]): SearchResponse {
  return { commentary_search_results: kommentare } as unknown as SearchResponse;
}

describe('andereTonlagen (#785)', () => {
  it('nennt je Kommentar die erste Antwort zur selben Aussage in anderem Stil', () => {
    const a = kommentar('a', 'sachlich', 's1');
    const b = kommentar('b', 'sachlich', 's1');
    const c = kommentar('c', 'humorvoll', 's1');
    const tonlagen = andereTonlagen(antwort(a, b, c));

    expect(tonlagen.get(a)).toEqual({ id: 'c', stil: 'humorvoll' });
    expect(tonlagen.get(b)).toEqual({ id: 'c', stil: 'humorvoll' });
    expect(tonlagen.get(c)).toEqual({ id: 'a', stil: 'sachlich' });
  });

  it('keine bei nur einem Stil, ohne Stil oder ohne Aussage', () => {
    const a = kommentar('a', 'sachlich', 's1');
    const b = kommentar('b', 'sachlich', 's1');
    const ohneStil = kommentar('c', null, 's1');
    const ohneAussage = kommentar('d', 'humorvoll', null);

    expect(andereTonlagen(antwort(a, b, ohneStil, ohneAussage)).size).toBe(0);
  });

  it('nicht ueber Aussagen hinweg', () => {
    const a = kommentar('a', 'sachlich', 's1');
    const b = kommentar('b', 'humorvoll', 's2');

    expect(andereTonlagen(antwort(a, b)).size).toBe(0);
  });

  it('nicht von einer Antwort in Kommentarspalten auf eine fuer die eigenen Leute', () => {
    const a = kommentar('a', 'sachlich', 's1');
    const b = kommentar('b', 'bissig', 's1', 'eigene_leute');

    expect(andereTonlagen(antwort(a, b)).size).toBe(0);
  });

  it('ohne Antwort leer', () => {
    expect(andereTonlagen(null).size).toBe(0);
  });
});
