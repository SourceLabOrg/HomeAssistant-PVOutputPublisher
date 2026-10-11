# Design Specification: V2 Schema Migration & Unified Parameter Mapping

## 1. Overview & Motivation
The **HomeAssistant-PVOutputPublisher** integration is transitioning from its legacy v1 configuration schema to a **unified, parameter-aligned v2 schema**. 

### Legacy (v1) Limitations:
* **Ambiguous Heuristics:** Used generic "Primary" and "Secondary" solar sensor inputs and attempted runtime auto-detection of Power ($W$) vs. Energy ($Wh$).
* **Limited Extensibility:** Could not support PVOutput extended parameters (`v7`–`v12`), explicit net flag (`n=1`), or manual cumulative flag overrides (`c1=1`).
* **Lack of User Context:** No ability to save internal notes for multi-system setups.

### V2 Goals:
* **Unified UI:** A single, clear configuration form directly aligned with PVOutput's `addstatus.jsp` API parameters (`v1` through `v12`, `c1`, `n`).
* **Zero Disruption via Migration:** Automated, robust migration from Schema v1 to v2 on install/startup (`async_migrate_entry`).
* **Local Notes Field:** User-facing internal notes field stored per system, omitted from API payloads.
* **Maintainable Architecture:** Single schema, single UI flow, single payload generator, and high test coverage.

---

## 2. V2 Data Model & Configuration Keys

### 2.1 Configuration Keys (`const.py`)
```python
# Integration Scope
DOMAIN = "pvoutput_publisher"
CONF_API_KEY = "api_key"
CONF_SYSTEMS = "systems"

# System Common
CONF_NAME = "name"
CONF_SYSTEM_ID = "system_id"
CONF_FREQUENCY = "frequency"
CONF_NOTES = "notes"  # Internal notes (string, omitted from API)

# PVOutput 1-to-1 API Parameters
CONF_V1 = "v1"    # Energy Generation (Wh)
CONF_V2 = "v2"    # Power Generation (W)
CONF_V3 = "v3"    # Energy Consumption (Wh)
CONF_V4 = "v4"    # Power Consumption (W)
CONF_V5 = "v5"    # Temperature (°C / °F)
CONF_V6 = "v6"    # Voltage (V)
CONF_V7 = "v7"    # Extended Data 1
CONF_V8 = "v8"    # Extended Data 2
CONF_V9 = "v9"    # Extended Data 3
CONF_V10 = "v10"  # Extended Data 4
CONF_V11 = "v11"  # Extended Data 5
CONF_V12 = "v12"  # Extended Data 6

# PVOutput Flags
CONF_C1 = "c1"    # Cumulative Energy Flag (bool -> &c1=1)
CONF_NET = "n"    # Net Power Flag (bool -> &n=1)

DEFAULT_FREQUENCY = "5"
PVOUTPUT_API_URL = "https://pvoutput.org/service/r2/addstatus.jsp"
```

---

## 3. V1 to V2 Migration Logic (`async_migrate_entry`)

When Home Assistant loads a ConfigEntry with `entry.version == 1`, `async_migrate_entry(hass, entry)` is automatically invoked.

```
[V1 Config Entry]
  ├── api_key
  └── systems: [ { name, system_id, entity_id, secondary_entity_id, consumption_entity_id, temperature_entity_id, voltage_entity_id, frequency } ]
        │
        ▼ (async_migrate_entry)
  Inspect Entity Registry & Live States for each system:
    1. Primary (entity_id) & Secondary (secondary_entity_id):
       - If unit in [Wh, kWh, MWh] or device_class == energy:
           -> Map to v1
           -> If state_class in [total, total_increasing]: Set c1 = True
       - If unit in [W, kW] or device_class == power:
           -> Map to v2
       - If state/registry unavailable: Name fallback ("energy" in id -> v1, else v2)
    2. Consumption (consumption_entity_id):
       - If unit in [Wh, kWh, MWh] or device_class == energy:
           -> Map to v3
       - Else:
           -> Map to v4
    3. Temperature (temperature_entity_id) -> Map to v5
    4. Voltage (voltage_entity_id)         -> Map to v6
    5. Notes (notes)                       -> Initialize as "" (empty string)
    6. Extended (v7..v12)                  -> Initialize as None / omitted
    7. Flags (c1, n)                       -> Default based on above or False
        │
        ▼
[V2 Config Entry (version=2)] Saved and returned to HA
```

### 3.1 Migration Safety Guarantees
* **Multi-Layer Introspection:** Checks 1) Live State machine (`hass.states`), 2) Entity Registry (`er.async_get(hass)`), and 3) Entity ID string heuristics (`"energy"`, `"power"`, `"kwh"`, `"w"`).
* **Non-Destructive:** If migration encounters an unrecognized structure, it preserves all existing keys while upgrading version to prevent data loss.
* **Test Verification:** Dedicated migration unit tests with mocked v1 entries verifying exact v2 outputs.

---

## 4. UI & Form Schema (`config_flow.py`)

Config flow and options flow use a single unified system schema `_get_system_schema(existing_data)`:

| Field | Type / Selector | Description |
| :--- | :--- | :--- |
| `name` | Text (Required) | Friendly name of solar array |
| `system_id` | Text (Required) | PVOutput System ID |
| `frequency` | Select (Required) | Push frequency (5m, 10m, 15m, 30m, 1h, 3h) |
| `notes` | Text (Optional) | Internal reference notes (not sent to API) |
| `v1` | Sensor Selector (`device_class="energy"`) | **v1: Energy Generation** (Wh, converts kWh/MWh) |
| `v2` | Sensor Selector (`device_class="power"`) | **v2: Power Generation** (W, converts kW) |
| `v3` | Sensor Selector (`device_class="energy"`) | **v3: Energy Consumption** (Wh, converts kWh/MWh) |
| `v4` | Sensor Selector (`device_class="power"`) | **v4: Power Consumption** (W, converts kW) |
| `v5` | Sensor Selector (`device_class="temperature"`) | **v5: Temperature** (°C / °F with auto-conversion) |
| `v6` | Sensor Selector (`device_class="voltage"`) | **v6: Voltage** (V) |
| `v7` – `v12` | Sensor Selector (Optional) | **v7 – v12: Extended Data** (Donation features) |
| `c1` | Boolean Toggle | **Cumulative Flag (`c1=1`)**: Generation/Consumption is lifetime |
| `n` | Boolean Toggle | **Net Flag (`n=1`)**: Power generation is net export |

---

## 5. Payload Generation & Push Logic (`__init__.py`)

At scheduled intervals, for each configured v2 system:
1. Build timestamp: `d=YYYYMMDD&t=HH:MM`.
2. Inspect each mapped parameter `v1` through `v12`:
   * Fetch entity state. Skip if `unknown`, `unavailable`, or invalid float.
   * Apply unit conversions:
     * `v1` / `v3`: `kwh` $\rightarrow \times 1000$, `mwh` $\rightarrow \times 10^6$. Output as integer.
     * `v2` / `v4`: `kw` / `kilowatt(s)` $\rightarrow \times 1000$. Output as integer.
     * `v5`: `°f` / `f` $\rightarrow (F - 32) \times \frac{5}{9}$. Output as float `%.1f`.
     * `v6`: Output as float `%.1f`.
     * `v7`–`v12`: Output as formatted numeric value.
3. Append flags:
   * If `c1` is `True`: Append `&c1=1`.
   * If `n` is `True`: Append `&n=1`.
4. Log human-readable summary at `INFO` level.
5. POST payload with headers (`X-Pvoutput-Apikey`, `X-Pvoutput-SystemId`).

---

## 6. Implementation Roadmap & Running Checklist

- [x] **Step 1: Constants & Data Model**
  - Updated `custom_components/pvoutput_publisher/const.py` with `CONF_V1`..`CONF_V12`, `CONF_C1`, `CONF_NET`, `CONF_NOTES`.
- [x] **Step 2: Migration Engine**
  - Implemented `async_migrate_entry(hass, config_entry)` in `__init__.py`.
  - Implemented helper function `migrate_v1_system_to_v2(hass, system_data)`.
- [x] **Step 3: Configuration & Options Flow**
  - Updated `PVOutputPusherConfigFlow.VERSION = 2`.
  - Updated `_get_system_schema()` in `config_flow.py` for v2 fields and notes.
- [x] **Step 4: Push Pipeline in `__init__.py`**
  - Updated `push_data()` to process v2 system fields, flags, and notes.
- [x] **Step 5: Base English Translations (`en.json`)**
  - Added friendly labels and helper tooltips for v1..v12, c1, net, and notes in `en.json`.
- [x] **Step 6: Unit & Integration Tests**
  - Added unit tests for `async_migrate_entry` (live state present, registry lookup, fallback naming, idempotency, duplicate sensors, secondary-only configs, consumption lifetime).
  - Updated config flow tests for v2 schema and full field editing.
  - Updated push payload tests for v2 parameters, flags, unit conversions, and notes exclusion.
  - Test suite passing with 22/22 tests (95% coverage).
- [x] **Step 7: Documentation (`README.md`, `CHANGELOG.md`)**
  - Updated `README.md` to document the V2 parameter mapping, notes field, and migration.
  - Updated `CHANGELOG.md` with 2.0.0 release notes.
- [ ] **Step 8: Multi-Language Translations (Final Phase)**
  - Generate updated translations for `de.json`, `es.json`, `ja.json`, `zh-Hans.json`, `zh-Hant.json` once UI adjustments and iterations are finalized.

---

## 7. Discoveries & Implementation Notes
*(Updated dynamically during implementation)*
- *2026-10-11:* Switched from dual-mode toggle to unified v2 architecture with automated `async_migrate_entry` to provide cleaner UX and zero configuration ambiguity.
- *2026-10-11:* English translation (`en.json`) updated first; other language files deferred to final phase per iterative development plan.
- *2026-10-11:* Migration logic refined to prevent duplicate sensor assignments (e.g. if a user configured two energy sensors in v1, secondary energy is safely ignored rather than mistakenly placed into `v2` Power).

