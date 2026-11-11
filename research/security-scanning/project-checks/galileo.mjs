// Run only the reviewed numerical core of the pinned public author download.
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const html = readFileSync(process.argv[2]);
const sha256 = createHash('sha256').update(html).digest('hex');
assert.equal(sha256, 'c86d847b235bdf1d37819eb6dc0d65b344ddd6cf7b25d3b3471e020b51bb9652');
const core = /<script id="og-core">([\s\S]*?)<\/script>/.exec(html.toString('utf8'))[1];
const game = vm.runInNewContext(core + '\nOGCore', {}, {timeout: 5000});
const radius = 850e6;
const duration = 3600;
const initial = [radius, 0, 0, 0, Math.sqrt(game.GMJ / radius), 0];
const state = Float64Array.from(initial);
const step = game.advance(state, 0, duration, null, {maxSteps: 100000});
assert.equal(step.t, duration);
assert.equal(step.hit, -1);

// Independent planar velocity-Verlet integrator. The physical assumptions and
// constants match the game's prescribed circular moons. No game force code is used.
function acceleration(t, x, y) {
  const central = -game.GMJ / Math.hypot(x, y) ** 3;
  let ax = central*x, ay = central*y;
  for (const moon of game.MOONS) {
    const theta = moon.ph0 + 2*Math.PI*t/moon.P;
    const dx = moon.a*Math.cos(theta)-x, dy = moon.a*Math.sin(theta)-y;
    const scale = moon.GM / Math.hypot(dx,dy) ** 3;
    ax += scale*dx;
    ay += scale*dy;
  }
  return [ax, ay];
}
function coast(dt) {
  let [x, y, , vx, vy] = initial;
  let [ax, ay] = acceleration(0,x,y);
  for (let t=0; t<duration; t+=dt) {
    x += vx*dt + ax*dt*dt/2;
    y += vy*dt + ay*dt*dt/2;
    const [nx, ny] = acceleration(t+dt,x,y);
    vx += (ax+nx)*dt/2;
    vy += (ay+ny)*dt/2;
    ax = nx; ay = ny;
  }
  return [x,y,vx,vy];
}
const coarse = coast(1), fine = coast(0.5);
const referenceDelta = Math.hypot(coarse[0]-fine[0], coarse[1]-fine[1]);
const positionError = Math.hypot(state[0]-fine[0], state[1]-fine[1], state[2]);
const velocityError = Math.hypot(state[3]-fine[2], state[4]-fine[3], state[5]);
console.log(JSON.stringify({sha256, coast_seconds: duration, game_steps: step.steps,
  reference_step_halving_m: referenceDelta, endpoint_difference_m: positionError,
  velocity_difference_m_s: velocityError},null,2));
assert.ok(referenceDelta < 0.1 && positionError < 1 && velocityError < 0.001);
