# Installation & Setup

<!-- pump-aware-fork-preview:start -->
## Optional fork preview installation

**Fork preview, not an upstream release feature.** The following information applies to `filou01/ha-adaptive-climate`, branch `codex/pump-aware-pwm`, [preview v0.67.1-pwm.8](https://github.com/filou01/ha-adaptive-climate/releases/tag/v0.67.1-pwm.8). Do not assume the upstream release supports this configuration.

The pump-aware preview is not obtained by installing the upstream default
branch. Use the explicitly tagged prerelease of the personal fork, preserving
backups of integration files, YAML and learning storage. Keep the domain
`adaptive_climate`; never install two copies of that domain. The fork's `main`
is the upstream baseline, while preview development uses `codex/pump-aware-pwm`.

Before a supervised upgrade, turn participating thermostats OFF and verify
their helper/switch outputs and downstream relays OFF. Install the selected
fork prerelease in HACS, restart HA and resume HEAT. The first journal-free
upgrade cannot reconstruct earlier delivery; observe existing minimum-OFF
protection. Existing journal-aware upgrades retain compatible stored budgets.
Do not delete learning data, rename working helpers or run old standalone
patch scripts. Follow the [fork guide](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pump-aware-pwm.md#english) for activation and rollback.
<!-- pump-aware-fork-preview:end -->

Complete guide to installing and configuring Adaptive Climate (v0.47.0) for the first time.

## Prerequisites

- Home Assistant 2023.1 or newer
- At least one temperature sensor entity
- At least one heating/cooling switch or valve entity
- HACS (recommended for installation)

## Installation Methods

### Install using HACS (Recommended)

1. Open Home Assistant
2. Navigate to **HACS** → **Integrations**
3. Click the **three dots menu** (⋮) in the top right
4. Select **Custom repositories**
5. Add the repository:
   - **URL**: `https://github.com/afewyards/ha-adaptive-climate`
   - **Category**: Integration
6. Click **Add**
7. Search for **Adaptive Climate** in HACS
8. Click **Install** on the card
9. **Restart Home Assistant**

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/afewyards/ha-adaptive-climate/releases)
2. Extract the `adaptive_climate` folder from the archive
3. Copy the folder to your Home Assistant `config/custom_components/` directory
   - Full path: `<config>/custom_components/adaptive_climate/`
4. **Restart Home Assistant**

### Verify Installation

After restarting, verify the integration is loaded:

1. Navigate to **Settings** → **System** → **Logs**
2. Search for "adaptive_climate"
3. You should see initialization messages with no errors

## Quick Start

### Basic Configuration

Add this to your `configuration.yaml`:

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

### Restart and Test

1. **Restart Home Assistant** to load the configuration
2. Navigate to **Settings** → **Devices & Services** → **Integrations**
3. Look for the new climate entity: `climate.living_room`
4. Test basic operation:
   - Set a target temperature
   - Verify the heater switch responds
   - Monitor temperature sensor readings

## Initial Configuration Checklist

### Required Parameters
- ✅ `name` - Friendly name for the thermostat
- ✅ `heater` or `cooler` or `demand_switch` - At least one actuator
- ✅ `target_sensor` - Temperature sensor entity ID
- ✅ `heating_type` - System type (floor_hydronic, radiator, convector, forced_air)
- ✅ `area_m2` - Zone floor area in square meters

### Recommended Parameters
- `min_temp` / `max_temp` - Setpoint limits (default: 7°C - 35°C)
- `target_temp` - Initial temperature target (default: 20°C)
- `ceiling_height` - Room height in meters (default: 2.5m)
- `window_area_m2` - Total window area for thermal calculations
- `window_orientation` - Primary window direction for solar gain

### Optional System Configuration

Add under `adaptive_climate:` domain block for advanced features:

```yaml
adaptive_climate:
  house_energy_rating: A+++
  outdoor_sensor: sensor.outdoor_temp
  weather_entity: weather.home
  learning_window_days: 7
  main_heater_switch: switch.boiler  # Central heat source
  sync_modes: true  # Synchronize HVAC modes across zones
  auto_mode_switching:
    enabled: true
    threshold: 2.0
  chronic_approach_historic_scan: false  # Scan existing cycles on startup
```

## First-Time Tuning Recommendations

### Let the System Learn (Recommended)

1. **Install with basic configuration** (heating_type + area_m2)
2. **Set reasonable setpoints** (18-22°C)
3. **Wait 3-7 days** for adaptive learning to collect cycle data
4. **Apply learned parameters** using service:
   ```yaml
   service: adaptive_climate.apply_adaptive_pid
   target:
     entity_id: climate.living_room
   ```

### Physics-Based Initialization

The thermostat automatically calculates initial PID values from:
- **Heating type** - Determines base response characteristics (floor_hydronic, radiator, convector, forced_air)
- **Zone volume** - Calculated from `area_m2` × `ceiling_height`
- **Window area** - Thermal loss adjustment factor
- **House energy rating** - Insulation quality factor
- **Floor construction** - For floor_hydronic, optional detailed thermal mass calculation

No manual PID tuning is required. The system will start with sensible defaults and improve over time.

### Outdoor Compensation (Ke)

When `outdoor_sensor` is configured at the domain level:

1. **Ke (outdoor compensation)** initialized from physics at startup
2. PID learning runs first (6+ cycles, then 3 consecutive converged cycles)
3. Ke learning enabled **after** PID converges
4. Ke fine-tuned via correlation analysis (5+ observations over ≥5°C outdoor range)
5. No user action required - fully automatic

### Automatic PID Application

By default, `auto_apply_pid: true` enables automatic PID tuning:
- System learns from heating cycles and builds convergence confidence
- When confidence reaches heating-type threshold, new PID values are applied automatically
- 5-cycle validation window monitors performance
- Automatic rollback if performance degrades >30%
- Safety limits: 5 applies/season, 20 lifetime, 50% max drift from physics

Set `auto_apply_pid: false` to disable automatic application and use manual service calls instead.

## Verification Steps

### Check Entity Creation

Verify these entities were created (replace `living_room` with your zone name):

**Climate Entity:**
- `climate.living_room` - Main thermostat control

**Performance Sensors:**
- `sensor.living_room_duty_cycle` - Heating duty cycle (%)
- `sensor.living_room_power_m2` - Power per square meter (W/m²)
- `sensor.living_room_cycle_time` - Average cycle time (min)
- `sensor.living_room_heat_output` - Heat output in W (requires supply/return temp sensors)

**Learning Metrics:**
- `sensor.living_room_overshoot` - Temperature overshoot (°C)
- `sensor.living_room_settling_time` - Settling time (min)
- `sensor.living_room_oscillations` - Oscillation count

**Actuator Wear (hidden, optional):**
- `sensor.living_room_heater_wear` - Heater wear percentage
- `sensor.living_room_cooler_wear` - Cooler wear percentage

**System:**
- `number.adaptive_climate_learning_window` - Learning window control (days)

### Monitor Initial Operation

Watch the climate entity attributes for the first few heating cycles:

```yaml
# Example attributes to monitor
kp: 0.5
ki: 0.02
kd: 5.0
ke: 0.0  # Will be learned if outdoor_sensor configured
integral: 10.5
control_output: 45.2
learning_status: "collecting"  # collecting | stable | optimized
cycles_collected: 2
convergence_confidence_pct: 25
status:
  state: "heating"  # idle | heating | cooling | paused | preheating | settling
  conditions: []  # contact_open, humidity_spike, open_window, night_setback, learning_grace
```

### Common First-Run Issues

| Issue | Solution |
|-------|----------|
| Entity not created | Check `configuration.yaml` syntax, restart HA |
| Heater never turns on | Verify `heater` entity ID is correct and reachable |
| Temperature not updating | Check `target_sensor` entity ID and sensor availability |
| Control output always 0 | Verify target temperature is higher than current temperature |
| Learning status stuck at "collecting" | Normal for first 6+ cycles; check convergence_confidence_pct |
| PWM validation error | Ensure `pwm` period matches heating type requirements or set to 0 for valve control |

## Advanced Configuration Examples

### Bathroom with Humidity Detection

```yaml
climate:
  - platform: adaptive_climate
    name: Bathroom
    heater: switch.heating_bathroom
    target_sensor: sensor.temp_bathroom
    heating_type: radiator
    area_m2: 8
    humidity_sensor: sensor.bathroom_humidity
    humidity_spike_threshold: 15
    humidity_absolute_max: 80
```

Automatically pauses heating during showers and resumes after humidity stabilizes.

### Night Setback with Predictive Preheat

```yaml
climate:
  - platform: adaptive_climate
    name: Bedroom
    heater: switch.heating_bedroom
    target_sensor: sensor.temp_bedroom
    heating_type: radiator
    area_m2: 16
    night_setback:
      enabled: true
      start: "22:00"
      delta: 2.0
      recovery_deadline: "07:00"
      preheat_enabled: true
      max_preheat_hours: 3.0
```

Learns heating rate and starts early to reach target exactly at 07:00.

### Open Window Detection

```yaml
adaptive_climate:
  open_window_detection:
    temp_drop: 1.5
    detection_window: 10
    pause_duration: 30
    cooldown: 60
    action: pause

climate:
  - platform: adaptive_climate
    name: Living Room
    heater: switch.heating_living
    target_sensor: sensor.temp_living
    heating_type: radiator
    area_m2: 20
```

Detects rapid temperature drops and pauses heating automatically.

### Contact Sensors with Learning Grace

```yaml
climate:
  - platform: adaptive_climate
    name: Living Room
    heater: switch.heating_living
    target_sensor: sensor.temp_living
    heating_type: radiator
    area_m2: 20
    contact_sensors:
      - binary_sensor.door_living_room
      - binary_sensor.window_living_room
    contact_action: pause
    contact_delay: 120
    contact_learning_grace: 300
```

Pauses when door/window opens, with grace period for learning.

## Next Steps

Once basic operation is verified:

1. **Add advanced features** - See [Configuration Reference](https://github.com/afewyards/ha-adaptive-climate/wiki/Configuration-Reference)
2. **Enable multi-zone coordination** - See [Multi-Zone Coordination](https://github.com/afewyards/ha-adaptive-climate/wiki/Multi-Zone-Coordination)
3. **Configure night setback** - See [Energy Optimization](https://github.com/afewyards/ha-adaptive-climate/wiki/Energy-Optimization)
4. **Set up monitoring** - See [Sensors & Monitoring](https://github.com/afewyards/ha-adaptive-climate/wiki/Sensors-&-Monitoring)
5. **Install companion card** - [Adaptive Climate Card](https://github.com/afewyards/adaptive-climate-card)

---

[← Back to Home](https://github.com/afewyards/ha-adaptive-climate/wiki/Home) | [Configuration Reference →](https://github.com/afewyards/ha-adaptive-climate/wiki/Configuration-Reference)
