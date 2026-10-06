# River Raid

A tribute to the 1982 Activision classic, written in Python with pygame.

Fly up an endless river, shoot ships, helicopters, jets and bridges, and keep
your fuel up by flying over FUEL depots.

## Run

```
pip install pygame
python riverraid.py
```

## Levels

Choose on the title screen with ↑ / ↓ or keys 1–4. Each level keeps its own high score.

| Level | Lives | Description |
|---|---|---|
| Beginner | 5 | Wide river, slow enemies, slow fuel drain |
| Medium | 3 | The classic experience |
| Hard | 3 | Narrow river, fast enemies, thirsty engine |
| Principal | 2 | Only for the brave — no mercy |

## Controls

| Key | Action |
|---|---|
| ← → | Steer |
| ↑ | Speed up |
| ↓ | Slow down |
| Space | Fire |
| P | Pause |
| Esc | Quit |

## Rules

- Touching the riverbank, an enemy or a bridge destroys your plane.
- Fuel runs out over time — fly over FUEL depots to refill (or shoot them for points).
- Shoot a bridge to set a checkpoint; after losing a life you restart past the last bridge you destroyed.
- The river gets narrower and enemies get faster with every bridge.
- Extra life every 10,000 points.

| Target | Points |
|---|---|
| Ship | 30 |
| Helicopter | 60 |
| Fuel depot | 80 |
| Jet | 100 |
| Bridge | 500 |
