import { Container, RenderTexture, Renderer, Sprite } from 'pixi.js';

/**
 * PersistencePass — phosphor afterglow & motion blur WITHOUT smearing.
 *
 * The previous implementation fed the *entire composite* back into itself, so
 * bright objects accumulated into a foggy halo and lost all definition. The fix
 * is to separate the **crisp scene** from the **trail**:
 *
 *   1. Render the live scene once into `sceneRT` (always crisp, never fed back).
 *   2. Build a trail buffer: `trail = prevTrail × persistence + sceneRT × deposit`
 *      (ping-pong). This is the only feedback loop — a decaying phosphor ghost.
 *   3. Output = bloomed trail (soft glow underneath) + crisp scene on top.
 *
 * Because the crisp scene is re-drawn fresh every frame and layered OVER the
 * trail, the dolphin / FFT / waves keep hard edges while still leaving a short
 * luminous afterglow behind them as they move. No more whole-scene fog.
 *
 * `persistence` controls trail length (lower = shorter afterglow) and `deposit`
 * controls how much new light is laid down each frame.
 */
export class PersistencePass {
  /** Container holding the visible result (add this to the scene). */
  readonly output = new Container();
  /** Wrapper around the trail sprite — post-processing glow attaches here. */
  readonly glowWrap = new Container();
  /** Live renderers are parented here (rendered into sceneRT, not displayed). */
  readonly live = new Container();

  private sceneRT: RenderTexture;
  private trailA: RenderTexture;
  private trailB: RenderTexture;
  private prevTrail: RenderTexture;
  private currTrail: RenderTexture;

  private readonly fadeSprite: Sprite;     // prevTrail × persistence
  private readonly depositSprite: Sprite;  // sceneRT × deposit (into trail)
  private readonly trailOutSprite: Sprite; // currTrail (soft glow, below)
  private readonly crispOutSprite: Sprite; // sceneRT (sharp, on top)

  private readonly trailComposite = new Container();

  /** Trail length (0 = none, 1 = infinite). Kept SHORT to avoid fog. */
  persistence = 0.5;
  /** How much fresh light is deposited into the trail each frame. */
  deposit = 0.35;

  constructor(width: number, height: number) {
    this.sceneRT = RenderTexture.create({ width, height });
    this.trailA = RenderTexture.create({ width, height });
    this.trailB = RenderTexture.create({ width, height });
    this.prevTrail = this.trailA;
    this.currTrail = this.trailB;

    this.fadeSprite = new Sprite(this.prevTrail);
    this.depositSprite = new Sprite(this.sceneRT);
    this.trailOutSprite = new Sprite(this.currTrail);
    this.crispOutSprite = new Sprite(this.sceneRT);

    // Trail feedback loop: faded previous + fresh deposit.
    this.trailComposite.addChild(this.fadeSprite);
    this.trailComposite.addChild(this.depositSprite);

    // Visible output: bloomed trail underneath, crisp scene on top.
    this.glowWrap.addChild(this.trailOutSprite);
    this.output.addChild(this.glowWrap);
    this.output.addChild(this.crispOutSprite);
  }

  /** Advance one frame: capture the crisp scene, update the trail, refresh output. */
  update(renderer: Renderer): void {
    // 1. Capture the current crisp live frame.
    renderer.render({ container: this.live, target: this.sceneRT, clear: true });

    // 2. Trail = faded previous + fresh deposit (the only feedback path).
    this.fadeSprite.texture = this.prevTrail;
    this.fadeSprite.alpha = this.persistence;
    this.depositSprite.texture = this.sceneRT;
    this.depositSprite.alpha = this.deposit;
    renderer.render({ container: this.trailComposite, target: this.currTrail, clear: true });

    // 3. Output: soft glow (trail) below, sharp scene on top.
    this.trailOutSprite.texture = this.currTrail;
    this.crispOutSprite.texture = this.sceneRT;

    // Swap trail buffers for the next frame.
    const tmp = this.prevTrail;
    this.prevTrail = this.currTrail;
    this.currTrail = tmp;
  }

  destroy(): void {
    this.sceneRT.destroy(true);
    this.trailA.destroy(true);
    this.trailB.destroy(true);
    this.output.destroy({ children: true });
    this.trailComposite.destroy({ children: false });
  }
}
