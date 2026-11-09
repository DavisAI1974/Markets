# Four-date extension replication

Finish the missing continuous precursor scan and primer diagnostics before timestamp assembly or paper configuration. Code runs only on GitHub-hosted runners. Results belong in markets-data.

The two historical analysis modules are copied from Markets `407a23379`; only explicit dependency-injection arguments are added. Numerical functions, predicates, grids and outcomes are unchanged. The date adapter pins inputs, validates SHA256, retains finalization-only births, and reproduces October 18 before running the other dates. The family-start population has separate missing-input status; it is never replaced by dipoles.

Run `python agent-pass/replication/finish_four_day_extensions.py --output <new-path>` on the hosted runner with numpy, pandas, matplotlib and pytest. All source reads and output hashes are recorded.
