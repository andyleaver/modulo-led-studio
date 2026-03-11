Modulo LED Studio – Current Development Status
Current Focus: UI Workflow & Layout Polish
Modulo LED Studio is currently in the final interface refinement stage.
The core engine architecture, rendering pipeline, rules system, mapping model, and export paths are now largely complete. Development focus has shifted to polishing the application interface and user workflow.
Current work centers on ensuring the UI reflects the intended creation flow and that all controls are properly wired and usable.
Active Work Areas
UI Workflow Alignment
Tabs and panels are being arranged to match the natural order of building a project.
On a clean launch or new project, the interface should guide the user through creation in a logical sequence.
Typical workflow path:
Layout / Surface Setup
→ Layers
→ Behaviour / Rules
→ Signals / Modulation
→ Preview
→ Export
All tabs must be fully wired and functional, with no placeholder panels or inactive controls.
Layout & Interaction Polish
Current UI improvements include:
Fixing non-responsive controls
Ensuring panels can resize and dock correctly
Correct default window layout on startup
Removing hidden or inaccessible UI elements
Ensuring buttons, dropdowns, and controls are wired to the engine
The goal is that every visible control performs a real action.
Clean Startup State
Modulo is designed to always launch in a clean creation-ready state:
No autosave restore
No demo project injection
Default strip layout with 144 LEDs
Zero layers
Preview starts empty (black)
This ensures users always begin with a known baseline environment.
Era System (Temporarily Disabled)
The LED Era onboarding system exists in the codebase but is currently disabled while UI work is completed.
It will return once the interface structure is finalized.
Development Principle
Modulo follows a single canonical engine path:
One schema
One runtime
One preview path
One export path
Legacy compatibility is handled only through one-time migration, never through parallel runtimes.