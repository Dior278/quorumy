# Reliability

| Situation | Behavior |
| --- | --- |
| Connection dropped | Automatic reconnect, draft kept, and the session stays paused until confirmation |
| Research no longer useful | Cancel from **Agents → Research**, which also stops the related reports |
| Research too long | 120-second limit by default, set with `policy.mission_timeout_seconds` |
| Tool failure | Visible error state; a mission does not succeed without a result |
| Result already available | Reuse is marked and sources are kept; freshness is not rechecked |
| Answer from research | Original request and links in **Where this answer came from** |
| Voice interrupted | Spoken, interrupted, and written answers stay distinct; recent repeats are filtered |

Words spoken during a drop are not reconstructed. A quote makes checking easier and does not guarantee the model’s interpretation. Cancellation can happen after a provider call has already been billed.

Tests cover failures, timeouts, cancellations, sources, reconnections, and layouts at 320, 390, 768, and 1440 px. See the [check commands](EVALUATION.md) and the [in-call audio test](demo-video.md).
