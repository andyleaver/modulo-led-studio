What is currently being worked on?
Modulo is in a phase called “Opening All Doors.”
This phase is not about adding new behaviours or effects.
It is about removing architectural ceilings.
The goal is to ensure that every controllable parameter in the system:
Is reachable.
Is observable.
Is routable.
Is export-consistent.
Has no hidden or shadow duplicates.
Behaves identically in preview and on hardware.
This is an architecture hardening phase.
What Does “Opening All Doors” Mean?
In practical terms, it means:
If something can be adjusted, it must also be:
Targetable by Rules.
Targetable by Modulators.
Visible in diagnostics.
Resolved through a single canonical path.
Evaluated deterministically.
Export-safe (or clearly marked if not).
There are no privileged parameters. There are no isolated systems. There are no hidden internal-only values that users cannot access.
If it exists, it must have a canonical address and a defined capability.
What Will Be Possible When Complete?
When “All Doors Are Open,” the following will be true:
1. Unified Parameter System
Every adjustable value in Modulo will:
Have a canonical address.
Declare whether it is writable.
Declare whether it is modulate-able.
Declare whether it is export-safe.
Declare whether it persists.
This includes:
Layer parameters
Operator parameters
PostFX parameters
Behaviour parameters
System variables
Project-level settings
2. Cross-System Control
The following will be possible:
Rules can mutate any writable parameter.
Modulators can drive any compatible parameter.
Behaviours can read canonical signals and system state.
Operators can be driven by modulation or logic.
PostFX can respond to behaviours or rules.
Nothing is siloed.
3. Deterministic Evaluation
All systems will run through a defined order:
Signals gathered
Behaviours updated
Rules applied
Modulators resolved
Operators applied
PostFX applied
Frame rendered
Preview and export must follow the same order.
No hidden preview-only shortcuts.
4. Export Parity
Exported firmware will:
Use the same logical parameter resolution path.
Respect capability gating per target.
Clearly report blocked features.
Produce deterministic behaviour identical to preview.
Export generates real firmware, not configuration files.
What This Is Not
Opening All Doors does not mean:
Turning Modulo into a general game engine.
Expanding beyond LED control as a primary goal.
Adding complexity for its own sake.
Modulo remains:
A behaviour-first authoring system for addressable LEDs.
The architecture is being hardened so that the ceiling imposed by traditional LED apps is permanently removed.
Why This Matters
Most LED software stops at:
Effect selection
Limited parameters
Hardcoded behaviour
Shallow time
Visual-only control
Modulo is built to allow users to design systems, not select patterns.
Opening All Doors ensures that:
No artificial limits remain.
No internal wiring gaps cause inconsistency.
No feature is inaccessible once it exists.
When complete, Modulo will provide full behavioural control over addressable LEDs, without requiring users to write firmware manually.