Follow AGENTS.md "Start here".

git pull --rebase. Log a `running` entry for your section and method, push it,
then list again — if that target is already claimed, take another.

Start from `explog list --verdict promising`, then `abandoned`: a lead with
numbers beats a fresh idea. Hypotheses can come from anywhere; a direction
earns its place by having a test you can state. Measure cheap first
(fitness.windowed for partial stretches, stats.ioc/chi_squared for
intermediates) to size what a direction is worth spending, not to close it —
a flat result bounds your coverage, so record the bound. Subagents when two
directions don't need each other's results; a background script when a sweep
would otherwise idle you. Work in research/attacks/<slug>/, bulk output in
its out/.

Finish by resolving your entry to a verdict carrying the numbers. Keep the scripts and a
short note even when it went nowhere. Then drift check, tests, commit, push.
