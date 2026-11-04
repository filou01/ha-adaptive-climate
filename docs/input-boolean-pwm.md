# input_boolean PWM outputs — preview 4

`v0.67.1-pwm.4` accepts one non-inverted `input_boolean.*` heater output per
HEAT-only PWM zone alongside the existing `switch.*` support. The user's
NSPanel-Easy/ESPHome relay-following-helper topology previously caused the
group to enter `unsupported zone` fallback solely because of the helper domain.
Mixed groups are supported. No YAML change or entity renaming is required.

Only the runtime domain eligibility check changes. Commands still enter the
serialized `HeaterController` and its existing `homeassistant.turn_on/turn_off`
service path, HA-state confirmation, minimum switching times, cancellation,
delivery accounting and learning bookkeeping. Unsupported analog domains,
multiple/inverted outputs, cooling/AC and unavailable HA outputs retain their
existing rejection/fallback behavior. Both overlap strategies are unchanged.
All earlier learning/startup fixes are included; coordination remains opt-in.

**Observation limit:** a helper confirms its requested state, not the physical
NSPanel relay. Delivery accounting and pump/overlap estimates follow helper
ON/OFF time. A panel outage, delayed ESPHome update or manual relay override
may diverge from that state without being visible to the integration. This
change does not add relay feedback, downstream availability checks or ESPHome
configuration. See [the user guide](pump-aware-pwm.md#using-an-input_boolean-relay-proxy).

## Verification

Source/test commit: `6f594b1aff063fee2016df58aaa7aac223e482b7`.
The release adds documentation to this exact source/test tree.

The existing eleven real-controller/HA-adapter tests now run for both output
domains. Six further cases verify mixed-domain ON/OFF through the existing
service path and continued rejection of analog output domains. The resulting
28 tests cover pulse preparation, minimum effective duration, delivered-time
accounting after target changes, zero-demand cancellation, unavailable outputs,
shared outputs, rename/shutdown, stale-temperature safety and failed-service
fallback without duplicate starts. Existing immediate-demand and race tests
remain in the full suite.

| Validation | Result |
| --- | --- |
| Windows real-controller HA integration boundary tests | 28 passed |
| Full Linux Python 3.11.18 suite | 3572 passed, 11 skipped; exit 0 |
| Full Linux Python 3.12.3 suite | 3572 passed, 11 skipped; exit 0 |
| Ruff check / format | PASS; 250 files formatted |
| Pyright source | PASS; 0 errors |
| GitHub test/lint/type matrix | [QUEUED](https://github.com/filou01/ha-adaptive-climate/actions/runs/41878351264) |
| HACS | [QUEUED](https://github.com/filou01/ha-adaptive-climate/actions/runs/41878351448) |
| hassfest | [QUEUED](https://github.com/filou01/ha-adaptive-climate/actions/runs/41878351443) |

The full suite also includes the eight deterministic 24-hour legacy/coordinated
PWM replays. Their [existing model and limitations](architecture/pump-aware-pwm-verification.md)
remain unchanged. They simulate binary output timing, not an ESPHome network.

**NOT RUN:** physical NSPanel/ESPHome relay-following-helper test, real HA/device
end-to-end validation, physical pump/flow measurements, supervised 24-hour
heating, Raspberry Pi performance, variable maintenance-duty replay with real
actuator timing, full Windows suite for preview 4 and wiki publication.
Queued GitHub validations are not counted as executed or passed.

## Changed files, installation and rollback

- `custom_components/adaptive_climate/managers/pwm_coordination.py`: admit
  `switch` and `input_boolean` output domains; clarify rejection message.
- `tests/test_pwm_ha_integration.py`: exercise both domains and mixed groups.
- README, user guide, this report and combined PR draft: compatibility,
  proxy-state limitations and validation evidence.

Back up integration/configuration/learning storage, select
[`v0.67.1-pwm.4` in HACS prereleases](https://github.com/filou01/ha-adaptive-climate/releases/tag/v0.67.1-pwm.4),
then restart HA. Previous fallback is latched until restart. For the monitored
restart, first turn participating thermostats OFF through HA and verify helpers
and downstream relays are OFF. Resume HEAT after startup. No learning reset,
storage migration or PID gain change is introduced in preview 4.

To return to independent control, disable coordination and restart. For code
rollback reinstall unchanged preview 3 and restart; input_boolean groups will
again fall back there. Existing learning data is compatible between previews
3 and 4. The semantic-release-managed manifest remains at `0.67.0`; the release
tag identifies the fork preview. No upstream PR is opened.
