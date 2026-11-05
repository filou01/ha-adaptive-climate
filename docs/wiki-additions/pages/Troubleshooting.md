# Troubleshooting

<!-- pump-aware-fork-preview:start -->
## Fork preview: PWM handover and restart checklist

**Fork preview, not an upstream release feature.** The following information applies to `filou01/ha-adaptive-climate`, branch `codex/pump-aware-pwm`, [preview v0.67.1-pwm.8](https://github.com/filou01/ha-adaptive-climate/releases/tag/v0.67.1-pwm.8). Do not assume the upstream release supports this configuration.

1. Confirm the installed fork prerelease, active group ownership and intended
   strategy. New `runtime_*` fields identify the executable planning path.
2. Compare actual output edges, not only ideal cyclic projections. A configured
   handover is conditional on real demand, valid budget, start allowance,
   minimum times and successful output-state confirmation.
3. An idle zone with positive PID output is not necessarily owed another pulse:
   inspect signed credit, ordinary epoch quota and low-duty accumulation. A
   completed ordinary pulse must not restart on small PID fluctuations alone.
4. `restart_state_invalid` requires checking configuration identity, journal
   consistency and wall time. `restart_storage_error` blocks unjournaled ON.
   Preserve backups and investigate; do not delete the entire learning store
   or repeatedly restart to hide a fault.
5. A `Large dt discrepancy` warning compares control-call and sensor-update
   intervals; it alone proves neither a PID integration defect nor fallback.
   Missing contact entities at startup should be checked again once integrations
   are ready; an actually unavailable contact needs separate investigation.
6. Helper availability does not confirm a panel relay or flow. Inspect available
   downstream feedback and never add heat solely to improve a pump metric.

Startup-only success is not a completed heating/handover test. Follow the
[supervised installation test plan](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-runtime-handovers.md#english) and
[current validation limits](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/extension-validation.md#english). To return to independent scheduling,
disable coordination and restart; general learning/startup fixes remain active.
<!-- pump-aware-fork-preview:end -->

This guide helps diagnose and resolve common issues with the Adaptive Climate.

## Diagnostic Checklist

Follow this step-by-step process to diagnose problems:

### 1. Verify Basic Configuration

- **Check entity state**: Is the thermostat entity showing `unavailable` or `unknown`?
  - Open Developer Tools > States and search for your climate entity
  - If unavailable, check Home Assistant logs for errors during startup

- **Verify target sensor**: Is the temperature sensor reporting valid readings?
  - Check the sensor's state in Developer Tools > States
  - Ensure it's not `unavailable`, `unknown`, or stale (>30 min old)

- **Confirm heater/cooler entities**: Do the actuator entities exist and respond?
  - Try manually toggling the heater/cooler switch
  - Check for entity ID typos in configuration

### 2. Check Entity Attributes

Open Developer Tools > States, find your thermostat, and review key attributes:

**PID Parameters:**
- `pid_history`: List of PID gain changes with timestamp, reason, and actor
- Check the most recent entry for current gains (kp, ki, kd, ke)
- Note: kp, ki, kd, ke are no longer exposed as top-level attributes (moved to pid_history)

**Learning Status:**
- `learning_status`: Shows "collecting", "stable", or "optimized"
- `cycles_collected`: How many complete heating cycles recorded
- `convergence_confidence_pct`: Overall confidence in PID tuning (0-100%)

**Temperature Data:**
- `current_temperature`: Should match your sensor reading
- `temperature`: Current setpoint
- `outdoor_temperature`: If configured, should show current outdoor temp

**Performance Metrics:**
- `control_output`: Current PID output percentage (0-100%)
- `duty_accumulator_pct`: PWM accumulation as % of threshold
- Note: duty_cycle_pct, power_w_m2, and cycle_time_min have been moved to dedicated sensor entities

### 3. Review Logs

Enable debug logging to see detailed operation:

```yaml
logger:
  default: info
  logs:
    custom_components.adaptive_climate: debug
```

Look for:
- **Errors on startup**: Configuration validation issues
- **PID calculation warnings**: Invalid sensor values, NaN outputs
- **Cycle tracking messages**: State transitions (IDLE→HEATING→SETTLING)
- **Learning messages**: Cycle analysis, PID adjustments

## Let Adaptive Learning Do the Work

The thermostat learns from actual heating cycles and auto-tunes over time.

### How It Works

1. **Initial values**: Physics-based calculation using:
   - `heating_type` (floor_hydronic, radiator, convector, forced_air)
   - `area_m2` and `ceiling_height` (zone volume)
   - `window_area_m2` (heat loss)
   - `house_energy_rating` (thermal mass)

2. **Data collection**: Monitors temperature during heating cycles
   - Minimum 5 minutes heating time required
   - Tracks overshoot, settling time, oscillations
   - Detects response delays and undershoots

3. **Automatic adjustments**: After 6+ cycles and convergence:
   - Reduces Kp if overshooting
   - Increases Ki if undershooting or chronic approach failure
   - Increases Kd if oscillating or slow settling
   - Changes are applied automatically when `auto_apply_pid: true` (domain config)
   - All changes recorded in `pid_history` attribute with reason and timestamp

### Give It Time

- **First 24 hours**: May overshoot or undershoot as it learns
- **After 6 cycles**: Check `learning_status` attribute (should be "stable" or "optimized")
- **After 1 week**: Should stabilize with optimal tuning
- **Be patient**: Each heating type has different response times
  - Floor hydronic: 30-60 min per cycle
  - Radiators: 20-40 min per cycle
  - Forced air: 10-20 min per cycle

**Learning Status States:**
- `collecting`: Gathering data (< 6 cycles OR confidence below heating-type threshold)
- `stable`: System stable (confidence ≥ heating-type threshold AND < 95%)
- `optimized`: Very high confidence (confidence ≥ 95%)

## Outdoor Compensation (Ke)

When `outdoor_sensor` is configured, the thermostat uses physics-based Ke initialization and adjusts it through learning.

### Checking Status

**Entity Attributes:**
- `pid_history`: Check recent entries for Ke changes (reason: "ke_physics" or "ke_learning")
- `convergence_confidence_pct`: Overall system confidence (includes Ke tuning)
- Ke value is in the most recent pid_history entry

**How It Works:**
- Physics-based Ke calculated from house energy rating and zone characteristics
- Ke adjustments applied automatically when `auto_apply_pid: true` (domain config)
- All Ke changes recorded in pid_history with timestamps and reasons

### Troubleshooting Ke

If outdoor compensation seems wrong:

1. **Check pid_history**: Look for Ke-related entries
   ```yaml
   pid_history:
     - timestamp: "2026-01-30T10:30:00+00:00"
       ke: 0.5
       reason: "ke_physics"
       actor: "system"
   ```

2. **Verify outdoor sensor**: Ensure it's reading correctly
   - Should show real outdoor temperature, not indoor or garage
   - Verify sensor updates regularly (every 5-15 min)

3. **Check house_energy_rating**: Affects Ke calculation
   - Lower rating (F/G) → higher Ke (more outdoor compensation)
   - Higher rating (A/A+) → lower Ke (less outdoor compensation)

## Understanding the Status Attribute

The `status` attribute provides consolidated operational information.

**Format:**
```yaml
status:
  state: "heating"  # Current state
  conditions: ["night_setback"]  # List of active conditions
  resume_at: "2026-01-30T08:00:00+00:00"  # When pause ends (optional)
  setback_delta: 2.0  # °C adjustment (optional)
  setback_end: "2026-01-30T07:00:00+00:00"  # When night period ends (optional)
```

**States:**
- `idle`: Not actively heating/cooling
- `heating`: Actively heating
- `cooling`: Actively cooling
- `paused`: Paused due to contact sensor, open window, or humidity spike
- `preheating`: Night setback preheat active
- `settling`: Heater off, waiting for temperature to stabilize

**Conditions:**
- `contact_open`: Contact sensor (window/door) open
- `humidity_spike`: Shower steam detected
- `open_window`: Algorithmic open window detection
- `night_setback`: Night setback active
- `learning_grace`: Learning grace period (first few cycles)

**Debug-Only Fields** (when `debug: true`):
- `humidity_peak`: Peak humidity % during spike
- `open_sensors`: List of contact sensor entity IDs that triggered

---

## Auto Mode Switching (New in v0.44.0)

**Available:** When `auto_mode_switching` is enabled in domain config

**How It Works:**
- Automatically switches between HEAT/COOL based on outdoor temperature
- Uses weather forecast for proactive switching
- Season locking prevents unwanted mode changes (winter→HEAT only, summer→COOL only)

**Troubleshooting:**

1. **Not Switching Modes**
   - Check `weather_entity` is configured and working
   - Verify `auto_mode_switching.enabled: true` in domain config
   - Check outdoor temp vs median zone setpoint ± threshold

2. **Switching Too Often**
   - Increase `min_switch_interval` (default: 3600s = 1 hour)
   - Increase `threshold` (default: 2.0°C)

3. **Wrong Season Locking**
   - Check `season_thresholds.winter_below` (default: 12.0°C)
   - Check `season_thresholds.summer_above` (default: 18.0°C)
   - Review forecast temperatures

**Example Configuration:**
```yaml
adaptive_climate:
  weather_entity: weather.home
  auto_mode_switching:
    enabled: true
    threshold: 2.5  # °C delta from median setpoint
    min_switch_interval: 7200  # 2 hours between switches
    forecast_hours: 12  # Lookahead for proactive switching
```

---

## Common Issues

### Slow Response to Temperature Changes

**Symptoms:**
- Takes >60 minutes to reach setpoint
- Temperature rises/falls very slowly
- Heater runs continuously but temperature barely moves

**Possible Causes:**

1. **Setpoint boost disabled**
   - **New Feature**: Setpoint feedforward pre-loads integral term on setpoint increases
   - **Check**: Is `setpoint_boost: true` in configuration? (default: true)
   - **Effect**: Accelerates response to setpoint changes by 30-50%
   - **Configuration**:
     ```yaml
     climate:
       - platform: adaptive_climate
         setpoint_boost: true  # Enable (default)
         setpoint_boost_factor: 25.0  # Override default (optional)
     ```

2. **Incorrect heating_type**
   - **Check**: Is `heating_type` correct for your system?
   - **Fix**: Update configuration to match actual system:
     - Floor hydronic: Slowest, most conservative
     - Radiators: Medium response
     - Convectors: Faster response
     - Forced air: Fastest, most aggressive

2. **Kp too low**
   - **Check**: Look at `kp` attribute (should be >10)
   - **Fix**: Wait for adaptive learning to increase it, or manually adjust:
     ```yaml
     service: adaptive_climate.set_pid_gain
     data:
       kp: 25.0  # Increase by 20-30%
     target:
       entity_id: climate.living_room
     ```

3. **Undersized heater**
   - **Check**: Is `power_w_m2` very high (>25 W/m²)?
   - **Check**: Does heater run 100% duty cycle without reaching setpoint?
   - **Fix**: This is a physical limitation - PID tuning can't overcome insufficient heating capacity

4. **Inaccurate area_m2**
   - **Check**: Is configured area much larger than actual?
   - **Fix**: Recalculate zone area and update configuration
   - **Effect**: Oversized area → conservative PID → slow response

### Oscillations (Temperature Swings)

**Symptoms:**
- Temperature repeatedly overshoots and undershoots setpoint
- Cycles between too hot and too cold
- 3+ oscillations per hour

**Possible Causes:**

1. **Kp too high**
   - **Check**: Look at `kp` attribute
   - **Fix**: Adaptive learning will detect oscillations and reduce Kp automatically
   - **Manual fix**: Reduce Kp by 10-15%:
     ```yaml
     service: adaptive_climate.set_pid_gain
     data:
       kp: 18.0  # Reduce from previous value
     target:
       entity_id: climate.living_room
     ```

2. **Kd too low**
   - **Check**: Look at `kd` attribute (should be >0)
   - **Fix**: Increase derivative term to dampen oscillations:
     ```yaml
     service: adaptive_climate.set_pid_gain
     data:
       kd: 5.0  # Increase by 20-30%
     target:
       entity_id: climate.living_room
     ```

3. **PWM period too short**
   - **Check**: Look at `pwm` configuration
   - **Fix**: Increase PWM period to reduce cycling frequency:
     ```yaml
     # For floor hydronic
     pwm: "00:15:00"  # 15 minutes

     # For radiators
     pwm: "00:10:00"  # 10 minutes
     ```

4. **Thermal lag not accounted for**
   - **Symptom**: Temperature continues rising after heater turns off
   - **Fix**: Adaptive learning will increase Kd to predict overshoot
   - **Wait**: 3-5 cycles for learning to adapt

### Never Reaches Setpoint

**Symptoms:**
- Temperature stays 0.5-2°C below setpoint
- Heater runs continuously or very high duty cycle
- Eventually stabilizes below target

**Possible Causes:**

1. **Ki too low (integral windup prevention)**
   - **Check**: Look at `pid_history` for most recent Ki value (should be >1.0)
   - **Symptom**: Error accumulates but integral term doesn't compensate
   - **Note**: Chronic approach detector should automatically boost Ki if this persists
   - **Manual fix** (if needed):
     ```yaml
     service: adaptive_climate.set_pid_gain
     data:
       ki: 5.0  # Increase by 25-50%
     target:
       entity_id: climate.living_room
     ```

2. **Excessive heat loss**
   - **Check**: Is `power_w_m2` >20 W/m²?
   - **Check**: Are there drafts, poor insulation, or open windows?
   - **Fix**: Address physical issues (seal leaks, close windows)
   - **Workaround**: Increase setpoint to compensate

3. **Ke value incorrect (outdoor compensation)**
   - **Check**: Look at most recent Ke in `pid_history` (typical range: 0.3-0.6)
   - **Symptom**: Ke reduces output in cold weather, preventing full heating
   - **Fix**: Check house_energy_rating configuration (affects Ke calculation)
   - **Manual fix**: Adjust Ke if needed:
     ```yaml
     service: adaptive_climate.set_pid_gain
     data:
       ke: 0.4  # Adjust based on your system
     target:
       entity_id: climate.living_room
     ```

### Overshoots Then Settles

**Symptoms:**
- Temperature rises 0.5-2°C above setpoint
- Eventually settles back to target
- Most noticeable on first heating cycle of the day

**Diagnosis:**

This is **normal behavior initially** - the system is learning thermal characteristics.

**Expected Behavior:**
- **First 1-3 cycles**: May overshoot by 1-2°C
- **After 3-5 cycles**: Adaptive learning detects overshoot pattern
- **After applying adjustments**: Overshoot reduced to <0.3°C

**Check Learning Progress:**
```yaml
# Check pid_history attribute for recent adjustments
pid_history:
  - timestamp: "2026-01-30T10:30:00+00:00"
    kp: 15.0  # Reduced from previous value
    ki: 3.0
    kd: 2.5
    ke: 0.5
    reason: "auto_apply"  # Automatic adjustment
    actor: "learning"
```

**Manual Intervention (if needed):**

Only intervene if:
- Overshoot >2°C after 6+ cycles
- Overshoot is uncomfortable or wastes energy
- `auto_apply_pid: true` not set in domain config

```yaml
# Reduce Kp manually
service: adaptive_climate.set_pid_gain
data:
  kp: 15.0  # Reduce by 15-20% from current value
target:
  entity_id: climate.living_room
```

## Humidity-Based Steam Detection

**Available:** When `humidity_sensor` is configured (typically for bathrooms)

**Symptom:**
- Heating pauses during showers
- `status` attribute shows `state: "paused"` with condition `humidity_spike`

**How It Works:**
- Detects shower steam via rapid humidity rise or absolute threshold
- Pauses heating during shower (prevents wasted energy)
- Resumes after humidity stabilizes (drops below exit threshold)
- Prevents stale integral buildup via automatic decay (~10%/min)

**State Machine:**
```
NORMAL → PAUSED (spike detected) → STABILIZING (humidity drops) → NORMAL
```

**Troubleshooting:**

1. **False Positives (pausing when not showering)**
   - Increase `humidity_spike_threshold` (default: 15%)
   - Increase `humidity_absolute_max` (default: 80%)
   - Check humidity sensor placement (should be in bathroom, not hallway)

2. **Not Detecting Showers**
   - Decrease `humidity_spike_threshold` (try 10%)
   - Decrease `humidity_absolute_max` (try 70%)
   - Verify humidity sensor is working and updating

3. **Too Long Paused**
   - Decrease `humidity_stabilization_delay` (default: 300s = 5 min)
   - Decrease `humidity_exit_drop` (default: 5% drop from peak)
   - Note: Max pause is 60 minutes (safety limit)

**Example Configuration:**
```yaml
climate:
  - platform: adaptive_climate
    name: Bathroom
    humidity_sensor: sensor.bathroom_humidity
    humidity_spike_threshold: 12  # % rise to trigger
    humidity_absolute_max: 75     # % absolute cap
    humidity_exit_threshold: 65   # % absolute for exit
```

---

## Chronic Approach Failure (New in v0.46.0)

**Symptom:**
- Temperature consistently fails to reach setpoint across multiple consecutive cycles
- System never crosses setpoint (rise_time=None)
- Significant gap remains (undershoot)

**Meaning:**
- Indicates insufficient Ki (integral gain)
- System lacks the integral accumulation needed to eliminate steady-state error
- More severe than occasional undershoot

**How It Works:**
- Detector tracks consecutive cycles that never reach setpoint
- Heating-type-specific thresholds (floor: 4 cycles, radiator: 3 cycles, etc.)
- Automatically applies Ki boost when pattern detected
- Resets counter when any cycle successfully reaches setpoint

**Automatic Response:**
- Ki multiplier applied (1.20x to 1.35x depending on heating type)
- Recorded in pid_history with reason "chronic_approach_boost"
- Cooldown period prevents over-adjustment (24h for floor, scaling down to 3h for forced air)
- Cumulative Ki capped at 2.0x original value

**Manual Intervention:**
If chronic approach persists after automatic boost:
```yaml
service: adaptive_climate.set_pid_gain
data:
  ki: 8.0  # Increase Ki significantly
target:
  entity_id: climate.living_room
```

**Note:** This feature replaces the older generic "undershoot" detection with a more specific pattern detector.


## PID Tuning Problems

### When to Reset vs Adjust

**Reset to Physics (Start Over):**

Use `reset_pid_to_physics` when:
- PID values are completely wrong (system unstable)
- Changed heating system type
- Changed zone area or window configuration
- Adaptive learning went in wrong direction
- Want to start fresh after major changes

```yaml
service: adaptive_climate.reset_pid_to_physics
target:
  entity_id: climate.living_room
```

**Effects:**
- Recalculates initial PID from physics model
- Clears all adaptive learning history
- Resets Ke to default (if outdoor sensor configured)
- Preserves configuration (area, heating_type, etc.)

**Manual Adjustment (Fine-Tuning):**

Use `set_pid_gain` when:
- Small tweaks needed (±10-20%)
- Adaptive recommendations seem reasonable but want manual control
- Testing specific parameter changes

```yaml
service: adaptive_climate.set_pid_gain
data:
  kp: 22.0
  ki: 0.25
  kd: 3.5
target:
  entity_id: climate.living_room
```

### Auto-Apply PID (Recommended)

The system can automatically apply learned PID adjustments with safety validation.

**Recommended Configuration:**
```yaml
adaptive_climate:
  auto_apply_pid: true  # Enable automatic PID application
```

**How It Works:**
1. **Minimum 6 cycles** before auto-apply is enabled
2. **Convergence required**: 3 consecutive good cycles
3. **Safety validation**: Changes must pass validation checks
4. **Automatic recording**: All changes logged in `pid_history`
5. **Rollback protection**: Can restore from history if needed

**Checking Auto-Apply Status:**
```yaml
# In Developer Tools > States, look for:
learning_status: "stable"  # or "optimized"
cycles_collected: 8
convergence_confidence_pct: 75.0
pid_history:
  - timestamp: "2026-01-30T14:30:00+00:00"
    kp: 13.5
    ki: 3.8
    kd: 2.5
    ke: 0.5
    reason: "auto_apply"  # Automatic adjustment
    actor: "learning"
```

**If Not Auto-Applying:**

1. **Not enough cycles**:
   - Wait for more heating cycles to complete
   - Check `cycles_collected` attribute (need ≥6)
   - Each cycle needs minimum 5 minutes heating time

2. **Not converged**:
   - Check `learning_status` (should be "stable" or "optimized")
   - Check `convergence_confidence_pct` (should be >60%)
   - Avoid interrupting cycles (setpoint changes, mode changes)

3. **Auto-apply disabled**:
   - Check domain config has `auto_apply_pid: true`
   - Review logs for validation failures

**Manual Rollback:**
```yaml
# Restore gains from previous history entry
service: adaptive_climate.restore_pid_history
data:
  index: 0  # 0 = first entry (physics baseline)
target:
  entity_id: climate.living_room
```

## Log Analysis Tips

Enable debug logging for detailed troubleshooting:

```yaml
logger:
  default: info
  logs:
    custom_components.adaptive_climate: debug
    custom_components.adaptive_climate.pid_controller: debug
    custom_components.adaptive_climate.adaptive.learning: debug
```

### Key Log Patterns

**Startup and Initialization:**
```
Initialized PID: Kp=20.5, Ki=3.0, Kd=2.8, Ke=0.5
Thermal time constant: τ=45.2 min
Recorded physics_init to pid_history
```
- Verify PID values are reasonable (Ki should be >1.0, Ke should be 0.3-0.6)
- Check tau (thermal time constant) matches heating type
- Confirm physics_init entry added to pid_history

**Cycle Tracking:**
```
State transition: IDLE → HEATING
Collecting temperature samples (heating active)
State transition: HEATING → SETTLING (heater off after 18.5 min)
Temperature stabilized after 25 min
Cycle complete: overshoot=0.3°C, settling_time=25min
```
- Track state machine transitions
- Look for premature interruptions
- Verify cycles are completing

**PID Calculation:**
```
PID output: P=12.5, I=8.3, D=2.1, E=-0.4, total=22.5
Error: -0.8°C, integral: 45.2, derivative: 0.15°C/min
```
- Verify all terms are contributing
- Check for NaN or infinite values
- Look for integral windup (I term saturated)

**Adaptive Learning:**
```
Cycle analysis: overshoot=0.8°C, response_time=45min, settling_time=62min
Rule matched: OVERSHOOT_MEDIUM, reducing Kp by 10%
Auto-apply: Kp=18.5, Ki=3.0, Kd=3.2, Ke=0.5
Recorded auto_apply to pid_history
```
- Review detected issues (overshoot, oscillations, undershoot, etc.)
- Check if adjustments make sense
- Verify entry added to pid_history with reason "auto_apply"

**Outdoor Compensation (Ke):**
```
Physics-based Ke enabled: Ke=0.5 (house_energy_rating=C, area=20m²)
Recorded ke_physics to pid_history
```
- Verify Ke value matches house energy rating
- Check pid_history for Ke-related entries
- Ke adjustments via learning recorded with reason "ke_learning"

**Warnings to Investigate:**
```
WARNING: Short cycling detected (8.5 min). Consider increasing PWM period.
WARNING: High power consumption (28.3 W/m²). Check for heat loss.
WARNING: Insufficient data for adaptive Ke (outdoor_temp_range: 2.1°C)
```
- Actionable warnings indicating configuration issues
- Cross-reference with health sensor warnings

### Finding Specific Issues

**Temperature not responding:**
```bash
# Search for PID calculation errors
grep "PID output" home-assistant.log | tail -20

# Look for zero or very small output
# P, I, D, E should all be non-zero when heating needed
```

**Cycles not completing:**
```bash
# Search for state transitions
grep "State transition" home-assistant.log | tail -20

# Look for IDLE→HEATING without matching HEATING→SETTLING
# Or SETTLING→IDLE without "stabilized"
```

**Learning not working:**
```bash
# Search for cycle analysis
grep "Cycle analysis" home-assistant.log | tail -10

# Should see metrics calculated after each cycle
# If missing, cycles are being interrupted or invalidated
```

**Ke learning stuck:**
```bash
# Search for Ke observations
grep "Ke observation" home-assistant.log | tail -20

# Should see regular observations during heating
# Check outdoor temperature variation
```

## When to Use Services

Summary of available services and when to use them.

### reset_pid_to_physics

**Use When:**
- Starting over from scratch
- Changed heating system configuration
- PID values are completely wrong
- Adaptive learning went off track

**Effect:**
- Recalculates PID from physics model
- Clears all learning history
- Resets Ke to default

**Example:**
```yaml
service: adaptive_climate.reset_pid_to_physics
target:
  entity_id: climate.living_room
```

### delete_pid_history (New in v0.46.0)

**Use When:**
- Want to remove specific PID history entries
- Need to clean up bad adjustments
- Debugging PID tuning issues

**Parameters:**
- `index`: Index of the history entry to delete (0 = oldest)
- `mode`: "heat" or "cool" (optional, defaults to current mode)

**Example:**
```yaml
service: adaptive_climate.delete_pid_history
data:
  index: 2  # Delete the 3rd entry (0-indexed)
target:
  entity_id: climate.living_room
```

### restore_pid_history (New in v0.46.0)

**Use When:**
- Want to revert to previous PID gains
- Testing different gain configurations
- Rollback after bad auto-adjustment

**Parameters:**
- `index`: Index of the history entry to restore from (0 = oldest)
- `mode`: "heat" or "cool" (optional, defaults to current mode)

**Example:**
```yaml
service: adaptive_climate.restore_pid_history
data:
  index: 0  # Restore gains from first history entry (physics-based)
target:
  entity_id: climate.living_room
```

### set_pid_gain

**Use When:**
- Manual fine-tuning needed
- Want to override specific parameter
- Testing hypothesis about optimal values

**Parameters:**
- `kp`: Proportional gain (10-500)
- `ki`: Integral gain (0-100)
- `kd`: Derivative gain (0-200)
- `ke`: Outdoor compensation (0.0-0.002)

**Example:**
```yaml
service: adaptive_climate.set_pid_gain
data:
  kp: 22.0
  ki: 0.3
  kd: 4.0
  ke: 0.0005
target:
  entity_id: climate.living_room
```


## Entity Attribute Debugging

Key attributes to check when troubleshooting.

### Temperature Attributes
| Attribute | Description | Normal Range |
|-----------|-------------|--------------|
| `current_temperature` | Current zone temperature | Sensor reading |
| `temperature` | Target setpoint | User-configured |
| `outdoor_temperature` | Outdoor temperature (if configured) | Sensor reading |

### PID Attributes
| Attribute | Description | Notes |
|-----------|-------------|-------|
| `pid_history` | List of PID gain changes | Check most recent entry for current gains |
| `integral` | Current integral term value | Should accumulate when below setpoint |
| `control_output` | Current PID output (%) | 0-100% heating demand |

**PID History Format:**
```yaml
pid_history:
  - timestamp: "2026-01-30T10:30:00+00:00"
    kp: 15.0
    ki: 3.0
    kd: 2.5
    ke: 0.5
    reason: "physics_init"  # or auto_apply, chronic_approach_boost, etc.
    actor: "system"  # or learning, user
```

### Learning Attributes
| Attribute | Description | Expected Values |
|-----------|-------------|-----------------|
| `learning_status` | Learning state | "collecting", "stable", "optimized" |
| `cycles_collected` | Complete heating cycles | Increments after each cycle |
| `convergence_confidence_pct` | Overall confidence | 0-100% |

### Performance Attributes
| Attribute | Description | Notes |
|-----------|-------------|-------|
| `control_output` | Current PID output percentage | 0-100% |
| `duty_accumulator_pct` | PWM accumulation as % of threshold | For PWM mode |

**Note:** Performance metrics like duty_cycle_pct, power_w_m2, and cycle_time_min are now in dedicated sensor entities (`sensor.{zone}_pid_performance`)

### Operational Status
| Attribute | Description | Values |
|-----------|-------------|--------|
| `status` | Consolidated operational status | Dict with state, conditions, etc. |

**Status Format:**
```yaml
status:
  state: "heating"  # idle, heating, cooling, paused, preheating, settling
  conditions: ["night_setback"]  # List of active conditions
  setback_delta: 2.0  # During night setback
  setback_end: "2026-01-30T07:00:00+00:00"  # When night period ends
```

### Debug Attributes (when `debug: true`)
| Attribute | Description | Use Case |
|-----------|-------------|----------|
| `convergence_confidence_pct` | Learning confidence (0-100%) | Monitor learning progress |
| `cycles_collected` | Complete heating cycles analyzed | Track learning data |
| `duty_accumulator_pct` | PWM accumulation % of threshold | Debug PWM timing |
| `pid_p_term` | Proportional contribution | Verify P term active |
| `pid_i_term` | Integral contribution | Check integral windup |
| `pid_d_term` | Derivative contribution | Confirm D term damping |
| `pid_e_term` | Outdoor compensation | Validate Ke effect |
| `error` | Current temperature error | Setpoint - current |

---

[← Back to Home](https://github.com/afewyards/ha-adaptive-climate/wiki/Home) | [Advanced Topics →](https://github.com/afewyards/ha-adaptive-climate/wiki/Advanced-Topics)
