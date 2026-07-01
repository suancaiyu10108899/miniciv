# Rust Kernel Architecture Plan

## Principles
- AI-first: every game state must be serializable for training
- ECS pattern for units/terrain (Bevy or custom)
- Python bindings via PyO3 for prototyping/training
- Headless mode for fast simulation

## Crate Structure
miniciv-core/     — game logic, no I/O
miniciv-render/   — ASCII/HTML/GPU rendering
miniciv-server/   — WebSocket game server
miniciv-ai/       — AI implementations + training
miniciv-py/       — PyO3 Python bindings

## Core Module Tree
src/
  lib.rs          — re-exports
  game.rs         — GameState, step(), init()
  map.rs          — MapGen, Terrain, Grid
  unit.rs         — Unit, UnitType, stats
  combat.rs       — CombatResolver
  economy.rs      — Economy, resources
  tech.rs         — TechTree, research
  fow.rs          — Fog of War
  snapshot.rs     — Serialize/Deserialize
  constants.rs    — Tuning parameters
  eval.rs         — Batch evaluation

## Key Design Decisions
1. Copy-on-write GameState for MCTS/rollouts
2. Deterministic RNG (seedable)
3. Action abstraction: trait Action { apply(&mut GameState) }
4. AI trait: trait Agent { fn decide(&GameState) -> Vec<Action> }
5. Arena allocator for units to minimize alloc overhead

## Performance Targets
- 100k games/second for Random vs Random (single core)
- 1k games/second for FlatMC (single core)
- Sub-ms game state deep copy
- Memory < 1KB per game state
