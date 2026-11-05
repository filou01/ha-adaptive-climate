# Configuration Reference

<!-- pump-aware-fork-preview:start -->
## Optional pump-aware PWM configuration in the fork preview

**Fork preview, not an upstream release feature.** The following information applies to `filou01/ha-adaptive-climate`, branch `codex/pump-aware-pwm`, [preview v0.67.1-pwm.8](https://github.com/filou01/ha-adaptive-climate/releases/tag/v0.67.1-pwm.8). Do not assume the upstream release supports this configuration.

This is a separate opt-in domain-level block under the existing
`adaptive_climate:` mapping. It is not a thermal group, manifold, pump-flow
controller or replacement for per-zone PWM. Merge it into the existing mapping
rather than duplicate the top-level key. Use actual restored entity IDs.

| Key | Default / supported values |
| --- | --- |
| `pwm_coordination.enabled` | `false`; explicit Boolean |
| `pwm_coordination.mode` | `load_balancing` only |
| `groups[].name` | Unique nonempty physical pump-group name |
| `overlap_strategy` | `minimal` or `maximal`; default `minimal` |
| `handover_overlap_seconds` | 240; finite 0–1800 seconds |
| `max_deferral_seconds` | 3600; finite 0–7200 seconds; ordinary pulses only |
| `zones[].entity` | Explicit climate entity; 2–16 unique members per group |
| `zones[].hydraulic_weight` | 1; finite and strictly positive; a preference, not measured flow |

Supported groups use the same positive period, HEAT-only PWM and one
non-inverted `switch.*` or `input_boolean.*` output per zone. Cooling/AC,
analog outputs, inverted/multiple outputs, duplicate physical outputs and
incompatible periods/minimum times are not coordinated. Unknown options and
duplicate membership are rejected. No obsolete `loops` option is introduced.

The [current fork guide](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pump-aware-pwm.md#english) contains the complete illustrative YAML,
runtime compatibility checks, supervised activation and rollback. Do not paste
the preview block into an upstream installation that does not support it.
<!-- pump-aware-fork-preview:end -->

Complete reference for all configuration parameters and examples.

## Configuration Levels

Configuration parameters can be set at two levels:

- **Domain Level** (`adaptive_climate:`): System-wide settings shared across all zones
- **Entity Level** (`climate:` platform): Per-zone settings for individual thermostats

Some parameters can be set at both levels - domain provides the default, entity override is optional.

### Domain-Level Only Parameters

These parameters can **only** be configured under `adaptive_climate:`:

- System: `house_energy_rating`, `learning_window_days`, `chronic_approach_historic_scan`, `debug`, `notify_service`, `persistent_notification`
- Weather: `weather_entity`, `outdoor_sensor`, `wind_speed_sensor`
- Central Control: `main_heater_switch`, `main_cooler_switch`, `source_startup_delay`, `sync_modes`
- Multi-Zone: `thermal_groups`, `manifolds`, `auto_mode_switching`
- Monitoring: `supply_temp_sensor`, `return_temp_sensor`, `flow_rate_sensor`, `volume_meter_entity`, `fallback_flow_rate`, `energy_meter_entity`, `energy_cost_entity`, `supply_temperature`
- Presets: `away_temp`, `eco_temp`, `boost_temp`, `comfort_temp`, `home_temp`, `activity_temp`, `preset_sync_mode`, `boost_pid_off`

### Entity-Level Only Parameters

These parameters can **only** be configured per climate entity:

- Core: `name`, `unique_id`, `heater`, `cooler`, `demand_switch`, `invert_heater`, `target_sensor`, `area`, `initial_hvac_mode`
- Adaptive: `heating_type`, `area_m2`, `ceiling_height`, `max_power_w`, `derivative_filter_alpha`, `auto_apply_pid`
- Windows: `window_area_m2`, `window_orientation`
- Floor: `floor_construction`, `loops`
- Safety: `force_off_state`, `sensor_stall`, `output_safety`
- Contact: `contact_sensors`, `contact_action`, `contact_delay`
- Humidity: `humidity_sensor`, `humidity_spike_threshold`, `humidity_absolute_max`, `humidity_detection_window`, `humidity_stabilization_delay`, `humidity_exit_threshold`, `humidity_exit_drop`
- Setpoint Boost: `setpoint_boost`, `setpoint_boost_factor`, `setpoint_debounce`
- Night Setback: `night_setback` (entire block)
- Actuator Wear: `heater_rated_cycles`, `cooler_rated_cycles`
- Timing: `min_cycle_duration_pid_off`, `min_off_cycle_duration_pid_off`, `control_interval`, `sampling_period`, `valve_actuation_time`
- Output: `output_precision`, `output_min`, `output_max`, `output_clamp_low`, `output_clamp_high`

### Dual-Level Parameters (Domain Default + Entity Override)

These can be set at domain level as defaults and optionally overridden per entity:

- Temperature: `min_temp`, `max_temp`, `target_temp`, `hot_tolerance`, `cold_tolerance`, `precision`, `target_temp_step`
- Timing: `pwm`, `min_cycle_duration`, `min_off_cycle_duration`
- Windows: `window_rating`

## Table of Contents

- [Core Parameters](#core-parameters)
- [Timing & Cycle Parameters](#timing--cycle-parameters)
- [Temperature Tolerance Parameters](#temperature-tolerance-parameters)
- [Output Control Parameters](#output-control-parameters)
- [Safety Parameters](#safety-parameters)
- [Adaptive Learning Parameters](#adaptive-learning-parameters)
- [Floor Construction Parameters](#floor-construction-parameters)
- [Valve Actuation Time Parameters](#valve-actuation-time-parameters)
- [Manifold Transport Delay Parameters](#manifold-transport-delay-parameters)
- [Actuator Wear Parameters](#actuator-wear-parameters)
- [Preset Mode Parameters](#preset-mode-parameters)
- [Night Setback Parameters](#night-setback-parameters)
- [Thermal Coupling Parameters](#thermal-coupling-parameters)
- [Contact Sensor Parameters](#contact-sensor-parameters)
- [Humidity Detection Parameters](#humidity-detection-parameters)
- [Setpoint Boost Parameters](#setpoint-boost-parameters)
- [Auto Mode Switching Parameters](#auto-mode-switching-parameters)
- [System Configuration Parameters](#system-configuration-parameters)
- [Configuration Examples](#configuration-examples)

## Core Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `name` | No | Adaptive Climate | Thermostat name |
| `unique_id` | No | none | Unique ID for entity registry |
| `heater` | No* | - | Switch/valve entity (or list) for heating mode |
| `cooler` | No | - | Switch/valve entity (or list) for cooling mode |
| `demand_switch` | No* | - | Switch/valve entity (or list) controlled in both modes |
| `invert_heater` | No | false | Invert heater on/off polarity |
| `target_sensor` | Yes | - | Temperature sensor entity |
| `area` | No | - | Home Assistant area ID to assign entity to |
| `min_temp` | No | 7.0 | Minimum setpoint temperature (or domain default) |
| `max_temp` | No | 35.0 | Maximum setpoint temperature (or domain default) |
| `target_temp` | No | 20.0 | Initial target temperature (or domain default) |
| `initial_hvac_mode` | No | - | Initial HVAC mode (HEAT, COOL, OFF) |

\* At least one of `heater`, `cooler`, or `demand_switch` is required.

**Note:** Cooling mode (COOL) is automatically enabled when `cooler` is configured at zone level or `main_cooler_switch` is configured at controller level.

## Timing & Cycle Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `control_interval` | No | Auto | Control loop interval (auto-derived from `sampling_period` or 60s default) |
| `pwm` | No | 00:15:00 | PWM period (set to 00:00:00 for valve mode) (or domain default) |
| `min_cycle_duration` | No | 00:00:00 | Minimum heater on-time (or domain default) |
| `min_off_cycle_duration` | No | 00:00:00 | Minimum heater off-time (or domain default) |
| `min_cycle_duration_pid_off` | No | - | Min on-time when PID disabled (boost mode) |
| `min_off_cycle_duration_pid_off` | No | - | Min off-time when PID disabled (boost mode) |
| `sampling_period` | No | 00:00:00 | PID calculation interval (00:00:00 = on sensor change) |
| `valve_actuation_time` | No | per type | Motorized valve travel time in seconds (see [Valve Actuation Time](#valve-actuation-time-parameters)) |

## Temperature Tolerance Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `hot_tolerance` | 0.3 | Tolerance above setpoint before cooling (°C) (or domain default) |
| `cold_tolerance` | 0.3 | Tolerance below setpoint before heating (°C) (or domain default) |
| `precision` | 0.1 | Display precision (0.1, 0.5, 1.0) (or domain default) |
| `target_temp_step` | 0.5 | Setpoint adjustment step size (0.1, 0.5, 1.0) (or domain default) |

## Output Control Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `output_min` | 0 | Minimum PID output value |
| `output_max` | 100 | Maximum PID output value |
| `out_clamp_low` | 0 | Lower output clamp limit |
| `out_clamp_high` | 100 | Upper output clamp limit |
| `output_precision` | 1 | Decimal places for output value |

## Safety Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `sensor_stall` | 06:00:00 | Timeout before declaring sensor stalled |
| `output_safety` | 5.0 | Safety output when sensor stalls (%) |
| `force_off_state` | true | Force heater off when HVAC mode is OFF |

## Adaptive Learning Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `heating_type` | - | System type: floor_hydronic, radiator, convector, forced_air |
| `area_m2` | - | Zone floor area in m² |
| `ceiling_height` | 2.5 | Ceiling height in meters |
| `max_power_w` | - | Total heater power in watts (for process gain scaling) |
| `window_area_m2` | - | Total window area in m² |
| `window_orientation` | - | Primary window direction (north, northeast, east, southeast, south, southwest, west, northwest, roof) |
| `window_rating` | hr++ | Window insulation rating (overrides domain default) |
| `auto_apply_pid` | true | Enable automatic PID tuning application |
| `derivative_filter_alpha` | auto | Derivative filter strength (0.0-1.0, auto-derived from heating_type) |

## Floor Construction Parameters

For `floor_hydronic` systems only. Specifies floor construction to calculate accurate thermal time constant for physics-based PID initialization.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pipe_spacing_mm` | int | No | 150 | Pipe spacing: 100, 150, 200, or 300 mm |
| `layers` | list | Yes | - | List of floor layers (top to bottom) |

### Layer Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `type` | string | Yes | `top_floor` or `screed` |
| `material` | string | Yes | Material name from library |
| `thickness_mm` | int | Yes | Layer thickness in mm |

### Top Floor Materials

| Material | Conductivity W/(m·K) | Density kg/m³ | Specific Heat J/(kg·K) |
|----------|---------------------|---------------|------------------------|
| `ceramic_tile` | 1.3 | 2300 | 840 |
| `porcelain` | 1.5 | 2400 | 880 |
| `natural_stone` | 2.8 | 2700 | 900 |
| `terrazzo` | 1.8 | 2200 | 850 |
| `polished_concrete` | 1.4 | 2100 | 880 |
| `hardwood` | 0.15 | 700 | 1600 |
| `engineered_wood` | 0.13 | 650 | 1600 |
| `laminate` | 0.17 | 800 | 1500 |
| `vinyl` | 0.19 | 1200 | 1400 |
| `carpet` | 0.06 | 200 | 1300 |
| `cork` | 0.04 | 200 | 1800 |

### Screed Materials

| Material | Conductivity W/(m·K) | Density kg/m³ | Specific Heat J/(kg·K) |
|----------|---------------------|---------------|------------------------|
| `cement` | 1.4 | 2100 | 840 |
| `anhydrite` | 1.2 | 2000 | 1000 |
| `lightweight` | 0.47 | 1000 | 1000 |
| `mastic_asphalt` | 0.7 | 2100 | 920 |
| `synthetic` | 0.3 | 1200 | 1200 |
| `self_leveling` | 1.3 | 1900 | 900 |
| `dry_screed` | 0.2 | 800 | 1000 |

### Pipe Spacing Efficiency

| Spacing (mm) | Efficiency | Notes |
|--------------|-----------|-------|
| 100 | 0.92 | Tight spacing - best heat distribution |
| 150 | 0.87 | Standard spacing (default) |
| 200 | 0.80 | Wide spacing - moderate efficiency |
| 300 | 0.68 | Very wide spacing - reduced efficiency |

### Validation Rules

1. **Layer Order:** Top floor layers must precede screed layers
2. **Thickness Ranges:**
   - Top floor: 5-25 mm
   - Screed: 30-80 mm
3. **Material Types:** Must exist in the material libraries above
4. **Pipe Spacing:** One of 100, 150, 200, 300 mm (defaults to 150 if not specified)

### Custom Materials

Override thermal properties for unlisted materials:

```yaml
floor_construction:
  layers:
    - type: screed
      material: custom_mix
      thickness_mm: 60
      conductivity: 1.1    # W/(m·K)
      density: 1850        # kg/m³
      specific_heat: 950   # J/(kg·K)
```

When custom properties are provided, they override any library values for that material name.

### Example Configuration

```yaml
climate:
  - platform: adaptive_climate
    name: Living Room UFH
    heater: switch.ufh_living
    target_sensor: sensor.temp_living
    heating_type: floor_hydronic
    area_m2: 32
    floor_construction:
      pipe_spacing_mm: 100
      layers:
        - type: top_floor
          material: hardwood
          thickness_mm: 16
        - type: screed
          material: anhydrite
          thickness_mm: 70
```

See [PID Control - Floor Construction Impact](https://github.com/afewyards/ha-adaptive-climate/wiki/PID-Control#floor-construction-impact-on-pid) for details on how this affects PID tuning.

## Valve Actuation Time Parameters

Configurable delay for motorized valve travel time. Accounts for the time required for zone valves to fully open or close, which affects PWM timing compensation and cycle tracking.

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `valve_actuation_time` | No | per heating type | Time in seconds for valve to fully open/close |

### Default Values by Heating Type

| Heating Type | Default (seconds) | Rationale |
|--------------|-------------------|-----------|
| `floor_hydronic` | 120 | Slow thermal mass, typically uses thermostatic actuators |
| `radiator` | 90 | Standard thermostatic radiator valves |
| `convector` | 0 | Direct control, no motorized valve |
| `forced_air` | 30 | Fast damper actuators |

### Timing Behavior

The valve actuation time affects several aspects of system operation:

1. **Demand Signaling**: Zone demand is signaled to the central controller only after the valve fully opens, not when the open command is sent. This prevents the main heater from firing before heat can actually flow.

2. **Demand Removal**: Demand is removed when the valve is approximately half-closed, accounting for in-flight heat still in the pipes.

3. **PWM Duty Adjustment**: On-time is extended by half the valve actuation time to compensate for closing delay, ensuring the requested heat delivery is achieved.

4. **Committed Heat Tracking**: For systems with manifold transport delay, tracks heat in-flight through pipes and subtracts from the next cycle's duty calculation.

5. **Overshoot Attribution**: Learning system splits overshoot into "controllable" (PID could have prevented) vs "committed" (unavoidable due to in-flight heat), preventing over-aggressive tuning adjustments.

### Example Configuration

```yaml
climate:
  - platform: adaptive_climate
    name: Living Room UFH
    heater: switch.ufh_living
    target_sensor: sensor.temp_living
    heating_type: floor_hydronic
    area_m2: 32
    valve_actuation_time: 150  # Override default 120s for slower actuator
```

### When to Configure

- **Use default**: Most installations work well with heating-type defaults
- **Increase**: If you observe demand spikes before valves are ready, or use slow thermal actuators
- **Decrease**: For fast electronic actuators or direct-control systems
- **Set to 0**: For systems without motorized valves (e.g., direct pump control)

## Manifold Transport Delay Parameters

For hydronic systems with significant pipe runs between heat source and zone manifolds. Accounts for transport delay (dead time) that varies by number of active zones.

### Domain-Level Parameters

Configured under `adaptive_climate:` in the manifolds list:

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `name` | Yes | - | Unique manifold identifier |
| `zones` | Yes | - | List of zone entity IDs served by this manifold |
| `pipe_volume` | Yes | - | Total pipe volume from heat source to manifold (liters) |
| `flow_per_loop` | No | 2.0 | Flow rate per heating loop (L/min) |

### Zone-Level Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `loops` | No | 1 | Number of heating loops in this zone (1-10) |

### Delay Calculation

```
transport_delay = pipe_volume / (active_loops × flow_per_loop)
```

- **active_loops**: Sum of loops from all zones currently heating on the manifold
- **Warm manifold**: If manifold was active within 5 minutes, delay = 0 (pipes already warm)

**Example:** 20L pipe volume, bathroom (2 loops) + bedroom (3 loops) active:
- Total flow = 5 loops × 2 L/min = 10 L/min
- Delay = 20L / 10 L/min = 2 minutes

### Configuration Example

```yaml
adaptive_climate:
  manifolds:
    - name: "2nd Floor"
      zones:
        - climate.bathroom_2nd
        - climate.bedroom_2nd
      pipe_volume: 20
      flow_per_loop: 2

climate:
  - platform: adaptive_climate
    name: "2nd Bathroom"
    heater: switch.ufh_bathroom_2nd
    target_sensor: sensor.temp_bathroom_2nd
    heating_type: floor_hydronic
    loops: 2  # Two floor heating loops

  - platform: adaptive_climate
    name: "2nd Bedroom"
    heater: switch.ufh_bedroom_2nd
    target_sensor: sensor.temp_bedroom_2nd
    heating_type: floor_hydronic
    loops: 3  # Three floor heating loops
```

### State Attributes

When manifold is configured, zone entities expose:
- `transport_delay`: Current transport delay in minutes (None when not heating)

## Actuator Wear Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `heater_rated_cycles` | - | Expected heater lifetime cycles (e.g., 100000 for contactors) |
| `cooler_rated_cycles` | - | Expected cooler lifetime cycles (e.g., 50000 for valves) |

## Preset Mode Parameters

These are configured at the controller level under `adaptive_climate:` (shared across all zones).

| Parameter | Default | Description |
|-----------|---------|-------------|
| `away_temp` | - | Away mode temperature |
| `eco_temp` | - | Eco mode temperature |
| `boost_temp` | - | Boost mode temperature |
| `comfort_temp` | - | Comfort mode temperature |
| `home_temp` | - | Home mode temperature |
| `activity_temp` | - | Activity mode temperature |
| `preset_sync_mode` | none | Sync setpoint to preset ("sync" or "none") |
| `boost_pid_off` | false | Disable PID control in boost mode |

## Night Setback Parameters

Configure as a nested block under `night_setback`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `start` | - | Start time ("22:00" or "sunset+30") |
| `end` | dynamic | End time ("06:30") - if omitted, calculated from sunrise/orientation/weather |
| `delta` | 2.0 | Temperature reduction at night (°C) |
| `recovery_deadline` | - | Override end time if earlier than dynamic calculation ("08:00") |
| `min_effective_elevation` | 10.0 | Minimum sun elevation (degrees) for effective solar gain through windows |
| `preheat_enabled` | false | Enable predictive pre-heating to reach target at recovery time |
| `max_preheat_hours` | per type | Maximum hours before recovery to start pre-heating (see table below) |

**Max Preheat Hours by Heating Type:**

| Heating Type | Default Max Preheat Hours |
|--------------|---------------------------|
| floor_hydronic | 8.0 |
| radiator | 4.0 |
| convector | 2.0 |
| forced_air | 1.5 |

## Thermal Groups Parameters

Configured at domain level under `adaptive_climate:`. Enables static multi-zone coordination with feedforward control for heat transfer between zones.

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `name` | Yes | - | Unique thermal group identifier |
| `zones` | Yes | - | List of zone entity IDs in this group |
| `type` | No | open_plan | Thermal group type (currently only 'open_plan') |
| `leader` | No | - | Leader zone entity ID (zone that receives feedforward) |
| `receives_from` | No | - | Source zone entity ID (zone providing heat transfer) |
| `transfer_factor` | No | 0.0 | Heat transfer coefficient (0.0-1.0) |
| `delay_minutes` | No | 0 | Thermal transfer delay in minutes |

### Example Configuration

```yaml
adaptive_climate:
  thermal_groups:
    - name: "Open Plan Ground Floor"
      zones:
        - climate.living_room
        - climate.kitchen
      type: open_plan
      leader: climate.living_room
      receives_from: climate.kitchen
      transfer_factor: 0.6
      delay_minutes: 5
```

**Note:** Transfer factor represents the fraction of heating output from the source zone that affects the leader zone. Higher values (0.6-0.8) indicate strong thermal coupling like open floor plans.

## Contact Sensor Parameters

Configured per-zone under `climate:`.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `contact_sensors` | - | List of window/door sensor entity IDs |
| `contact_action` | pause | Action when open: pause, frost_protection, none |
| `contact_delay` | 120 | Seconds before taking action |

## Humidity Detection Parameters

Configured per-zone under `climate:`. Detects shower steam in bathrooms and pauses heating during shower.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `humidity_sensor` | - | Humidity sensor entity ID |
| `humidity_spike_threshold` | 15 | Percentage rise to trigger detection |
| `humidity_absolute_max` | 80 | Absolute humidity percentage cap |
| `humidity_detection_window` | 300 | Seconds for rate calculation window |
| `humidity_stabilization_delay` | 300 | Seconds after drop before resuming |
| `humidity_exit_threshold` | 70 | Absolute humidity % to start exit |
| `humidity_exit_drop` | 5 | Percentage drop from peak to exit |

### Example Configuration

```yaml
climate:
  - platform: adaptive_climate
    name: Bathroom
    heater: switch.heating_bathroom
    target_sensor: sensor.temp_bathroom
    heating_type: radiator
    area_m2: 6
    humidity_sensor: sensor.bathroom_humidity
    humidity_spike_threshold: 15
    humidity_absolute_max: 80
    humidity_detection_window: 300
    humidity_stabilization_delay: 300
```

## Setpoint Boost Parameters

Configured per-zone under `climate:`. Accelerates PID response to setpoint changes via integral boost/decay.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `setpoint_boost` | true | Enable setpoint feedforward |
| `setpoint_boost_factor` | auto | Boost factor (auto-derived from heating_type) |
| `setpoint_debounce` | 5 | Debounce window in seconds |

**Heating Type Defaults:**

| Heating Type | boost_factor | decay_rate |
|--------------|--------------|------------|
| floor_hydronic | 25.0 | 0.15 |
| radiator | 18.0 | 0.20 |
| convector | 12.0 | 0.25 |
| forced_air | 8.0 | 0.30 |

### Example Configuration

```yaml
climate:
  - platform: adaptive_climate
    name: Living Room
    heater: switch.heating_living
    target_sensor: sensor.temp_living
    heating_type: floor_hydronic
    area_m2: 32
    setpoint_boost: true
    setpoint_boost_factor: 25.0  # Optional override
```

## Auto Mode Switching Parameters

Configured at domain level under `adaptive_climate:`. House-wide automatic HVAC mode switching based on outdoor temperature vs zone setpoints.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | - | Enable auto mode switching (required) |
| `threshold` | 2.0 | Temperature delta from median setpoint (°C) |
| `min_switch_interval` | 3600 | Minimum seconds between mode switches |
| `forecast_hours` | 6 | Lookahead hours for proactive switching |
| `season_thresholds.winter_below` | 12.0 | Forecast median below this = winter lock |
| `season_thresholds.summer_above` | 18.0 | Forecast median above this = summer lock |

### Example Configuration

```yaml
adaptive_climate:
  weather_entity: weather.home
  auto_mode_switching:
    enabled: true
    threshold: 2.0
    min_switch_interval: 3600
    forecast_hours: 6
    season_thresholds:
      winter_below: 12.0
      summer_above: 18.0
```

## System Configuration Parameters

These are configured under the `adaptive_climate:` domain block, not per-zone.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `house_energy_rating` | - | Building energy rating (A++++, A+++, A++, A+, A, B, C, D, E, F, G) for physics init |
| `learning_window_days` | 7 | Days of data for adaptive learning (1-30) |
| `chronic_approach_historic_scan` | false | Enable scan of existing cycles on startup for chronic approach detection |
| `weather_entity` | - | Weather entity for solar gain prediction and wind speed fallback |
| `outdoor_sensor` | - | Outdoor temperature sensor for Ke (shared by all zones) |
| `wind_speed_sensor` | - | Dedicated wind speed sensor (m/s); if not set, uses `weather_entity`'s wind_speed attribute |
| `main_heater_switch` | - | Main heater switch(es) - single entity or list |
| `main_cooler_switch` | - | Main cooler switch(es) - single entity or list |
| `source_startup_delay` | 30 | Seconds to wait before activating heat source (0-300) |
| `sync_modes` | true | Synchronize HEAT/COOL modes across zones |
| `notify_service` | - | Notification service for alerts/reports (e.g., 'mobile_app_phone' or 'notify.mobile_app_phone') |
| `persistent_notification` | true | Enable persistent notifications in Home Assistant |
| `debug` | false | Expose additional PID debug attributes on entities |
| `energy_meter_entity` | - | Energy meter sensor for cost tracking |
| `energy_cost_entity` | - | Energy price input for cost calculation |
| `supply_temperature` | - | Supply water temperature for physics-based PID scaling (25-80°C) |
| `supply_temp_sensor` | - | Supply water temperature sensor |
| `return_temp_sensor` | - | Return water temperature sensor |
| `flow_rate_sensor` | - | Flow rate sensor (L/min) |
| `volume_meter_entity` | - | Volume meter for flow rate calculation |
| `fallback_flow_rate` | 0.5 | Fallback flow rate (L/min) when meter unavailable (0.01-10.0) |
| `window_rating` | hr++ | Default window insulation rating for all zones |
| `min_temp` | 7.0 | Default minimum setpoint temperature (can be overridden per-zone) |
| `max_temp` | 35.0 | Default maximum setpoint temperature (can be overridden per-zone) |
| `target_temp` | 20.0 | Default initial target temperature (can be overridden per-zone) |
| `target_temp_step` | 0.5 | Default setpoint adjustment step (0.1, 0.5, 1.0) |
| `hot_tolerance` | 0.3 | Default tolerance above setpoint (°C) |
| `cold_tolerance` | 0.3 | Default tolerance below setpoint (°C) |
| `precision` | 0.1 | Default display precision (0.1, 0.5, 1.0) |
| `pwm` | 00:15:00 | Default PWM period (can be overridden per-zone) |
| `min_cycle_duration` | 00:00:00 | Default minimum heater on-time |
| `min_off_cycle_duration` | 00:00:00 | Default minimum heater off-time |

## Configuration Examples

### Basic Setup
```yaml
climate:
  - platform: adaptive_climate
    name: Living Room
    heater: switch.heating_living_room
    target_sensor: sensor.temp_living_room
    heating_type: radiator
    area_m2: 20
    min_temp: 7
    max_temp: 28
    target_temp: 20
```

### Multi-Zone with Coordination

**Prerequisites:** Assign climate entities to areas with floors in Home Assistant.

```yaml
adaptive_climate:
  house_energy_rating: A+++
  main_heater_switch: switch.boiler
  source_startup_delay: 30
  sync_modes: true
  outdoor_sensor: sensor.outdoor_temp

  # Thermal coupling - auto-discovers floors from HA registry
  thermal_coupling:
    open:
      - climate.ground_floor
      - climate.kitchen

climate:
  - platform: adaptive_climate
    name: Ground Floor
    heater: switch.heating_gf
    target_sensor: sensor.temp_gf
    heating_type: floor_hydronic
    area_m2: 28

  - platform: adaptive_climate
    name: Kitchen
    heater: switch.heating_kitchen
    target_sensor: sensor.temp_kitchen
    heating_type: radiator
    area_m2: 15
```

### Night Setback with Dynamic End Time
```yaml
climate:
  - platform: adaptive_climate
    name: Bedroom
    heater: switch.heating_bedroom
    target_sensor: sensor.temp_bedroom
    heating_type: radiator
    area_m2: 16
    window_orientation: south

    night_setback:
      start: "22:00"
      delta: 2.0
      recovery_deadline: "08:00"
      solar_recovery: true
      min_effective_elevation: 10
```

### Cooling/AC Configuration
```yaml
climate:
  - platform: adaptive_climate
    name: Living Room AC
    heater: switch.heating_living
    cooler: switch.ac_living
    target_sensor: sensor.temp_living
    heating_type: forced_air
    area_m2: 25
    min_temp: 16
    max_temp: 30
    target_temp: 22
    hot_tolerance: 0.5
    cold_tolerance: 0.5
```

### Valve Control (Fan Coil Unit)
```yaml
climate:
  - platform: adaptive_climate
    name: Fan Coil Unit
    demand_switch: switch.fcunit_valve
    target_sensor: sensor.temp_fcunit
    pwm: 0  # Direct valve control (0-100%)
    heating_type: forced_air
    area_m2: 20
    min_temp: 16
    max_temp: 28
    target_temp: 21
```

### Actuator Wear Tracking
```yaml
climate:
  - platform: adaptive_climate
    name: Living Room
    heater: switch.heating_living
    target_sensor: sensor.temp_living
    heating_type: radiator
    area_m2: 20
    heater_rated_cycles: 100000  # Typical contactor
    cooler_rated_cycles: 50000   # Typical valve
```

### Advanced System Configuration
```yaml
adaptive_climate:
  house_energy_rating: A+++
  learning_window_days: 7
  chronic_approach_historic_scan: false

  # Weather and outdoor compensation
  weather_entity: weather.home
  outdoor_sensor: sensor.outdoor_temp
  wind_speed_sensor: sensor.wind_speed_mps

  # Heat output monitoring
  supply_temperature: 45.0  # Fixed supply temp for physics scaling
  supply_temp_sensor: sensor.heating_supply
  return_temp_sensor: sensor.heating_return
  flow_rate_sensor: sensor.heating_flow
  volume_meter_entity: sensor.heating_volume_m3
  fallback_flow_rate: 0.5

  # Energy tracking
  energy_meter_entity: sensor.heating_energy
  energy_cost_entity: input_number.energy_price

  # Central heat source
  main_heater_switch:
    - switch.boiler
    - switch.circulation_pump
  main_cooler_switch: switch.ac_compressor
  source_startup_delay: 30

  # Mode synchronization
  sync_modes: true

  # Auto mode switching
  auto_mode_switching:
    enabled: true
    threshold: 2.0
    min_switch_interval: 3600
    forecast_hours: 6
    season_thresholds:
      winter_below: 12.0
      summer_above: 18.0

  # Preset temperatures
  away_temp: 14
  eco_temp: 18
  boost_temp: 23
  comfort_temp: 21
  home_temp: 20
  activity_temp: 20
  preset_sync_mode: none
  boost_pid_off: false

  # Default window rating
  window_rating: hr++

  # Domain-level climate defaults
  min_temp: 7.0
  max_temp: 35.0
  target_temp: 20.0
  target_temp_step: 0.5
  hot_tolerance: 0.3
  cold_tolerance: 0.3
  precision: 0.1
  pwm: 00:15:00
  min_cycle_duration: 00:00:00
  min_off_cycle_duration: 00:00:00

  # Notifications
  notify_service: mobile_app_phone
  persistent_notification: true

  # Debug mode
  debug: false
```

### Contact Sensors (Pause Heating)
```yaml
climate:
  - platform: adaptive_climate
    name: Bedroom
    heater: switch.heating_bedroom
    target_sensor: sensor.temp_bedroom
    heating_type: radiator
    area_m2: 16
    contact_sensors:
      - binary_sensor.bedroom_window
      - binary_sensor.bedroom_door
    contact_action: pause  # pause, frost_protection, none
    contact_delay: 120
```

### Bathroom with Humidity Detection
```yaml
climate:
  - platform: adaptive_climate
    name: Bathroom
    heater: switch.heating_bathroom
    target_sensor: sensor.temp_bathroom
    heating_type: radiator
    area_m2: 6

    # Humidity-based steam detection
    humidity_sensor: sensor.bathroom_humidity
    humidity_spike_threshold: 15
    humidity_absolute_max: 80
    humidity_detection_window: 300
    humidity_stabilization_delay: 300
    humidity_exit_threshold: 70
    humidity_exit_drop: 5

    # Window sensor backup
    contact_sensors:
      - binary_sensor.bathroom_window
    contact_action: pause
    contact_delay: 120
```

### Complete Multi-Feature Zone
```yaml
climate:
  - platform: adaptive_climate
    name: Living Room
    unique_id: living_room_thermostat
    heater: switch.heating_living
    target_sensor: sensor.temp_living
    area: living_room  # Home Assistant area assignment

    # Heating system
    heating_type: floor_hydronic
    area_m2: 32
    ceiling_height: 2.5
    max_power_w: 1500
    loops: 3  # For manifold transport delay

    # Physics and learning
    auto_apply_pid: true

    # Windows and solar
    window_area_m2: 6
    window_orientation: south

    # Floor construction
    floor_construction:
      pipe_spacing_mm: 150
      layers:
        - type: top_floor
          material: hardwood
          thickness_mm: 16
        - type: screed
          material: anhydrite
          thickness_mm: 70

    # Night setback with preheat
    night_setback:
      start: "22:00"
      delta: 2.0
      recovery_deadline: "07:00"
      preheat_enabled: true
      max_preheat_hours: 8.0

    # Setpoint boost
    setpoint_boost: true
    setpoint_boost_factor: 25.0

    # Contact sensors
    contact_sensors:
      - binary_sensor.living_door
      - binary_sensor.living_window
    contact_action: pause
    contact_delay: 120

    # Temperature settings
    min_temp: 16
    max_temp: 28
    target_temp: 21
    hot_tolerance: 0.5
    cold_tolerance: 0.5

    # Actuator wear tracking
    heater_rated_cycles: 100000
```

## Configuration Validation Tips

1. **Check YAML syntax** - Use Home Assistant's built-in configuration checker
2. **Verify entity IDs** - All referenced entities must exist before starting
3. **Required parameters** - Ensure at least `target_sensor` and one actuator (`heater`, `cooler`, or `demand_switch`) are configured
4. **Heating type** - Match to your actual system for optimal PID initialization and PWM timing
5. **Area calculation** - Measure room dimensions carefully (length × width in m²)
6. **Window orientation** - Use primary window direction, or omit if no dominant direction
7. **Domain vs Entity config** - Some parameters can be set at domain level as defaults and overridden per entity
8. **PWM compatibility** - Never use PWM mode (`pwm > 0`) with climate entities (causes nested control loops)
9. **Humidity sensors** - Only configure for bathrooms or zones where steam detection is needed
10. **Auto mode switching** - Requires `weather_entity` to be configured

## Common Configuration Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Wrong `heating_type` | Oscillations or sluggish response | Set to actual system type (floor_hydronic, radiator, convector, forced_air) |
| Incorrect `area_m2` | Never reaches setpoint or overshoots | Verify room dimensions - measure length × width |
| Missing `outdoor_sensor` | No Ke (outdoor compensation) learning | Add sensor at domain level under `adaptive_climate:` |
| `pwm: 0` with switches | No on/off cycling, always on | Set pwm to appropriate period (00:05:00 to 00:15:00) or use 00:00:00 for valve mode |
| `pwm > 0` with climate entities | Nested PID loops, erratic behavior | Set `pwm: 00:00:00` for valve mode when controlling climate entities |
| Multiple `heater` entries without list syntax | Syntax error on startup | Use YAML list format with `-` prefix |
| `humidity_sensor` on non-bathroom zones | Unwanted heating pauses | Only use in zones with shower/bath steam |
| `auto_mode_switching` without `weather_entity` | Mode switching fails silently | Add `weather_entity` to domain config |
| `chronic_approach_historic_scan: true` permanently | Slow startup on every restart | Set to `false` after initial scan completes |
| Floor construction on non-floor_hydronic | Ignored, no effect | Only configure for `heating_type: floor_hydronic` |
| Invalid `supply_temperature` range | Config validation error | Must be 25-80°C |
| `notify_service` with wrong format | Notifications fail | Use 'service_name' or 'notify.service_name' format |

---

[← Back to Home](https://github.com/afewyards/ha-adaptive-climate/wiki/Home) | [PID Control →](https://github.com/afewyards/ha-adaptive-climate/wiki/PID-Control)
