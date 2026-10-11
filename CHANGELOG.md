# Change Log
The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## 2.0.0 (10/11/2026)

### Breaking Changes / Architecture Upgrade
- Upgraded configuration schema to **Version 2** with direct 1-to-1 parameter mappings to the PVOutput API (`v1`–`v12`, `c1` cumulative flag, `n` net flag).
- Automated, non-destructive migration (`async_migrate_entry`) from v1 to v2 on installation/startup with zero configuration loss.
- **Cumulative Energy Flag (`c1`) Migration Note:**
  - Migrated systems with an Energy Generation sensor (`v1`) default the **Cumulative Energy Flag (`c1=1`)** to enabled. This matches PVOutput's requirement for lifetime counter sensors (such as inverter lifetime yield) so PVOutput calculates interval yields instead of rejecting the value as "Energy value too high".
  - **How to verify your configuration:** Go to **Settings > Devices & Services > PVOutput Publisher > Configure**, then click **Edit** on your array. 
    - If your `v1` sensor is a lifetime yield counter (monotonically increasing and does not reset to 0 daily), keep **Cumulative Energy Flag (c1=1)** checked.
    - If your `v1` sensor resets to 0 at midnight (daily yield), uncheck this box.

### Feature Changes
- Added support for Extended Data parameters `v7` through `v12` (PVOutput donation features).
- Added support for explicit Net Flag (`n=1`) and Cumulative Energy Flag (`c1=1`).
- Added internal private **Notes** field per solar array for user reference.

## 1.2.0 (06/05/2026)

### Feature Changes
- Add support for optional voltage sensor (v6 parameter). (Issue#5)[https://github.com/SourceLabOrg/HomeAssistant-PVOutputPublisher/issues/5]

## 1.1.0 (05/20/2026)

### Feature Changes
- Switched to strict, clock-aligned scheduling to prevent time drift and perfectly sync with PVOutput intervals. (Issue#1)[https://github.com/SourceLabOrg/HomeAssistant-PVOutputPublisher/issues/1]
- Added support for an optional secondary solar sensor to upload Power and Energy data simultaneously for maximum accuracy.
- Add language support for Chinese (Simplified & Traditional)

### Bugfixes
- Removes `device_class=temperature` restriction when picking your temperature sensor. (Issue#1)[https://github.com/SourceLabOrg/HomeAssistant-PVOutputPublisher/issues/1]

## 1.0.1 (03/23/2026)
Setup and submitted to HACs!

## 1.0.0 (03/23/2026)
Initial internal release!
