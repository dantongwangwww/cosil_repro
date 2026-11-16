# LocBench560 ablation v2 execution source checkpoint

This independent source and documentation snapshot preserves the complete v1 tree at abdb3cfa011bb411628fbfd33914ebac4f3448ec. The v1 startup failure and run are retained. No benchmark arm was started in v1; separate synthetic startup probes are disclosed in the engineering revision.

v2 adds genuine preflight-progress heartbeat, controlled SIGTERM cleanup, metadata-only preparation bridging and inherited session accounting (2 used, at most 1 remains). It does not relax the 180-second watchdog or 3600-second arm limit. The560 tasks,557 ready input bytes, interventions, weights, LoRA, calibrated temperature/thresholds, prompts, tools, nonthinking mode and scoring protocol are unchanged. All model-method source is byte-identical to v1 after module-prefix normalization, as independently checked.

The24 Python sources passed150 synthetic/unit tests, with stable source SHA and no v2 model/GPU calls. Independent final source/input/pin review passed. The111 absolute source/document bindings cover old84 dependencies plus27 v2 files. Remote publication is only recoverability evidence: local execution freeze, actual admission, capacity probes and engineering canary remain mandatory before benchmark execution.

Only code, README/interface contract, aggregate engineering documentation and this safe checkpoint metadata are published. Exclude protocol.json/results, datasets/gold, rosters/CSV/predictions, raw logs, model weights, credentials, sealed test and manuscripts. No upstream Git or existing branch is rewritten.
