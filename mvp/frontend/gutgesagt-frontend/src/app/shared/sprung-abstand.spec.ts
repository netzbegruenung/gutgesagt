import { sprungAbstand } from './sprung-abstand';

describe('sprungAbstand', () => {
  afterEach(() => document.documentElement.style.removeProperty('scroll-padding-top'));

  it('nimmt scroll-padding-top vom <html>, damit der Anker nicht unter dem klebenden Kopf landet', () => {
    document.documentElement.style.setProperty('scroll-padding-top', '65px');
    expect(sprungAbstand()).toEqual([0, 65]);
  });

  it('ohne scroll-padding (Desktop) kein Abstand', () => {
    document.documentElement.style.setProperty('scroll-padding-top', 'auto');
    expect(sprungAbstand()).toEqual([0, 0]);
  });
});
