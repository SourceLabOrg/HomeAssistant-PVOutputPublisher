# Change Log
The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

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
