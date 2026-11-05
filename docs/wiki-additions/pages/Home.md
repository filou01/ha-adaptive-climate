# Adaptive Climate Documentation

<!-- pump-aware-fork-preview:start -->
## Optional fork extension documentation

**Fork preview, not an upstream release feature.** The following information applies to `filou01/ha-adaptive-climate`, branch `codex/pump-aware-pwm`, [preview v0.67.1-pwm.8](https://github.com/filou01/ha-adaptive-climate/releases/tag/v0.67.1-pwm.8). Do not assume the upstream release supports this configuration.

An opt-in pump-aware HEAT PWM preview is developed separately from upstream.
It coordinates genuine zone pulses on one shared electrically OR-controlled
pump; it does not own the pump relay or infer physical flow. The fork also
contains narrow learning/startup corrections. Original project features and
fork previews must be distinguished when choosing a HACS repository or YAML.

See [Fork Extensions](Fork-Extensions.md) for English/German guides, current
configuration, version history, diagnostics, test plans and rollback.
<!-- pump-aware-fork-preview:end -->

Welcome to the comprehensive documentation for **Adaptive Climate** (v0.47.0) - an advanced Home Assistant thermostat integration featuring PID control with automatic tuning, adaptive learning, multi-zone coordination, and energy optimization.

## Quick Links

- [Main Repository](https://github.com/afewyards/ha-adaptive-climate)
- [Installation Guide](https://github.com/afewyards/ha-adaptive-climate/wiki/Installation-&-Setup)
- [Quick Start](https://github.com/afewyards/ha-adaptive-climate/wiki/Installation-&-Setup#quick-start)
- [GitHub Issues](https://github.com/afewyards/ha-adaptive-climate/issues)
- [Companion Lovelace Card](https://github.com/afewyards/adaptive-climate-card)

## Documentation Index

### Getting Started
- **[Installation & Setup](https://github.com/afewyards/ha-adaptive-climate/wiki/Installation-&-Setup)** - HACS and manual installation, initial configuration, first-time tuning
- **[Configuration Reference](https://github.com/afewyards/ha-adaptive-climate/wiki/Configuration-Reference)** - Complete parameter tables, configuration examples, YAML validation

### Core Features
- **[PID Control](https://github.com/afewyards/ha-adaptive-climate/wiki/PID-Control)** - How PID works, P/I/D/E/F terms, PWM vs valve control
- **[Adaptive Learning](https://github.com/afewyards/ha-adaptive-climate/wiki/Adaptive-Learning)** - What it learns, cycle tracking, PID adjustment rules, chronic approach detection
- **[Automatic PID Application](https://github.com/afewyards/ha-adaptive-climate/wiki/Automatic-PID-Application)** - Auto-apply, validation, rollback, safety limits
- **[Physics-Based Initialization](https://github.com/afewyards/ha-adaptive-climate/wiki/Physics-Based-Initialization)** - Thermal calculations, heating type characteristics, zone properties

### Advanced Features
- **[Multi-Zone Coordination](https://github.com/afewyards/ha-adaptive-climate/wiki/Multi-Zone-Coordination)** - Central heat source control, mode sync, thermal groups, manifold transport delay
- **[Energy Optimization](https://github.com/afewyards/ha-adaptive-climate/wiki/Energy-Optimization)** - Night setback with predictive preheat, open window detection, humidity-based steam detection, contact sensors, outdoor compensation
- **[Actuator Wear Tracking](https://github.com/afewyards/ha-adaptive-climate/wiki/Actuator-Wear-Tracking)** - Cycle counting, maintenance alerts, predictive maintenance

### Monitoring & Management
- **[Sensors & Monitoring](https://github.com/afewyards/ha-adaptive-climate/wiki/Sensors-&-Monitoring)** - Performance sensors, health monitoring, energy tracking, reports
- **[Services](https://github.com/afewyards/ha-adaptive-climate/wiki/Services)** - Domain services, entity services, automation patterns

### Help & Development
- **[Troubleshooting](https://github.com/afewyards/ha-adaptive-climate/wiki/Troubleshooting)** - Diagnostic checklist, common issues, health warnings
- **[Advanced Topics](https://github.com/afewyards/ha-adaptive-climate/wiki/Advanced-Topics)** - Custom presets, integrations, debugging, performance optimization
- **[Migration Guide](https://github.com/afewyards/ha-adaptive-climate/wiki/Migration-Guide)** - From HASmartThermostat, generic_thermostat, version updates
- **[Development](https://github.com/afewyards/ha-adaptive-climate/wiki/Development)** - Architecture, test organization, contributing

## Prerequisites

- Home Assistant 2023.1 or newer
- At least one temperature sensor
- At least one heating/cooling switch or valve
- Python 3.11+ (included in Home Assistant)

## Key Concepts

### Adaptive Learning
The thermostat automatically learns from heating cycles and adjusts PID parameters over time. Give it 3-7 days to optimize performance for your specific space. The system tracks convergence confidence and applies tuning automatically when thresholds are met.

### Outdoor Compensation (Ke)
When an outdoor temperature sensor is configured, the system uses physics-based Ke initialization, then fine-tunes Ke after PID converges. This ensures optimal performance across all weather conditions.

### Physics-Based Initialization
Initial PID values are calculated from your zone's physical properties (heating type, area, windows) using empirical values from real-world HVAC systems. No manual tuning required.

### Setpoint Feedforward
Detects setpoint changes and applies integral boost/decay to accelerate PID response without overshoot. Enabled by default.

### Multi-Zone Coordination
Multiple thermostats can work together, sharing a central heat source, synchronizing modes, and coordinating via thermal groups for optimal efficiency.

### Disturbance Handling
Automatic detection and compensation for:
- Open windows (algorithmic detection via rapid temperature drop)
- Humidity spikes (bathroom steam detection with automatic pause/resume)
- Contact sensors (door/window sensors with configurable actions)
- Chronic approach failure (persistent inability to reach setpoint with Ki boost)

### Predictive Features
- **Preheat learning** - Learns heating rate to reach target exactly at scheduled time
- **Auto mode switching** - House-wide HVAC mode switching based on outdoor temperature with seasonal locking

## Support

- **Issues**: [GitHub Issues](https://github.com/afewyards/ha-adaptive-climate/issues)
- **Discussions**: [GitHub Discussions](https://github.com/afewyards/ha-adaptive-climate/discussions)

## Credits

This integration is a fork of [HASmartThermostat](https://github.com/ScratMan/HASmartThermostat) by ScratMan, with extensive enhancements for adaptive learning and multi-zone coordination.

---

*Last updated: January 2026*
