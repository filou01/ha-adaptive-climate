# Sensors & Monitoring

<!-- pump-aware-fork-preview:start -->
## Fork preview: coordinated PWM diagnostics

**Fork preview, not an upstream release feature.** The following information applies to `filou01/ha-adaptive-climate`, branch `codex/pump-aware-pwm`, [preview v0.67.1-pwm.8](https://github.com/filou01/ha-adaptive-climate/releases/tag/v0.67.1-pwm.8). Do not assume the upstream release supports this configuration.

Participating climate entities expose a `pwm_coordination` attribute. These
are scheduling/accounting diagnostics, not a physical pump or flow sensor.

| Fields | Interpretation |
| --- | --- |
| `mode`, `reason`, `overlap_strategy`, `generation` | Group ownership, fallback and plan lifecycle |
| `requested_seconds`, `observed_on_seconds`, `remaining_credit_seconds`, `cancelled_balance_seconds` | Signed balance: requested = observed + remaining credit + cancelled |
| `last_start_epoch`, `last_ordinary_start_epoch`, `suppressed_ordinary_starts` | Actual/ordinary start allowance; suppression counts are not hardware command counts |
| `priority_start_count`, latency/blocking fields | Immediate eligible target/mode response and minimum-OFF blocking |
| `restart_uncertain_seconds` | Uncertain reserved budget, not verified offline runtime |
| `estimated_pump_starts`, energized/overlap counters | Estimates from observed configured output states in the current registry session |
| `projected_cyclic_starts`, `projected_high_weight_overlap_seconds` | Ideal steady-state cyclic projections |
| `runtime_projected_starts`, `runtime_start_in_seconds`, `runtime_plan_reason` | Remaining executable plan including advisory future opportunities |

`unmet_debt_seconds` is only the positive part of signed remaining credit.
Zero does not prove a zero balance. Zone ledgers and some counters survive
restart; group estimates/generation begin a new registry session. For helper
outputs, ON/OFF observations refer to the helper, not the downstream relay.
See the [diagnostic definitions and test plan](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-runtime-handovers.md#english).
<!-- pump-aware-fork-preview:end -->

The Adaptive Climate provides comprehensive monitoring through sensors, entity attributes, and reporting services.

## Performance Sensors (Per Zone)

Each zone automatically creates sensors for real-time performance monitoring:

### Heating Performance

- **`sensor.{zone}_duty_cycle`** - Current heating duty cycle (%)
  - Percentage of time heater is active over a 1-hour measurement window
  - Useful for identifying zones with high heating demand

- **`sensor.{zone}_power_m2`** - Power consumption per square meter (W/m²)
  - Normalized power consumption for zone size comparison
  - **Warning threshold:** >20 W/m² may indicate heat loss issues
  - Requires `heating_power_w` configuration

- **`sensor.{zone}_cycle_time`** - Average heating cycle time (minutes)
  - Time between heater activations
  - **Critical:** <10 min indicates too-fast cycling, check PID tuning
  - **Warning:** <15 min, consider increasing PWM period

### Learning Metrics

Track adaptive learning performance and convergence:

- **`sensor.{zone}_overshoot`** - Temperature overshoot (°C)
  - How far above setpoint temperature rises
  - Adaptive learning reduces Kp when overshoot >0.2°C

- **`sensor.{zone}_settling_time`** - Time to reach setpoint (minutes)
  - Duration from heating start to temperature stabilization
  - Slow settling (>90 min) triggers Kd increase

- **`sensor.{zone}_oscillations`** - Number of temperature oscillations
  - Temperature swings around setpoint during settling
  - >3 oscillations triggers Kp reduction and Kd increase

### Comfort Metrics

Track user comfort over time:

- **`sensor.{zone}_time_at_target`** - Time at target temperature (%)
  - Percentage of time temperature was within ±0.5°C of setpoint
  - Calculated over a 24-hour rolling window
  - Higher values indicate better comfort

- **`sensor.{zone}_comfort_score`** - Composite comfort score (0-100)
  - Combines multiple comfort metrics into a single score
  - Weights: 60% time at target, 30% low overshoot, 10% stable settling
  - >80 = excellent, 60-80 = good, <60 = needs tuning

### Heat Output Monitoring

**`sensor.{zone}_heat_output`** - Actual heat output (W)

Requires hydronic system instrumentation:
- `supply_temp_sensor` - Supply water temperature
- `return_temp_sensor` - Return water temperature
- `flow_rate_sensor` - Flow rate (L/min) OR `volume_meter_entity`
- `fallback_flow_rate` - Default flow rate when meter unavailable

Calculates heat transfer using: `Q = ṁ × c_p × ΔT`

```yaml
adaptive_climate:
  supply_temp_sensor: sensor.heating_supply_temp
  return_temp_sensor: sensor.heating_return_temp
  flow_rate_sensor: sensor.heating_flow_rate
  fallback_flow_rate: 0.5  # L/min fallback when meter unavailable
```

### Actuator Wear Tracking

Track equipment lifecycle (optional, hidden by default):

- **`sensor.{zone}_heater_wear`** - Heater actuator wear percentage
  - Requires `heater_rated_cycles` configuration (manufacturer spec)
  - Visible only when configured

- **`sensor.{zone}_cooler_wear`** - Cooler actuator wear percentage
  - Requires `cooler_rated_cycles` configuration
  - Useful for maintenance scheduling

Example configuration:
```yaml
climate:
  - platform: adaptive_climate
    name: Living Room
    heater: switch.living_room_heater
    heater_rated_cycles: 100000  # Enable wear tracking
```

## System-Wide Sensors

These sensors are created once for the entire system:

- **`sensor.adaptive_climate_total_power`** - Total heating power (W)
  - Aggregates power consumption across all zones
  - Requires `heating_power_w` configured on zone entities

- **`sensor.adaptive_climate_weekly_cost`** - Weekly heating cost (€ or $)
  - Tracks energy cost from start of week (Monday)
  - Requires `energy_meter_entity` and optionally `energy_cost_entity`
  - Resets automatically each Monday

## Climate Entity Attributes

Additional data exposed as entity attributes (visible in Developer Tools → States):

### Core Attributes (Always Present)

**PID State (for restoration):**
- `kp`, `ki`, `kd`, `ke` - Current PID gains
- `integral` - Current integral term value
- `pid_mode` - PID operating mode (on/off)
- `outdoor_temp_lagged` - Lagged outdoor temperature for Ke term

**Diagnostics:**
- `control_output` - Current PID output percentage
- `heater_cycle_count` - Total heater on→off cycles since installation
- `cooler_cycle_count` - Total cooler on→off cycles since installation

### Learning Status

- **`learning_status`** - Overall learning state
  - `idle` - Paused (contact open, humidity spike, or learning grace period)
  - `collecting` - Gathering data (< 6 cycles OR confidence below threshold)
  - `stable` - System stable (confidence ≥ threshold AND < 95%)
  - `optimized` - Very high confidence (≥ 95%)

- **`pid_history`** - List of PID adjustments (when non-empty)
  - Each entry shows timestamp, gains (kp/ki/kd/ke), reason, actor
  - Reasons include: `physics_init`, `auto_apply`, `undershoot_boost`, `chronic_approach_boost`, etc.

**Heating-type confidence thresholds for "stable" state:**
- floor_hydronic: 80%
- radiator: 70%
- convector: 60%
- forced_air: 60%

### Status Attribute

Consolidated operational status from all subsystems:

```python
"status": {
    "state": str,              # "idle" | "heating" | "cooling" | "paused" | "preheating" | "settling"
    "conditions": list[str],   # Active conditions (see below)
    "resume_at": str,          # ISO8601 timestamp when pause ends (optional)
    "setback_delta": float,    # °C adjustment during night_setback (optional)
    "setback_end": str,        # ISO8601 timestamp when night period ends (optional)
    # Debug-only fields (when debug: true):
    "humidity_peak": float,    # Peak humidity % during spike (optional)
    "open_sensors": list[str], # Contact sensor entity IDs that triggered (optional)
}
```

**Conditions (list of active states):**
- `contact_open` - One or more contact sensors are open
- `humidity_spike` - Shower/steam detected in bathroom
- `open_window` - Algorithmic open window detection triggered
- `night_setback` - Night setback period is active
- `learning_grace` - Learning paused after night setback transition

### Debug-Only Attributes

Requires `debug: true` in domain config:

**Learning metrics:**
- `convergence_confidence_pct` - Learning confidence (0-100%)
- `cycles_collected` - Number of complete heating cycles analyzed
- `duty_accumulator_pct` - PWM accumulation as % of threshold
- `current_cycle_state` - Cycle tracker state (idle/heating/settling)
- `cycles_required_for_learning` - Minimum cycles needed (constant: 6)

**Humidity detection:**
- `humidity_detection_state` - Detailed humidity detector state
- `humidity_resume_in` - Seconds until humidity pause ends

**Preheat debug attributes:**
- `preheat_active` - Whether predictive pre-heating is currently active
- `preheat_scheduled_start` - When preheat will start (ISO8601)
- `preheat_estimated_duration_min` - Estimated preheat duration
- `preheat_learning_confidence` - Preheat learning confidence (0-100%)
- `preheat_heating_rate_learned` - Learned heating rate (°C/hour)
- `preheat_observation_count` - Number of preheat observations

**Undershoot detector debug attributes:**
- `undershoot_time_hours` - Hours spent below target
- `undershoot_thermal_debt` - Accumulated thermal debt (°C·hours)
- `undershoot_ki_multiplier` - Cumulative Ki multiplier applied

**Auto mode switching debug attributes:**
- Various attributes from auto mode switching manager (when enabled)

## System Entities

### Learning Window Control

**`number.adaptive_climate_learning_window`** - Adjustable learning window (days)
- Default: 7 days
- Range: 1-30 days
- Determines how much historical data to use for PID recommendations
- Shorter window = faster adaptation, longer window = more stable tuning

## Energy Tracking

Configure energy monitoring for cost analysis:

```yaml
adaptive_climate:
  energy_meter_entity: sensor.heating_energy  # kWh meter
  energy_cost_entity: input_number.energy_price  # €/kWh or $/kWh
```

### Cost Reports

**Daily/Weekly/Monthly Reports** - `adaptive_climate.cost_report`
```yaml
service: adaptive_climate.cost_report
data:
  period: weekly  # daily, weekly, or monthly
```

Generates report with:
- Total energy consumption (kWh)
- Estimated cost based on energy price
- Per-zone breakdown (when multiple zones configured)
- Comparison to previous period (if available)

Requires `notify_service` for delivery:
```yaml
adaptive_climate:
  notify_service: notify.mobile_app
```

## Health Monitoring

### Automated Health Checks

**`adaptive_climate.health_check`** - Run system diagnostics
```yaml
service: adaptive_climate.health_check
```

Checks for:
- Fast cycling (<10 min critical, <15 min warning)
- High power consumption (>20 W/m²)
- Stalled learning (no convergence after 15+ cycles)
- Sensor availability
- PID parameter sanity (within configured limits)

Results delivered via `notify_service` if configured.

### Weekly Performance Reports

**`adaptive_climate.weekly_report`** - Automated performance summary
```yaml
service: adaptive_climate.weekly_report
```

Report includes:
- Per-zone duty cycle averages
- Total energy consumption
- Learning progress (cycles completed, recommendations applied)
- Health warnings (if any)
- Outdoor compensation convergence status

Set up automation for weekly delivery:
```yaml
automation:
  - alias: Weekly Thermostat Report
    trigger:
      - platform: time
        at: "09:00:00"
    condition:
      - condition: time
        weekday: mon
    action:
      - service: adaptive_climate.weekly_report
```

### Health Warnings

The system automatically monitors for common issues:

| Warning | Threshold | Indication | Resolution |
|---------|-----------|------------|------------|
| **Critical Cycle Time** | <10 min | System cycling too fast | Check PID tuning, increase PWM period |
| **Warning Cycle Time** | <15 min | Suboptimal cycling frequency | Consider increasing PWM period |
| **High Power** | >20 W/m² | Excessive heat demand | Check insulation, window seals, or setpoint |

Warnings are logged and included in health check/weekly reports.

## Analytics Integration

### Home Assistant Energy Dashboard

To add zones to the Energy dashboard:

1. Configure `energy_meter_entity` (domain level)
2. Go to **Settings → Dashboards → Energy**
3. Add heating zones as individual consumption sources
4. Use `sensor.{zone}_duty_cycle` for relative allocation

### Grafana/InfluxDB

Recommended sensors for time-series analysis:
- `sensor.{zone}_duty_cycle` - Heating demand over time
- `sensor.{zone}_power_m2` - Normalized power consumption
- `sensor.{zone}_overshoot` - Learning convergence tracking
- `sensor.{zone}_heat_output` - Actual heat delivery (hydronic systems)
- `sensor.{zone}_time_at_target` - Comfort tracking
- `sensor.{zone}_comfort_score` - Overall comfort metric
- Climate entity attributes (via SQL queries or state history)

### Lovelace Dashboard Example

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Living Room Performance
    entities:
      - sensor.living_room_duty_cycle
      - sensor.living_room_power_m2
      - sensor.living_room_cycle_time

  - type: history-graph
    title: Learning Metrics
    entities:
      - sensor.living_room_overshoot
      - sensor.living_room_settling_time
      - sensor.living_room_oscillations
    hours_to_show: 168  # 7 days

  - type: gauge
    entity: sensor.living_room_comfort_score
    name: Comfort Score
    needle: true
    min: 0
    max: 100
    severity:
      green: 80
      yellow: 60
      red: 0

  - type: gauge
    entity: sensor.living_room_heater_wear
    name: Heater Wear
    needle: true
    min: 0
    max: 100
    severity:
      green: 0
      yellow: 70
      red: 90
```

## Debugging Tools

### Enable Debug Mode

Expose PID internals and detailed status for troubleshooting:
```yaml
adaptive_climate:
  debug: true
```

Shows in climate entity attributes:
- Current cycle state (idle/heating/settling)
- Preheat scheduling details
- Humidity detection state machine
- Undershoot detector metrics
- Auto mode switching details

### Monitoring Learning Progress

Use `learning_status` attribute to track system state:
1. **collecting** - Initial data gathering phase
   - Wait for at least 6 complete cycles
   - Convergence confidence building toward threshold
2. **stable** - System has converged
   - Confidence ≥ heating-type threshold (60-80%)
   - PID gains are reliable
3. **optimized** - Very high confidence
   - Confidence ≥ 95%
   - System is well-tuned

Check `pid_history` to see adjustments made by learning system.

### Cycle Interruption Tracking

Check `interruption_history` attribute (when available) to diagnose why learning cycles are being invalidated:
- **Setpoint changes:** ΔT >0.5°C when heater off
- **Mode changes:** Incompatible mode transitions (heat→off, cool→heat)
- **Contact sensors:** Window/door open >5 min
- **Timeouts:** Settling phase exceeds 120 min

### Learning Window Adjustment

If learning is too sensitive or too slow:
- **Too sensitive:** Increase `number.adaptive_climate_learning_window` (e.g., 14 days)
- **Too slow:** Decrease to 3-5 days for faster adaptation

---

[← Back to Home](https://github.com/afewyards/ha-adaptive-climate/wiki/Home) | [Services →](https://github.com/afewyards/ha-adaptive-climate/wiki/Services)
